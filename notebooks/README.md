# Notebooks

This directory contains ad-hoc Jupyter Notebooks used for exploring or transforming Hubspot data via the Hubspot API.

## `notes.ipynb`

This was an early exploration of the [Hubspot notes syncing process](../notes/README.md), which has since been refactored into
standalone scripts.

The notebook may not be up to date with the scripts.

## `vendor_activities.ipynb`

This notebook was used for a one-time conversion of activity data (emails, meetings, phone calls, etc.) from the (older)
`company` object to the (newer) `vendor` object.

The `company` object comes built-in to Hubspot and acts as a container for related contacts. Companies are used to represent
Transit Agencies and other organizations that Cal-ITP interacts with. Previously, companies were also used to represent transit
technology and service vendors.

Later, Cal-ITP Customer Success created the custom object type `vendor` to be able to track engagement with this subset of
companies more accurately within Hubspot.

This notebook was used to migrate historic activity data from the `company` objects to the corresponding `vendor` objects.
