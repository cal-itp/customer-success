from pathlib import Path
from typing import Any

import pandas as pd


def hubspot_to_df(response: Any) -> pd.DataFrame:
    """Helper converts a Hubspot response with `{ 'results': [ {...}, {...}, ...] }` into a DataFrame of records."""
    return pd.json_normalize(response.to_dict(), "results")


def write_json_records(df: pd.DataFrame, file_path: str):
    """Writes a DataFrame of records into a JSON file."""
    path = f"data/{file_path}"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path, orient="records", indent=2)
