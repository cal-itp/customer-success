from dataclasses import dataclass
import json

from bs4 import BeautifulSoup

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


def process_notes(notes: list[Note]) -> list[Note]:
    for note in notes:
        # collapse all text from the HTML body, joining distinct elements with a space
        # strip extra whitespace, and place inner newlines within a blockquote
        note.body = BeautifulSoup(note.body, "html.parser").get_text(" ").strip().replace("\n", ">\n")
        # convert from Unix timestamp milliseconds to Unix timestamp seconds for Slack's date formatting
        note.created_at = int(int(note.created_at) / 1000)

    return notes
