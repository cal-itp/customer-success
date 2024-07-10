from dataclasses import dataclass
import json
from typing import Generator

from bs4 import BeautifulSoup
from slack_sdk.models.blocks import HeaderBlock, SectionBlock, MarkdownTextObject

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


def create_messages(notes: list[Note]) -> Generator[dict, None, None]:
    # see https://api.slack.com/reference/surfaces/formatting

    for note in notes:
        target_name = note.name_company or note.name_vendor
        target_type = "Transit Agency" if note.name_company else "Vendor"
        header = f"[{target_type}] {target_name}:"

        note_text = f"> {note.body}"
        created_by_text = f"*Created by:*\n{note.name_user}"
        date_fmt = f"<!date^{note.created_at}^{{date_long}} at {{time}}|{note.created_at}>"
        created_on_text = f"*Created on:*\n{date_fmt}"

        yield dict(
            channel=CHANNEL_ID,
            text=header,
            blocks=[
                HeaderBlock(text=header),
                SectionBlock(text=MarkdownTextObject(text=note_text)),
                SectionBlock(fields=[MarkdownTextObject(text=created_by_text), MarkdownTextObject(text=created_on_text)])
            ],
        )
