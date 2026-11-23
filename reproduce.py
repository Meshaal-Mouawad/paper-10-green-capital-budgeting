#!/usr/bin/env python3
"""Regenerate the original study, reproduce all independent checks, and draw the figures."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def files_under(folder):
    return sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def check_distribution():
    for line in (ROOT / "SHA256SUMS.txt").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Distribution checksum mismatch: {relative}")


def execute(script, args, output_root, env, name):
    cmd = [sys.executable, str(script), *map(str, args)]
    result = subprocess.run(cmd, cwd=output_root, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{name} failed with status {result.returncode}.\n{result.stdout}\n{result.stderr}")
    print(name, flush=True)


def close_fields(left, right):
    if left == right:
        return True
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(close_fields(v, right[k]) for k, v in left.items())
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(close_fields(a, b) for a, b in zip(left, right))
    try:
        a, b = Decimal(str(left)), Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False
    return a.is_finite() and b.is_finite() and abs(a - b) <= Decimal("1e-7")


def check_duplicate_scenario(data):
    # The scanner retains whichever of two identically named declarations it encounters first.
    # Validate retained context and syntax against the retained function, then normalize the
    # filesystem-dependent winner across platforms for the reference-output comparison.
    duplicates = [row for row in data if row["case"] == "duplicate_names"]
    retained = [row for row in duplicates if row["record_name"] is not None]
    assert len(duplicates) == 2 and len(retained) == 1
    assert retained[0]["ast_mismatch"] == retained[0]["numeric_mismatch"]
    assert all(r["case_records"] == 1 for r in duplicates)
    for row in duplicates:
        for key in ("record_name", "record_kind", "leap_anchor", "declaration", "fixed_declaration_gate_passes", "ast_mismatch"):
            row.pop(key)


def compare_file(expected, observed):
    if not observed.is_file():
        raise FileNotFoundError(observed.name)
    if expected.read_bytes() == observed.read_bytes():
        return "byte_identical"
    if expected.suffixes[-2:] == [".csv", ".gz"]:
        with gzip.open(expected, "rb") as left, gzip.open(observed, "rb") as right:
            if left.read() == right.read():
                return "field_agreement"
        raise ValueError(f"Decompressed CSV differs: {expected.name}")
    if expected.suffix == ".csv":
        def read(p):
            with p.open(newline="", encoding="utf-8") as stream:
                return list(csv.reader(stream))
    elif expected.suffix == ".json":
        def read(p):
            data = json.loads(p.read_text(encoding="utf-8"))
            if p.name == "extension_outputs.json":
                check_duplicate_scenario(data)
            return data
    else:
        raise ValueError(f"Byte comparison failed: {expected.name}")
    if not close_fields(read(expected), read(observed)):
        raise ValueError(f"Field comparison failed: {expected.name}")
    return "field_agreement"


def compare_group(expected_root, actual_root, relative_files):
    return {str(p): compare_file(expected_root/p, actual_root/p) for p in sorted(relative_files)}


def clean_pdf_bytes(path):
    data = path.read_bytes()
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-256:]:
        raise ValueError(f"Incomplete PDF: {path.name}")
    return re.sub(rb"/CreationDate\s*\([^)]*\)", b"/CreationDate()", data)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, default=ROOT / "reproduced")
    cli.add_argument("--without-figures", action="store_true", help="Use only Python's standard library.")
    cli.add_argument("--verify-only", action="store_true", help="Verify distribution SHA-256 entries and exit.")
    options = cli.parse_args()
    check_distribution()
    if options.verify_only:
        print("Distribution checksums match.")
        return
    if sys.version_info < (3, 11):
        cli.error("A full financial audit requires Python 3.11 or later.")
    out = options.output.resolve()
    if out.exists() and any(out.iterdir()):
        cli.error("Choose an empty output directory.")
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=str(out/"matplotlib_cache"))
    for key in ("PYTHONPATH", "KPI_SCAN_ALL", "KPI_MAX_FILE_MB", "KPI_FORCE_FILE_FALLBACK"):
        env.pop(key, None)
    frozen = ROOT / "baseline"
    regen = out / "regenerated_baseline"
    shutil.copytree(frozen, regen)
    # Remove prior generated outputs so every checked figure, table and fixture is freshly produced.
    for sub in ("data", "results", "figures", "study/finance_kpi_sources", "study/negative_control_kpi_sources"):
        shutil.rmtree(regen/sub)
    run = lambda script, args, name: execute(script, args, out, env, name)
    for name in ("run_study", "run_boundary_controls", "verify_study"):
        run(regen/"study"/(name+".py"), [], "Original study: " + name)
    base_tables = [p.relative_to(frozen) for sub in ("data","results","study/finance_kpi_sources","study/negative_control_kpi_sources")
                   for p in files_under(frozen/sub)]
    comparison = {"original_science": compare_group(frozen, regen, base_tables)}
    extensions = out / "extensions"
    for name in ("decision_checks", "matched_direction"):
        run(ROOT/"extensions"/(name+".py"), [frozen, extensions], "Article extension: " + name)
    finance = out / "finance"
    source = out / "source"
    run(ROOT/"audit/independent_finance.py", [frozen, "--output", finance], "Independent finance audit")
    run(ROOT/"audit/independent_extensions.py", ["--lead-directory", extensions, "--output", finance], "Independent extension audit")
    run(ROOT/"audit/finance_design.py", ["--output", finance], "Finance design and relative-value checks")
    run(ROOT/"audit/replay_source_audit.py", [frozen, "--out", source], "Independent source extraction and software challenges")
    for name, folder in (("finance",finance),("source",source),("extensions",extensions)):
        expected_root = ROOT/"outputs"/name
        inputs = [p.relative_to(expected_root) for p in files_under(expected_root)]
        comparison[name] = compare_group(expected_root, folder, inputs)
    policy = out / "policy"
    assignment = out / "assignment"
    run(ROOT/"analysis/policy/policy_surface.py", [frozen, policy], "Policy geometry and mixed eligibility")
    run(ROOT/"analysis/assignment/assignment_sensitivity.py", [ROOT, "--output", assignment],
        "Financial bundle reassignments and budget-weight bounds")
    run(ROOT/"analysis/policy/crosscheck_assignments.py", [frozen, assignment, "--receipt", policy/"crosscheck.json"],
        "Independent reassignment dynamic program")
    run(ROOT/"analysis/assignment/crosscheck_policy.py", [ROOT, policy, "--output", assignment],
        "Independent policy-area and mixed-mask checks")
    for name, folder in (("policy", policy), ("assignment", assignment)):
        expected_root = ROOT/"outputs"/name
        comparison[name] = compare_group(expected_root, folder, [p.relative_to(expected_root) for p in files_under(expected_root)])
    field = out / "field_records"
    run(ROOT/"field_records/replay.py", ["--output", field/"verified_quantities.json"],
        "Public field-record arithmetic")
    comparison["field_records"] = compare_group(ROOT/"field_records", field, [Path("verified_quantities.json")])
    figure_status = {}
    if not options.without_figures:
        import matplotlib
        run(regen/"study/create_figures.py", [], "Original figures")
        run(ROOT/"extensions/draw_figures.py", [frozen, out/"figures"], "Article figures")
        run(ROOT/"analysis/policy/draw_policy_map.py", [policy/"policy_cells.csv", out/"figures/policy_geometry.pdf"],
            "Article policy geometry figure")
        for name, expected, actual in [("original",frozen/"figures",regen/"figures"),
                                       ("article",ROOT/"figures",out/"figures")]:
            for p in sorted(expected.iterdir()):
                new = actual / p.name
                if p.suffix == ".pdf":
                    equal = clean_pdf_bytes(p) == clean_pdf_bytes(new)
                else:
                    if not new.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError(f"Missing or incomplete PNG: {p.name}")
                    equal = p.read_bytes() == new.read_bytes()
                figure_group = "supplement" if p.name == "shortfall_sensitivity.pdf" else name
                figure_status[figure_group+"/"+p.name] = {"rebuilt": True,"same_rendering_bytes_excluding_pdf_creation_date": equal}
        plotting = matplotlib.__version__
    else:
        plotting = None
    checks = {group:{"files":len(entries),"byte_identical":sum(v=="byte_identical" for v in entries.values()),
                     "field_agreement":sum(v=="field_agreement" for v in entries.values())} for group,entries in comparison.items()}
    receipt = {"status":"passed", "python":sys.version.split()[0], "matplotlib":plotting,
               "baseline_manifest_sha256":hashlib.sha256((frozen/"SHA256SUMS.txt").read_bytes()).hexdigest(),
               "checked_output_groups":checks, "figures":figure_status,
               "finance_audit":json.loads((finance/"audit.json").read_text()),
               "extension_audit":{k:v for k,v in json.loads((finance/"posthoc_audit.json").read_text()).items() if isinstance(v,int)},
               "source_cohorts":{key:{k:v for k,v in row.items() if k != "scan_stats"} for key,row in json.loads((source/"source_receipt.json").read_text())["cohorts"].items()},
               "assignment_audit":json.loads((assignment/"validation.json").read_text()),
               "assignment_countercheck":json.loads((policy/"crosscheck.json").read_text()),
               "policy_and_mixed_mask_audit":json.loads((assignment/"policy_crosscheck.json").read_text()),
               "field_comparison_absolute_tolerance":1e-7}
    (out/"run_confirmation.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    (out/"file_comparison.json").write_text(json.dumps(comparison,indent=2)+"\n",encoding="utf-8")
    print("Passed. See run_confirmation.json in the output directory.")


if __name__ == "__main__":
    main()
