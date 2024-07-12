from dataclasses import dataclass
import json
import os
import time
from typing import Generator

from bs4 import BeautifulSoup
from slack_sdk.models.blocks import HeaderBlock, SectionBlock, MarkdownTextObject
from slack_sdk.web import WebClient
from slack_sdk.web.slack_response import SlackResponse

from notes import NOTES_PATH


ACCESS_TOKEN = os.environ["SLACK_ACCESS_TOKEN"]
CHANNEL = os.environ["SLACK_CHANNEL_ID"]
HUBSPOT_INSTANCE = os.environ["HUBSPOT_INSTANCE_ID"]
RATE_LIMIT = float(os.environ.get("SLACK_RATE_LIMIT", 1.0))

# Hubspot magic numbers
COMPANIES = "0-2"
VENDORS = "2-22517187"

slack = WebClient(token=ACCESS_TOKEN)


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
        # add the markdown blockquote
        note.body = "> " + note.body
        # max body size 3000 characters
        if len(note.body) > 3000:
            # take the first 2995 characters, plus 3 for the ellipsis, plus 2 for the markdown blockquote and space
            # 2995 + 3 + 2 = 3000
            note.body = note.body[0:2995] + "..."
        # convert from Unix timestamp milliseconds to Unix timestamp seconds for Slack's date formatting
        note.created_at = int(int(note.created_at) / 1000)

    return notes


def create_messages(notes: list[Note]) -> Generator[dict, None, None]:
    # see https://api.slack.com/reference/surfaces/formatting

    for note in notes:
        if note.name_company:
            target_name, target_id, target_type, type_id = (note.name_company, note.id_company, "Transit Agency", COMPANIES)
        else:
            target_name, target_id, target_type, type_id = (note.name_vendor, note.id_vendor, "Vendor", VENDORS)

        note_id = note.id_note
        url = f"https://app.hubspot.com/contacts/{HUBSPOT_INSTANCE}/record/{type_id}/{target_id}/view/1?engagement={note_id}"

        header_text = f"[{target_type}] {target_name}:"
        created_by_text = f"*Created by:*\n{note.name_user}"
        date_fmt = f"<!date^{note.created_at}^{{date_long}} at {{time}}|{note.created_at}>"
        created_on_text = f"*Created on:*\n{date_fmt}"
        link_text = f"<{url}|View in Hubspot>"

        yield dict(
            channel=CHANNEL,
            text=header_text,
            blocks=[
                HeaderBlock(text=header_text),
                SectionBlock(text=MarkdownTextObject(text=note.body)),
                SectionBlock(fields=[MarkdownTextObject(text=created_by_text), MarkdownTextObject(text=created_on_text)]),
                SectionBlock(text=MarkdownTextObject(text=link_text)),
            ],
        )


def post_messages(messages: Generator[dict, None, None]) -> Generator[SlackResponse, None, None]:
    for message in messages:
        response = slack.chat_postMessage(**message)
        yield response
        time.sleep(RATE_LIMIT)


if __name__ == "__main__":
    notes = read_notes_json()

    notes = process_notes(notes)

    messages = create_messages(notes)

    responses = post_messages(messages)

    for response in responses:
        assert response.status_code == 200
