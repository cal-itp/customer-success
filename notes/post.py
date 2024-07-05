from dataclasses import dataclass
import json

from notes.download import NOTES_PATH


@dataclass()
class Note:
    body: str
    created_at: int
    id_note: str
    id_user: str
    name_user: str
    id_company: str = None
    name_company: str = None
    id_vendor: str = None
    name_vendor: str = None


def read_notes_json() -> list[Note]:
    if not NOTES_PATH.exists():
        raise FileNotFoundError(NOTES_PATH)

    notes_data = json.loads(NOTES_PATH.read_text())

    return [Note(**note) for note in notes_data]
