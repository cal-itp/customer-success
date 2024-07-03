from pathlib import Path
from typing import Any

import pandas as pd


def hubspot_get_all_pages(hubspot_api, page_size=10, **kwargs) -> list:
    """Repeatedly call the `get_page` method of the given Hubspot API until all responses are received.

    Extra kwargs are passed through to the `get_page` method.
    """
    kwargs["limit"] = page_size
    pages = []

    response = hubspot_api.get_page(**kwargs)
    pages.append(response)

    while response.paging:
        kwargs["after"] = response.paging.next.after
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

    # create a list of DataFrames by normalizing results from each response
    dfs = [pd.json_normalize(r.to_dict(), "results") for r in response]

    # concatenate all the DataFrames together into one
    # ignore index since it doesn't carry any information (essentially, row number)
    return pd.concat(dfs, ignore_index=True)


def write_json_records(df: pd.DataFrame, file_path: str):
    """Writes a DataFrame of records into a JSON file."""
    path = f"data/{file_path}"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path, orient="records", indent=2)
