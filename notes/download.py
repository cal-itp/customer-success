import os
from pathlib import Path

from hubspot import HubSpot
from hubspot.crm.objects import BatchReadInputSimplePublicObjectId
import pandas as pd

from data.utils import chunk_list, hubspot_get_all_pages, hubspot_to_df, write_json_records


ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
LAST_NOTE_PATH = Path("last_note_id")
PAGE_SIZE = int(os.environ["HUBSPOT_PAGE_SIZE"])

ASSOCIATION_TYPES = ["companies", "vendors"]
ASSOCIATION_COLUMNS = [f"associations.{assoc}.results" for assoc in ASSOCIATION_TYPES]
ASSOCIATION_COLUMNS_COMPANIES = ASSOCIATION_COLUMNS[0]
ASSOCIATION_COLUMNS_VENDORS = ASSOCIATION_COLUMNS[1]

hubspot = HubSpot(access_token=ACCESS_TOKEN)
hubspot_companies_api = hubspot.crm.companies.batch_api
hubspot_notes_api = hubspot.crm.objects.notes.basic_api
hubspot_objects_api = hubspot.crm.objects.basic_api
hubspot_objects_batch_api = hubspot.crm.objects.batch_api
hubspot_properties_api = hubspot.crm.properties.core_api


def get_last_note_id():
    try:
        return LAST_NOTE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def update_last_note_id(last_note_id):
    LAST_NOTE_PATH.write_text(str(last_note_id).strip(), encoding="utf-8")


def get_notes() -> pd.DataFrame:
    note_props = ["hs_created_by", "hs_createdate", "hs_note_body"]
    last_note_id = get_last_note_id()

    notes_responses = hubspot_get_all_pages(
        hubspot_notes_api, page_size=PAGE_SIZE, after=last_note_id, properties=note_props, associations=ASSOCIATION_TYPES
    )

    update_last_note_id(notes_responses[-1].results[-1].id)

    return hubspot_to_df(notes_responses)


def preprocess_notes(notes: pd.DataFrame) -> pd.DataFrame:
    # rename vendor association column
    # weird name, maybe because it is a custom association type?
    notes[ASSOCIATION_COLUMNS_VENDORS] = notes["associations.p5519226_vendors.results"]

    # select only the columns needed for later
    cols = {
        "created_at": "created_at",
        "id": "id_note",
        "properties.hs_created_by": "id_user",
        "properties.hs_note_body": "body",
        ASSOCIATION_COLUMNS_COMPANIES: ASSOCIATION_COLUMNS_COMPANIES,
        ASSOCIATION_COLUMNS_VENDORS: ASSOCIATION_COLUMNS_VENDORS,
    }
    notes = notes[cols.keys()]
    # and rename some for simplicity
    notes = notes.rename(columns=cols)

    # drop notes without a body
    notes = notes.dropna(subset=["body"])

    # drop notes without a creator
    notes = notes.dropna(subset=["id_user"])

    # drop notes without any of the association types (e.g. all are NA)
    notes = notes.dropna(subset=ASSOCIATION_COLUMNS, how="all")

    # expand list-like association columns into rows
    # there should be only max 1 of each association type per row
    # explode each column separately since they have different counts of NAs
    # the resulting DataFrame should have
    #    row count == count of rows with company association
    #               + count of rows with vendor association
    notes = notes.explode(ASSOCIATION_COLUMNS_COMPANIES, ignore_index=True).explode(
        ASSOCIATION_COLUMNS_VENDORS, ignore_index=True
    )

    # expand dict row values into columns
    # e.g. the columns have values like:
    #     {"id": 12345, "type": "note_to_company"}
    # and we want to pull the value from "id" into its own column in the DataFrame

    # .apply(pd.Series) converts the value to a DataFrame with a column for each key in the dict (id, type)
    # ["id"] keeps only the column we need
    # .concat puts the columns into a single DataFrame
    id_company = notes[ASSOCIATION_COLUMNS_COMPANIES].apply(pd.Series)["id"]
    notes = pd.concat([notes, id_company], axis=1).rename(columns={"id": "id_company"})

    id_vendor = notes[ASSOCIATION_COLUMNS_VENDORS].apply(pd.Series)["id"]
    notes = pd.concat([notes, id_vendor], axis=1).rename(columns={"id": "id_vendor"})

    # remove now-expanded columns and clean up index
    notes = notes.drop(columns=ASSOCIATION_COLUMNS)
    notes.reset_index(drop=True, inplace=True)

    return notes


def join_companies(notes: pd.DataFrame) -> pd.DataFrame:
    note_company_ids = [{"id": id} for id in set(notes["id_company"].dropna())]
    responses = []

    # batch requests support a max of 100 parameters
    for note_company_id_chunk in chunk_list(note_company_ids, 100):
        batch_request = BatchReadInputSimplePublicObjectId(inputs=note_company_id_chunk, properties=["company_type", "name"])
        responses.append(hubspot_companies_api.read(batch_request, archived=False))

    companies = hubspot_to_df(responses)

    # filter to only Transit Agency companies
    companies = companies.loc[companies["properties.company_type"].eq("Transit Agency")]
    # keep only the columns we want, and rename
    companies = companies[["id", "properties.name"]].rename(columns={"id": "id_company", "properties.name": "name_company"})
    companies.reset_index(drop=True, inplace=True)

    # merge back with the notes DataFrame
    # left join since some notes are associated with vendors and not companies
    # so want to keep all the notes
    notes = notes.merge(companies, how="left", on="id_company")
    notes.reset_index(drop=True, inplace=True)
    # drop notes where there was a company ID but no company name (e.g. the note's company was not a Transit Agency)
    notes.drop(notes[(~notes["id_company"].isna()) & (notes["name_company"].isna())].index, inplace=True)

    return notes


def join_users(notes: pd.DataFrame) -> pd.DataFrame:
    user_props = ["hs_given_name", "hs_family_name"]
    users_responses = hubspot_get_all_pages(
        hubspot_objects_api, page_size=PAGE_SIZE, object_type="users", properties=user_props
    )
    users = hubspot_to_df(users_responses)  # noqa: F841

    # TODO: map note creator to user, getting first/last name

    return notes


def join_vendors(notes: pd.DataFrame) -> pd.DataFrame:
    note_vendor_ids = [{"id": id} for id in set(notes["id_vendor"].dropna())]
    responses = []

    # batch requests support a max of 100 parameters
    for note_vendor_id_chunk in chunk_list(note_vendor_ids, 100):
        batch_request = BatchReadInputSimplePublicObjectId(inputs=note_vendor_id_chunk, properties=["vendor_name"])
        responses.append(hubspot_objects_batch_api.read("vendors", batch_request, archived=False))

    vendors = hubspot_to_df(responses)

    # keep only the columns we want, and rename
    vendors = vendors[["id", "properties.vendor_name"]].rename(
        columns={"id": "id_vendor", "properties.vendor_name": "name_vendor"}
    )
    vendors.reset_index(drop=True, inplace=True)

    # merge back with the notes DataFrame
    notes = notes.merge(vendors, how="left", on="id_vendor")
    notes.reset_index(drop=True, inplace=True)

    return notes


if __name__ == "__main__":
    notes = get_notes()

    notes = preprocess_notes(notes)
    notes = join_companies(notes)
    notes = join_users(notes)
    notes = join_vendors(notes)

    write_json_records(notes, "notes.json")