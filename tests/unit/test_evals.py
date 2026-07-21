"""
Runs the deterministic governance eval harness as part of the unit suite, so a
local `pytest` and CI both fail if any governance guarantee regresses.

The harness itself lives in evals/ (data-driven scenarios + runner); this is a
thin wrapper that executes it in-process and asserts a clean exit.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "aegis_evals_runner", ROOT / "evals" / "run_evals.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_governance_evals_all_pass(capsys):
    runner = _load_runner()
    rc = runner.main(["run_evals.py"])  # no scenario arg → default evals/scenarios.yaml
    out = capsys.readouterr().out
    assert rc == 0, f"governance eval scenarios failed:\n{out}"
