import os
import sys

# make the repo root importable, so tests can do "from etl... import ..."
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)