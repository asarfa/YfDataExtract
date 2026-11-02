"""`yfdx-app` entry point: starts the Streamlit interface."""

import sys
from pathlib import Path


def main() -> None:
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__).with_name("app.py")), *sys.argv[1:]]
    raise SystemExit(stcli.main())
