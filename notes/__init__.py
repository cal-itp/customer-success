import logging
from pathlib import Path
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(name)s): %(message)s")

NOTES_PATH = Path("data/notes.json")
