"""Stage 2: transform persisted staging tables and persist the master table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .staging import clean_conditions, clean_encounters, clean_medications, clean_patients, unpack_symptoms


def read_staging(staging_dir: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(staging_dir)
    names = ["patients", "encounters", "medications", "observations", "conditions"]
    return {name: pd.read_csv(path / f"{name}.csv") for name in names}


def build_master_table(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build one row per encounter, aggregating one-to-many enrichments first."""
    if "observations" in sources:
        patients = sources["patients"]
        encounters = sources["encounters"]
        medications = sources["medications"]
        conditions = sources["conditions"]
        observations = sources["observations"]
    else:
        patients = clean_patients(sources["patients"])
        encounters = clean_encounters(sources["encounters"])
        medications = clean_medications(sources["medications"])
        conditions = clean_conditions(sources["conditions"])
        observations = unpack_symptoms(sources["symptoms"])

    condition_summary = conditions.groupby("encounter_id", as_index=False).agg(
        condition_codes=("code", lambda values: "|".join(sorted(set(values.dropna().astype(str))))),
        condition_count=("code", "nunique"),
    )
    medication_summary = medications.groupby("patient", as_index=False).agg(
        medication_names=("medication_name", lambda values: "|".join(sorted(set(values.astype(str))))),
        medication_count=("medication_id", "nunique"),
        medication_cost=("total_cost", "sum"),
    ).rename(columns={"patient": "patient_id"})
    symptom_summary = observations.groupby("patient_id", as_index=False).agg(
        symptom_score_mean=("symptom_value", "mean"),
        symptom_observation_count=("symptom_value", "count"),
    )

    master = encounters.merge(
        patients[["patient_id", "birth_date", "race", "ethnicity", "gender", "state", "income"]],
        on="patient_id", how="left", validate="many_to_one",
    )
    master = master.merge(condition_summary, on="encounter_id", how="left", validate="many_to_one")
    master = master.merge(medication_summary, on="patient_id", how="left", validate="many_to_one")
    return master.merge(symptom_summary, on="patient_id", how="left", validate="many_to_one")


def run_transform(staging_dir: str | Path) -> pd.DataFrame:
    """Read stage-1 artifacts, transform them, and write master back to staging."""
    master = build_master_table(read_staging(staging_dir))
    master.to_csv(Path(staging_dir) / "master.csv", index=False)
    return master