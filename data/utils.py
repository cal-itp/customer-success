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


def hubspot_get_all_pages(hubspot_api, page_size=10, max_pages=sys.maxsize, **kwargs) -> list:
    """Repeatedly call the `get_page` method of the given Hubspot API until all responses are received.

    Extra kwargs are passed through to the `get_page` method.
    """
    kwargs["limit"] = page_size
    pages = []

    response = hubspot_api.get_page(**kwargs)
    pages.append(response)

    while getattr_or_get(response, "paging") and len(pages) < max_pages:
        kwargs["after"] = getattr_or_get(getattr_or_get(getattr_or_get(response, "paging"), "next"), "after")
        response = hubspot_api.get_page(**kwargs)
        pages.append(response)

    return pages


def hubspot_to_df(response: Any) -> pd.DataFrame:
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


class HubspotUserApi:
    url = "https://api.hubapi.com/crm/v3/objects/users"

    def __init__(self, access_token: str):
        self.headers = {"accept": "application/json", "authorization": f"Bearer {access_token}"}

    def get_page(self, properties: list[str] = [], **kwargs):
        kwargs["properties"] = ",".join(properties)
        response = requests.request("GET", self.url, headers=self.headers, params=kwargs)
        return response.json()
