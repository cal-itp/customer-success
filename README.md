# Desk to Hubspot conversion

This repo contains a Jupyter Notebook that converts exported Teamwork Desk data
into a format for import into Hubspot.

## Getting started

1. Clone the repository

```bash
git clone https://github.com/cal-itp/desk-to-hubspot
```

1. Download the [Desk export data from Drive](https://drive.google.com/drive/folders/10QsUGgBR8SfjeVzZUQqEYyn1pFgI6J4t), place the files in the repository directory `/data/desk`

1. (Recommended) `Rebuild and Reopen` the devcontainer for this repository

1. (Alternate) Install dependencies from `requirements.txt` in your preferred Python environment.

1. Open the [notebook](transform.ipynb) and run all cells to produce output in `/data/hubspot`
