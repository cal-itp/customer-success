from typing import Any
import pandas as pd


def hubspot_to_df(response: Any) -> pd.DataFrame:
    """
    Helper converts a Hubspot response or list of responses like:

       `{ 'results': [ {...}, {...}, ...] }`

    into a DataFrame of records.
    """
    if not isinstance(response, list):
        response = [response]

    return pd.concat([pd.json_normalize(r.to_dict(), "results") for r in response])


def write_json_records(df: pd.DataFrame, file_path: str):
    """Helper writes the DataFrame into a JSON file."""
    df.to_json(f"data/{file_path}", orient="records", indent=2)
