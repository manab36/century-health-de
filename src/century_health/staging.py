"""Stage 1: load source files, clean them, and persist staging tables."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with lower-case snake_case column names."""
    result = frame.copy()
    result.columns = [
        re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        for column in result.columns
    ]
    return result


def ingest(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load all source formats from the source directory."""
    data_path = Path(data_dir)
    return {
        "patients": pd.read_csv(data_path / "patients.csv"),
        "symptoms": pd.read_csv(data_path / "symptoms.csv"),
        "medications": pd.read_csv(data_path / "medications.csv"),
        "encounters": pd.read_parquet(data_path / "encounters.parquet"),
        "conditions": pd.read_excel(data_path / "conditions.xlsx"),
    }


def clean_patients(frame: pd.DataFrame) -> pd.DataFrame:
    result = standardize_columns(frame)
    result["birth_date"] = pd.to_datetime(result["birthdate"], errors="coerce")
    if "deathdate" in result:
        result["death_date"] = pd.to_datetime(result["deathdate"], errors="coerce")
    for column in ["race", "ethnicity", "gender", "state"]:
        if column in result:
            result[column] = result[column].astype("string").str.strip().str.lower()
    for column in ["income", "healthcare_expenses", "healthcare_coverage", "lat", "lon"]:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.drop_duplicates("patient_id").reset_index(drop=True)


def clean_encounters(frame: pd.DataFrame) -> pd.DataFrame:
    result = standardize_columns(frame).rename(columns={"id": "encounter_id", "patient": "patient_id"})
    result["encounter_date"] = pd.to_datetime(result["start"], errors="coerce", utc=True)
    result["end_date"] = pd.to_datetime(result["stop"], errors="coerce", utc=True)
    for column in ["base_encounter_cost", "total_claim_cost", "payer_coverage"]:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.drop_duplicates("encounter_id").reset_index(drop=True)


def clean_medications(frame: pd.DataFrame) -> pd.DataFrame:
    result = standardize_columns(frame).rename(
        columns={"description": "medication_name", "totalcost": "total_cost"}
    )
    result["start_date"] = pd.to_datetime(result["start"], errors="coerce", utc=True)
    result["end_date"] = pd.to_datetime(result["stop"], errors="coerce", utc=True)
    result["total_cost"] = pd.to_numeric(result["total_cost"], errors="coerce")
    result["medication_id"] = (
        result["patient"].astype("string") + "|" + result["encounter"].astype("string")
        + "|" + result["code"].astype("string") + "|" + result["start"].astype("string")
    )
    return result.drop_duplicates("medication_id").reset_index(drop=True)


def unpack_symptoms(frame: pd.DataFrame) -> pd.DataFrame:
    """Unpack ``Rash:34;Fatigue:9`` into one row per symptom observation."""
    result = standardize_columns(frame)
    rows = result.assign(symptom_pair=result["symptoms"].str.split(";")).explode("symptom_pair")
    parsed = rows["symptom_pair"].str.extract(
        r"^(?P<symptom_name>[^:]+):(?P<symptom_value>[-+]?\d+(?:\.\d+)?)$"
    )
    rows = rows.join(parsed)
    rows["symptom_name"] = rows["symptom_name"].str.strip().str.lower().str.replace(" ", "_", regex=False)
    rows["symptom_value"] = pd.to_numeric(rows["symptom_value"], errors="coerce")
    return rows[["patient", "pathology", "symptom_name", "symptom_value"]].dropna(
        subset=["patient", "symptom_name", "symptom_value"]
    ).rename(columns={"patient": "patient_id"}).drop_duplicates().reset_index(drop=True)


def clean_conditions(frame: pd.DataFrame) -> pd.DataFrame:
    result = standardize_columns(frame).rename(columns={"patient": "patient_id", "encounter": "encounter_id"})
    return result.drop_duplicates().reset_index(drop=True)


def run_staging(data_dir: str | Path, staging_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load and clean source data, then write the stage-1 CSV artifacts."""
    sources = ingest(data_dir)
    staged = {
        "patients": clean_patients(sources["patients"]),
        "encounters": clean_encounters(sources["encounters"]),
        "medications": clean_medications(sources["medications"]),
        "observations": unpack_symptoms(sources["symptoms"]),
        "conditions": clean_conditions(sources["conditions"]),
    }
    output_path = Path(staging_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for name, frame in staged.items():
        frame.to_csv(output_path / f"{name}.csv", index=False)
    return staged