import argparse
import datetime as dt
import io
import os
import sys
import time
import zipfile

import pandas as pd
import requests
from hubspot import HubSpot
from hubspot.crm.exports import PublicExportRequest

from . import objects
from .objects import DataTypeSlug
from .utils import hubspot_get_all_pages, write_csv_records

ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
DATA_TYPES = [member.name.lower() for member in DataTypeSlug]
PAGE_SIZE = int(os.environ.get("HUBSPOT_PAGE_SIZE", 10))

hubspot = HubSpot(access_token=ACCESS_TOKEN)


def get_all_object_names() -> dict:
    """Generate simple dict of all object IDs with a human-readable representation of them.

    Not all of the human-readable representations are "names", per se, but using that term for simplicity.

    Returns dict in the format:
    {
        object_id: name,
        object_id: name,
        ...
    }
    """

    field_to_return = {
        DataTypeSlug.COMPANIES: ["name", "domain"],
        DataTypeSlug.CONTACTS: ["firstname", "lastname", "email"],
        DataTypeSlug.DEALS: ["dealname"],
        DataTypeSlug.TICKETS: ["subject"],
        DataTypeSlug.VENDORS: ["vendor_name"],
    }

    object_names = {}

    for object_type, fields in field_to_return.items():
        objects = hubspot.crm.objects.get_all(object_type, properties=field_to_return[object_type])

        match object_type:
            case DataTypeSlug.COMPANIES:
                # If no name, fall back to domain. If no domain, fall back to string to avoid None type errors.
                objects = {o.id: o.properties.get("name") or o.properties.get("domain") or "Unknown" for o in objects}
                object_names |= objects
            case DataTypeSlug.CONTACTS:
                # Not all contacts have a first name, last name, or email.
                # Combine names and emails for disambiguation.
                # Even if all three are missing, we end up with a string to avoid None type errors.
                for o in objects:
                    id = o.id
                    name = (
                        f"{o.properties.get('firstname') or '[unknown]'} "
                        f"{o.properties.get('lastname') or '[unknown]'} "
                        f"<{o.properties.get('email') or 'unknown'}>"
                    )
                    object_names |= {id: name}
            case _:
                # All deals, tickets, and vendors currently have no objects that are missing the desired field.
                objects = {o.id: o.properties.get(field_to_return[object_type][0]) or "" for o in objects}
                object_names |= objects

    return object_names


def request_exports(
    object_type: str,
    associations: list[list[str]],
    total_exports: int,
    core_props: list[str],
    extra_props: list[str],
    nicename: str = "",
) -> list[object]:
    """Request as many exports as needed for an object type with its associations and return their confirmation responses.

    Must be done in multiple parts because the HubSpot export API will only accept four associated object types at a time.
    `associations` should be a list of lists of HubSpot object type strings, each sublist with no more than four entries.
    """
    export_requests = []

    for index, association_set in enumerate(associations):
        # Always include the core props, but include the extra props for the first export.
        # This can't just be `props = core_props` because then it will point to the same location in memory
        # and mutate core_props in a way that persists through future iterations.
        props = []
        props += core_props

        if index == 0:
            props += extra_props

        public_export_request = PublicExportRequest(
            export_type="VIEW",
            format="CSV",
            export_name=f"Full {nicename or object_type} export ({index + 1} of {total_exports})",
            object_type=object_type,
            object_properties=props,
            associated_object_type=association_set,
        )

        export_requests.append(hubspot.crm.exports.public_exports_api.start(public_export_request))

    return export_requests


def replace_ids_with_names(ids, id_name_mapping: dict) -> str:
    """Replace numeric ID values in `ids` with a human-readable representation from `id_name_mapping`.

    `ids` is expected to be 0, 1, or 2+ (semicolon-separated) ID values.
    `id_name_mapping` is expected to have this format: { id: name }

    The return value adds a space after the semicolons, since the goal is human readability.
    """

    try:
        return "; ".join([id_name_mapping.get(id.strip(), id) for id in str(ids).split(";")]) if pd.notna(ids) else ""
    except Exception:
        return "error processing this data"


