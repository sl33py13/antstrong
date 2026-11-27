"""Time the full pipeline on a synthetic dataset.

Usage (from the project folder):
    python -m tools.make_benchmark_data bench-data      # creates 652,000 fake records
    python -m tools.benchmark bench-data
"""
import shutil
import sys
import tempfile
import time

from agent.analytics import compute_kpis
from agent.ingest import process_drop_folder


def main(drop_dir: str) -> None:
    for run in range(3):
        vault = tempfile.mkdtemp(prefix="antstrong-bench-")
        t0 = time.perf_counter()
        payload = process_drop_folder(drop_dir, vault)
        t1 = time.perf_counter()
        compute_kpis(payload)
        t2 = time.perf_counter()
        shutil.rmtree(vault, ignore_errors=True)
        records = sum(len(v) for v in payload.values())
        print(f"run {run + 1}: {records:,} records, ingest+privacy gate {t1 - t0:.2f}s, analytics {t2 - t1:.2f}s, total {t2 - t0:.2f}s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bench-data")
