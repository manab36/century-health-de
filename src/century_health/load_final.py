"""Stage 3: publish staged tables as final CSV outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def run_load_final(staging_dir: str | Path, final_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Read the staged tables, including the transformed master, into final CSVs."""
    staging_path = Path(staging_dir)
    final_path = Path(final_dir)
    final_path.mkdir(parents=True, exist_ok=True)
    names = ["patients", "encounters", "medications", "observations", "conditions", "master"]
    final_tables = {name: pd.read_csv(staging_path / f"{name}.csv") for name in names}
    for name, frame in final_tables.items():
        frame.to_csv(final_path / f"{name}.csv", index=False)
    return final_tables