def download_exports_to_csv(
    object_type: str,
    export_requests: list[object],
    total_exports: int,
    output_subdir: str = "",
    associations: bool = True,
    id_name_mapping: dict | None = None,
):
    """Wait for exports to complete, collect exported CSV files, and combine into one CSV file.

    `export_requests` should be a list of responses from HubSpot export API calls
    (e.g., the return value of the `request_exports()` function)
    """
    dfs = []

    for index, export_request in enumerate(export_requests):
        status = None
        timer = 5 * 60  # 5 minutes in seconds
        print(f"Checking status of export request {index + 1} of {total_exports}...", end="")

        while timer > 0:
            time.sleep(5)
            if status := hubspot.crm.exports.public_exports_api.get_status(getattr(export_request, "id")):
                if getattr(status, "status") == "COMPLETE":
                    print("complete! Downloading data.")

                    result = getattr(status, "result")

                    if result and ".zip" in result:
                        # Download the zip file into memory.
                        response = requests.get(result)
                        response.raise_for_status()  # ensure the download was successful

                        # Open the zip file from memory.
                        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                            # Find the first file inside the zip that ends with '.csv'
                            csv_files = [f for f in z.namelist() if f.endswith(".csv")]

                            if not csv_files:
                                raise ValueError(f"No CSV file found inside the zip archive at {result}")

                            target_csv = csv_files[0]

                            # Open that specific CSV and read it into Pandas.
                            with z.open(target_csv) as f:
                                df = pd.read_csv(f)
                    else:
                        # Download export CSV directly into DataFrame.
                        storage_options = {"User-Agent": "Mozilla/5.0"}  # needed to prevent HubSpot from returning a 403
                        df = pd.read_csv(result, storage_options=storage_options)

                    # Dynamically grab the name of the first column.
                    first_column = df.columns[0]

                    # Set the first column as the index so Pandas can match rows across files.
                    df.set_index(first_column, inplace=True)

                    dfs.append(df)
                    break
            timer -= 5
            print(".", end="")

    # Combine the DataFrames horizontally (axis=1).
    # This merges them based on the index (the first column we set above).
    combined_df = pd.concat(dfs, axis=1)

    # Drop any duplicated columns.
    # .duplicated() flags duplicates as True, the ~ operator inverts it to keep only the unique columns.
    combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]

    # Reset the index to turn the first column back into a regular data column.
    combined_df.reset_index(inplace=True)

    if associations:
        # Check association columns and replace IDs with names
        if "Associated Company IDs" in combined_df and combined_df["Associated Company IDs"].any():
            combined_df["Associated Companies"] = combined_df["Associated Company IDs"].apply(
                replace_ids_with_names, id_name_mapping=id_name_mapping
            )
        if "Associated Contact IDs" in combined_df and combined_df["Associated Contact IDs"].any():
            combined_df["Associated Contacts"] = combined_df["Associated Contact IDs"].apply(
                replace_ids_with_names, id_name_mapping=id_name_mapping
            )
        if "Associated Deal IDs" in combined_df and combined_df["Associated Deal IDs"].any():
            combined_df["Associated Deals"] = combined_df["Associated Deal IDs"].apply(
                replace_ids_with_names, id_name_mapping=id_name_mapping
            )
        if "Associated Ticket IDs" in combined_df and combined_df["Associated Ticket IDs"].any():
            combined_df["Associated Tickets"] = combined_df["Associated Ticket IDs"].apply(
                replace_ids_with_names, id_name_mapping=id_name_mapping
            )
        if "Associated Vendor IDs" in combined_df and combined_df["Associated Vendor IDs"].any():
            combined_df["Associated Vendors"] = combined_df["Associated Vendor IDs"].apply(
                replace_ids_with_names, id_name_mapping=id_name_mapping
            )

    # Export the final combined DataFrame to a new CSV file.
    # This ends up in the same directory as this file when the script is run from the repo root,
    # due to `data` being hardcoded in utils.write_csv_records().

    if output_subdir:
        output_path = f"{output_subdir}/{object_type}.csv"
    else:
        output_path = f"{object_type}.csv"
    write_csv_records(combined_df, output_path)

    return output_path


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="export.py",
        description="Export HubSpot data. Maximum 30 total exports per day, and exports with associations require 2 or 3 exports that then get combined.",
    )

    parser.add_argument(
        "type",
        choices=DATA_TYPES + ["all"],
        type=str.lower,  # accept any capitalization, but then normalize for later usage
        help="The HubSpot data type to export (or `all` to get them all).",
    )
    parser.add_argument(
        "--associations",
        action="store_true",
        help=(
            "Set to include association data (e.g., when exporting Contacts, "
            "include columns listing related Companies, Deals, etc.)."
        ),
    )
    parser.add_argument(
        "--email-bodies",
        action="store_true",
        help="Set to include body content when exporting emails. Does nothing when exporting other types.",
    )

    args = parser.parse_args(argv)

    if args.associations:
        # Generate and store mapping of object IDs to human-readable names.
        print("Caching human-readable object names.")
        id_name_mapping = get_all_object_names()

    timestamp_string = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")

    if args.type == "all":
        export_types = DATA_TYPES
    else:
        export_types = [args.type]

    for export_type in export_types:
        nicename = export_type
        dataclass: objects.DataType = getattr(objects, nicename)

        if nicename == DataTypeSlug.EMAILS and args.email_bodies:
            # Export emails to multiple JSON files in order to handle body content.
            print("Starting export of all emails with body content.")

            # Results per JSON file: page_size (100) × output_chunk_size (10) = 1,000
            if args.associations:
                associations = [
                    DataTypeSlug.CONTACTS,
                    DataTypeSlug.COMPANIES,
                    DataTypeSlug.DEALS,
                    DataTypeSlug.VENDORS,
                    DataTypeSlug.TICKETS,
                    DataTypeSlug.MEETINGS,
                ]
            else:
                associations = None

            hubspot_get_all_pages(
                hubspot.crm.objects.emails.basic_api,
                page_size=PAGE_SIZE,
                output=True,
                output_format="json",
                output_filename=f"{timestamp_string}/full_emails",
                output_chunk_size=10,
                properties=dataclass.core_props + dataclass.extra_props + dataclass.body_props,
                associations=associations,
            )

            print("Done exporting all emails with body content.")

        elif args.associations:
            print(f"Exporting all {nicename} with associations.")

            # Request multiple exports due to API limitation of 4 associations at a time.
            total_exports = len(dataclass.associations)
            export_requests = request_exports(
                dataclass.slug, dataclass.associations, total_exports, dataclass.core_props, dataclass.extra_props, nicename
            )

            # Wait for exports to complete, collect exported CSV files, and combine into one file.
            download_exports_to_csv(nicename, export_requests, total_exports, timestamp_string, True, id_name_mapping)

            print(f"Done exporting {nicename}.")

        else:
            print(f"Exporting all {nicename} without associations.")

            # Just make one simple export request.
            public_export_request = PublicExportRequest(
                export_type="VIEW",
                format="CSV",
                export_name=f"All {nicename} without associations",  # how it shows up in the HubSpot Exports UI
                object_type=dataclass.slug,
                object_properties=dataclass.core_props + dataclass.extra_props,
            )
            export_request = hubspot.crm.exports.public_exports_api.start(public_export_request)

            # Wait for export to complete and download the file.
            download_exports_to_csv(nicename, [export_request], 1, timestamp_string, False)

            print(f"Done exporting {nicename}.")

    # If running inside a GitHub Actions environment, store the file_path for later use.
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a") as env_file:
            env_file.write(f"UPLOAD_TARGET=data/{timestamp_string}\n")
            env_file.write(f"TIMESTAMP={timestamp_string}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
