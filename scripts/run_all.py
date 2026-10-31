"""Run the full pipeline end to end: download -> extract -> build -> validate."""

from __future__ import annotations

import download
import extract
import build_datasets
import validate


def main() -> None:
    download.main()
    extract.main()
    build_datasets.main()
    validate.main()


if __name__ == "__main__":
    main()
