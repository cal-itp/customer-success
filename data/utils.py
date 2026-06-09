from pathlib import Path
import sys
from typing import Any, Generator

import pandas as pd
import requests


def chunk_list(input_list: list, chunk_size: int) -> Generator[list, None, None]:
    """Yield successive sublists of max size chunk_size from the input list."""
    for i in range(0, len(input_list), chunk_size):
        yield input_list[i : i + chunk_size]


def getattr_or_get(obj, attr):
    """Try `getattr(obj, attr)`, falling back to `obj.get(attr)`."""
    try:
        return getattr(obj, attr)
    except AttributeError:
        return obj.get(attr)


def hubspot_get_all_pages(
    hubspot_api,
    page_size=10,
    max_pages=sys.maxsize,
    output=False,
    output_format="",
    output_filename=None,
    output_chunk_size=None,
    **kwargs,
) -> list:
    """Repeatedly call the `get_page` method of the given Hubspot API until all responses are received.

    Results can be sent directly to a CSV or JSON file by setting `output` to True and `output_format` to "csv" or "json".
    `output_filename` should not include the extension; that will be added based on `output_format`.
    If no `output_filename` is given, it will default to the string value of `hubspot_api`.
    If the total results are expected to be too large for a single file, they can be chunked into multiple files
    by setting `output_chunk_size` to the number of pages you want to save into each file.
    For example, if there are 20,000 records, you can get 20 files of 1,000 records each
    by setting `page_size` to 100 (which is the max HubSpot allows) and `output_chunk_size` to 10.

    Extra kwargs are passed through to the `get_page` method.
    """
    kwargs["limit"] = page_size
    pages = []

    if output:
        # Set up some things for later use
        filename = output_filename or str(hubspot_api)
        match output_format:
            case "csv":
                output_method = write_csv_records
            case "json":
                output_method = write_json_records
        counter = 1

    response = hubspot_api.get_page(**kwargs)
    pages.append(response)

    while getattr_or_get(response, "paging") and len(pages) < max_pages:
        kwargs["after"] = getattr_or_get(getattr_or_get(getattr_or_get(response, "paging"), "next"), "after")
        response = hubspot_api.get_page(**kwargs)
        pages.append(response)

        if output and output_chunk_size and (len(pages) == output_chunk_size or getattr_or_get(response, "paging") is None):
            # If we're outputting in chunks
            #   - and we've landed on the page number matching output_chunk size
            #   - or we're on the last page (the current response's "paging" value is None)

            # Output this chunk with the current counter appended to the filename
            output_method(hubspot_to_df(pages), f"{filename}_{counter}.{output_format}")

            # Reset pages and increment the counter for the next chunk
            pages = []
            counter += 1

    if output and not output_chunk_size:
        # If we're outputting but not in chunks, output the complete pages list
        output_method(hubspot_to_df(pages), f"{filename}.{output_format}")

    return pages


def hubspot_to_df(response: Any) -> pd.DataFrame | None:
    """
    Converts a Hubspot response like:

        ```
        { "results": [ {...}, {...}, ...] }
        ```

    or list of responses like:

        ```
        [
            { "results": [ {...}, {...}, ...] },
            { "results": [ {...}, {...}, ...] },
            ...
        ]
        ```

    into a single DataFrame of records.
    """
    # assume a list input
    if not isinstance(response, list):
        response = [response]

    try:
        dicts = [r.to_dict() for r in response]
    except AttributeError:
        dicts = [r for r in response]

    # create a list of DataFrames by normalizing results from each response
    dfs = [pd.json_normalize(d, "results") for d in dicts]

    if len(dfs) == 1:
        return dfs[0]
    if len(dfs) > 1:
        # concatenate all the DataFrames together into one
        # ignore index since it doesn't carry any information (essentially, row number)
        return pd.concat(dfs, ignore_index=True)
    else:
        return None


def write_json_records(df: pd.DataFrame, file_path: str):
    """Writes a DataFrame of records into a JSON file."""
    path = f"data/{file_path}"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path, orient="records", indent=2)


def write_csv_records(df: pd.DataFrame, file_path: str):
    """Writes a DataFrame of records into a CSV file."""
    path = f"data/{file_path}"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)


class HubspotUserApi:
    url = "https://api.hubapi.com/crm/v3/objects/users"

    def __init__(self, access_token: str):
        self.headers = {"accept": "application/json", "authorization": f"Bearer {access_token}"}

    def get_page(self, properties: list[str] = [], **kwargs):
        kwargs["properties"] = ",".join(properties)
        response = requests.request("GET", self.url, headers=self.headers, params=kwargs)
        return response.json()
