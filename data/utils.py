from pathlib import Path

import pandas as pd


def write_json_records(df: pd.DataFrame, file_path: str):
    """Writes a DataFrame of records into a JSON file."""
    path = f"data/{file_path}"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path, orient="records", indent=2)
