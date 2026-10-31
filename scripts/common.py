"""Shared constants and helpers for the TSE 2026 presidential election pipeline."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EXTRACTED_DIR = RAW_DIR / "extracted"
PROCESSED_DIR = ROOT / "data" / "processed"

# TSE placeholder values that mean "missing" in the open-data CSVs.
TSE_NULL_STRINGS = {"#NULO#", "#NE#"}
TSE_NULL_INTS = {-1, -3}

# Semicolon-separated, Latin-1 encoded, quoted fields.
TSE_CSV_KWARGS = dict(
    sep=";", encoding="latin1", quotechar='"', dtype=str, low_memory=False
)

PRESIDENTE_CARGO_CODE = 1
PRESIDENTE_CARGO_NAME = "PRESIDENTE"


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def to_nullable_int(series):
    """Convert a TSE numeric-string column to pandas nullable Int64, mapping
    placeholder codes (-1, -3) and blanks to <NA>."""
    import pandas as pd

    s = series.astype(str).str.strip()
    s = s.where(~s.isin({"", "nan", "None"}), other=pd.NA)
    num = pd.to_numeric(s, errors="coerce").astype("Int64")
    num = num.mask(num.isin(list(TSE_NULL_INTS)))
    return num


def clean_string_nulls(series):
    """Map TSE string placeholders (#NULO#, #NE#) to <NA>."""
    import pandas as pd

    s = series.astype(str).str.strip()
    return s.where(~s.isin(TSE_NULL_STRINGS | {""}), other=pd.NA)
