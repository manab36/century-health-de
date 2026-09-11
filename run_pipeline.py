import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from century_health.load_final import run_load_final
from century_health.staging import run_staging
from century_health.transform import run_transform

LOGGER = logging.getLogger("century_health.pipeline")
STAGES = ("staging", "transform", "load_final")


def run_pipeline(
    data_dir: str | Path = "Data",
    staging_dir: str | Path = "staging",
    final_dir: str | Path = "outputs",
    retry_stage: str | None = None,
    retries: int = 1,
) -> None:
    """Run all stages, or retry one named stage, with bounded retries."""
    if retry_stage is not None and retry_stage not in STAGES:
        raise ValueError(f"Unknown stage {retry_stage!r}; choose from {', '.join(STAGES)}")
    start_at = STAGES.index(retry_stage) if retry_stage else 0
    for stage in STAGES[start_at:]:
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            try:
                LOGGER.info("Starting %s (attempt %d/%d)", stage, attempt, attempts)
                if stage == "staging":
                    run_staging(data_dir, staging_dir)
                elif stage == "transform":
                    run_transform(staging_dir)
                else:
                    run_load_final(staging_dir, final_dir)
                LOGGER.info("Completed %s", stage)
                break
            except Exception:
                LOGGER.exception("Stage %s failed on attempt %d/%d", stage, attempt, attempts)
                if attempt == attempts:
                    raise RuntimeError(
                        f"Pipeline stopped at {stage}. Re-run with --retry-stage {stage}"
                    ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the three-stage Century Health pipeline.")
    parser.add_argument("--data-dir", default="Data")
    parser.add_argument("--staging-dir", default="staging")
    parser.add_argument("--final-dir", default="outputs")
    parser.add_argument("--retry-stage", choices=STAGES)
    parser.add_argument("--retries", type=int, default=1, help="Extra attempts per stage.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_pipeline(args.data_dir, args.staging_dir, args.final_dir, args.retry_stage, args.retries)


if __name__ == "__main__":
    main()