# Desk to Hubspot Conversion

A Jupyter Notebook that converts exported Teamwork Desk data into a format for
import into Hubspot.

## Getting started

1. Clone the repository

```bash
git clone https://github.com/cal-itp/crm-helpdesk
```

1. Download the [Desk export data from Drive](https://drive.google.com/drive/folders/10QsUGgBR8SfjeVzZUQqEYyn1pFgI6J4t)

1. Place the files in the repository directory [`desk-to-hubspot/data/desk`](desk-to-hubspot/data/desk/)

1. (Recommended) `Rebuild and Reopen` the devcontainer for this repository

1. (Alternate) Install dependencies from `requirements.txt` in your preferred Python environment.

1. Open the [notebook](desk-to-hubspot/convert.ipynb) and run all cells

1. Look for CSV output in [`desk-to-hubspot/data/hubspot`](/desk-to-hubspot/data/hubspot/)
