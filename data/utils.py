import pandas as pd


def write_json_records(df: pd.DataFrame, file_path: str):
    """Helper writes the DataFrame into a JSON file."""
    df.to_json(f"data/{file_path}", orient="records", indent=2)
