"""Backward-compatible imports for the modular pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .load_final import run_load_final
from .staging import (
    clean_conditions, clean_encounters, clean_medications, clean_patients,
    ingest, standardize_columns, unpack_symptoms, run_staging,
)
from .transform import build_master_table, read_staging, run_transform


def run_pipeline(data_dir: str | Path, output_dir: str | Path = "outputs") -> dict[str, pd.DataFrame]:
    """Run all stages using a sibling ``staging`` directory."""
    staging_dir = Path(output_dir).parent / "staging"
    run_staging(data_dir, staging_dir)
    run_transform(staging_dir)
    return run_load_final(staging_dir, output_dir)