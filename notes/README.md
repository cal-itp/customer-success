# Hubspot notes

The code in this directory defines a process that syncs notes from Hubspot associated with Transit Agencies and Vendors into
Cal-ITP Slack for wider visibility.

Notes are synced into the [`#notify-hubspot-notes`](https://cal-itp.slack.com/archives/C07C3ADGJ4S) channel.

The process is run every hour with a [GitHub Actions workflow](../.github/workflows/notes-sync.yml).

A GitHub [repository variable](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables) is used to maintain the `last_note_id` (the ID of the most recently processed note) between successive runs of the workflow.

## `download.py`

This script is responsible for downloading the latest notes using the Hubspot API:

1. Parse `last_note_id`
   - Initially, `last_note_id` will be empty
2. Get all notes since `last_note_id` <https://developers.hubspot.com/docs/api/crm/notes>
   - Use `after` parameter with value of `last_note_id` in API call
   - Include `associations` for: `companies` and `vendors`
   - Page through multiple pages, increase `limit` for page size
   - Save new `last_note_id` using the `paging.next.after` property from the last API response
3. For each note in the API response list:
   - If it has no body, skip
   - If it has no author/creator, skip
   - If it has no associations, skip
   - If it has a `company` association: check if `company_type == Transit Agency`; if not, skip
4. If the note is not being skipped:
   - Get the user's first name associated to `properties.hs_created_by` (the user's ID)
   - Get a company's name from the associated company ID
   - Get a vendor's name from the associated vendor ID
   - Add an item to the output list
5. Write the output list to a JSON file

## `post.py`

This script is responsible for posting each downloaded note into Slack using the Slack API:

1. Read the output list from the file
2. For each note in the output list:
   - Process the HTML from the note body into something usable
   - Generate a Slack message using the note attributes <https://api.slack.com/reference/surfaces/formatting#rich-layouts>
   - Post the message to the channel <https://api.slack.com/messaging/sending>
