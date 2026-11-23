#!/usr/bin/env python3
"""Replay native LEAP extraction, tag-reader comparisons and separate software challenges from a verified public baseline directory."""
import argparse
import ast
import csv
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import ModuleType
from zipfile import ZipFile
from public_inputs import ScientificInputs, SCIENCE_MANIFEST_SHA256

GIT_REVISION = "3d33a44371ff8634301b56116f838f3c03b3a8cd"
CORE = "reproducibility/leap_extract_core/"
MODULES = ["bluebook_generator/" + n for n in ("kpi_extractor.py", "parser.py", "__init__.py")]
SOURCE = "(scope1_kg + scope2_kg) / net_mwh"
SCOPE1 = "scope1_kg / net_mwh"
PARAMS = ("scope1_kg", "scope2_kg", "net_mwh", "gross_mwh")
ORDINARY = (360., 40., 10., 12.)
MODES = {"correct": SOURCE, "gross_denominator": "(scope1_kg + scope2_kg) / gross_mwh",
         "scope2_omission": SCOPE1, "net_output_undercount": "(scope1_kg + scope2_kg) / (net_mwh * 0.85)"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with open(path, "rb") as handle:
        hasher = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
        return hasher.hexdigest()


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fd:
        writer = csv.DictWriter(fd, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def csv_from(z, name):
    return list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8"))))


def provenance(z, original, repo):
    items = {}
    original_zip = ZipFile(original) if original else None
    try:
        for name in MODULES:
            data = z.read(CORE + name)
            item = {"sha256": digest(data), "bytes": len(data)}
            if original_zip:
                matching = [m for m in original_zip.namelist() if m.endswith("/" + name) and "__MACOSX/" not in m]
                if len(matching) != 1:
                    raise ValueError(f"Original member ambiguous or absent: {name}, {matching}")
                item["original_member"] = matching[0]
                item["original_bytes_equal"] = original_zip.read(matching[0]) == data
                assert item["original_bytes_equal"], name
            if repo:
                git_data = subprocess.check_output(["git", "-C", str(repo), "show", f"{GIT_REVISION}:{name}"])
                checkout_digest = file_digest(repo / name)
                item.update(git_bytes_equal=git_data == data, checkout_sha256=checkout_digest,
                            checkout_bytes_equal=checkout_digest == digest(data))
                assert item["git_bytes_equal"], name
            items[name] = item
    finally:
        if original_zip:
            original_zip.close()
    return {"modules": items, "original_archive_sha256": file_digest(original) if original else None,
            "git_tree_commit": GIT_REVISION if repo else None}


def load_extractor(z, root):
    directory = root / "modules"
    directory.mkdir()
    for name in MODULES:
        (directory / Path(name).name).write_bytes(z.read(CORE + name))
    package = ModuleType("bluebook_generator")
    package.__path__ = [str(directory)]
    sys.modules["bluebook_generator"] = package
    for variable in ("KPI_MAX_FILE_MB", "KPI_SCAN_ALL", "KPI_FORCE_FILE_FALLBACK"):
        os.environ.pop(variable, None)
    return importlib.import_module("bluebook_generator.kpi_extractor").find_kpis_in_directory


def tag_baseline(source):
    """Read explicit Python comment fields, their source line, and file name supplied by caller."""
    lines = source.splitlines()
    for index, line in enumerate(lines, start=1):
        match = re.fullmatch(r"\s*#\s*KPI\s*:\s*(.+?)\s*", line)
        if match:
            name = re.sub(r"[_\s]+", " ", match.group(1))
            break
    else:
        return None
    formula = None
    for line in lines:
        match = re.fullmatch(r"\s*#\s*Formula\s*:\s*(.+?)\s*", line)
        if match:
            formula = match.group(1)
            break
    return {"name": name, "file_line": index, "formula": formula}


def declared_disagreement(formula, expression):
    if formula is None or expression is None:
        return None
    formula_ast = ast.parse(formula, mode="eval").body
    return ast.dump(formula_ast) != ast.dump(expression)


def inspect_source(text, args):
    tree = ast.parse(text)
    first_return = next((node for node in ast.walk(tree) if isinstance(node, ast.Return)), None)
    namespace = {"__builtins__": {}}
    exec(compile(tree, "<pinned or reviewer fixture>", "exec"), namespace)
    try:
        observed, run_error = namespace["calculate_intensity"](*args), None
    except (ArithmeticError, KeyError) as exc:
        observed, run_error = None, type(exc).__name__
    try:
        reference, reference_error = (args[0] + args[1]) / args[2], None
    except ArithmeticError as exc:
        reference, reference_error = None, type(exc).__name__
    mismatch = None if observed is None or reference is None else abs(observed - reference) > 1e-7
    return (first_return, observed, reference, run_error, reference_error, mismatch)


def check_frozen(z, root, scan):
    audit = {r["source_file"]: r for r in csv_from(z, "data/code_audit.csv")}
    rows = []
    summary = {}
    for label, dirname, table in [("main", "finance_kpi_sources", "synthetic_projects"),
                                  ("control", "negative_control_kpi_sources", "negative_control_projects")]:
        register = {r["id"]: r for r in csv_from(z, "data/" + table + ".csv")}
        folder = root / dirname
        folder.mkdir()
        members = [n for n in z.namelist() if n.startswith(f"study/{dirname}/") and n.endswith(".py")]
        assert len(members) == 192 and len(register) == 48
        for n in members:
            (folder / Path(n).name).write_bytes(z.read(n))
        records, stats = scan(str(folder), include_stats=True)
        by_file = {Path(r["file_path"]).name: r for r in records}
        assert len(by_file) == len(records) == len(members)
        start = len(rows)
        for path in sorted(folder.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            record, tags = by_file[path.name], tag_baseline(text)
            portfolio, position, mode = path.stem.split("_", 2)
            project = portfolio + "_" + position
            args = tuple(float(register[project][k]) for k in PARAMS)
            ret, observed, ref, error, ref_error, num_flag = inspect_source(text, args)
            assert error is ref_error is None and ret is not None
            assert abs(ref - float(register[project]["intensity_true"])) < 1e-9
            assert not declared_disagreement(MODES[mode], ret.value)
            syntax = declared_disagreement(record["formula"], ret.value)
            baseline_syntax = declared_disagreement(tags["formula"], ret.value)
            fields_equal = all(tags[key] == record[key] for key in tags)
            code_return = text.splitlines()[ret.lineno - 1].strip()
            context_contains_return = any(code_return == line.strip() for line in record["code_context"].splitlines())
            assert fields_equal and syntax == baseline_syntax == num_flag == (mode != "correct")
            assert context_contains_return and record["detection_kind"] == "comment"
            source_hash = file_digest(path)
            if label == "main":
                ledger = audit[path.name]
                assert (ledger["source_sha256"] == source_hash and int(ledger["source_line"]) == tags["file_line"] and
                        ledger["leap_detected_name"] == tags["name"] and ledger["leap_formula"] == tags["formula"] and
                        ledger["leap_detection_kind"] == record["detection_kind"] and ledger["source_anchored"] == "True" and
                        ledger["implemented_expression"] == ast.unparse(ret.value) and
                        int(ledger["ast_syntax_disagreement"]) == syntax and int(ledger["test_reference_disagreement"]) == num_flag and
                        float(ledger["intensity_reported"]) == observed and float(ledger["intensity_true"]) == ref and
                        float(ledger["error_kg_mwh"]) == observed - ref)
            rows.append(dict(cohort=label, file=path.name, project=project, mode=mode, sha256=source_hash,
                             declaration_anchor=record["file_line"], return_line=ret.lineno,
                             detection=record["detection_kind"], name=record["name"], declaration=record["formula"],
                             return_expression=ast.unparse(ret.value), simple_fields_match=fields_equal,
                             return_in_context=context_contains_return, leap_input_ast_mismatch=syntax,
                             simple_input_ast_mismatch=baseline_syntax, numeric_mismatch=num_flag,
                             executed_output=observed, reference_output=ref, main_ledger_checked=label == "main"))
        batch = rows[start:]
        summary[label] = dict(files=len(batch), leap_records=len(records), tag_records=len(batch),
                              matched_name_formula_line_and_file=sum(r["simple_fields_match"] for r in batch),
                              ast_flags=sum(r["leap_input_ast_mismatch"] for r in batch),
                              baseline_ast_flags=sum(r["simple_input_ast_mismatch"] for r in batch),
                              numeric_flags=sum(r["numeric_mismatch"] for r in batch),
                              returned_context_includes_execution_line=sum(r["return_in_context"] for r in batch),
                              distinct_return_expressions=len(set(r["return_expression"] for r in batch)),
                              distinct_declarations=len(set(r["declaration"] for r in batch)), scan_stats=stats)
    return rows, summary


def challenge_specs():
    def function(expression):
        return "def calculate_intensity(" + ", ".join(PARAMS) + "):\n    return " + expression + "\n"

    def header(name="Green Financing Emissions Intensity", formula=SOURCE):
        return f"# KPI: {name}\n# Formula: {formula}\n"

    return [
        ("equivalent_reordering", {"calc.py": header() + function("(scope2_kg + scope1_kg) / net_mwh")}, ORDINARY),
        ("stale_declaration", {"calc.py": header(formula=SCOPE1) + function(SCOPE1)}, ORDINARY),
        ("earlier_misleading_comment", {"calc.py": "# Superseded Formula: " + SCOPE1 + "\n" + header() + function(SOURCE)}, ORDINARY),
        ("zero_net_energy", {"calc.py": header() + function(SOURCE)}, (360., 40., 0., 12.)),
        ("unannotated_same_function", {"calc.py": function(SOURCE)}, ORDINARY),
        ("duplicate_names", {"a.py": header() + function(SOURCE), "b.py": header() + function(SCOPE1)}, ORDINARY),
        ("omission_masked_at_zero_scope2", {"calc.py": header() + function(SCOPE1)}, (360., 0., 10., 12.)),
        ("unrelated_return_first", {"calc.py": header() + "def helper(scope1_kg, scope2_kg, net_mwh):\n    return " +
                                     SOURCE + "\n" + function(SCOPE1)}, ORDINARY),
    ]


def run_challenges(root, out, scan):
    challenge_dir = out / "extension_fixtures"
    challenge_dir.mkdir(exist_ok=True)
    results = []
    for case, files, args in challenge_specs():
        scratch = root / case
        scratch.mkdir()
        saved = challenge_dir / case
        saved.mkdir(exist_ok=True)
        for name, content in files.items():
            (scratch / name).write_text(content, encoding="utf-8")
            (saved / name).write_text(content, encoding="utf-8")
        records, stats = scan(str(scratch), include_stats=True)
        records_by_file = {Path(r["file_path"]).name: r for r in records}
        for name, content in files.items():
            record = records_by_file.get(name)
            ret, observed, ref, error, ref_error, numeric = inspect_source(content, args)
            tagged = tag_baseline(content)
            formula = record.get("formula") if record else None
            results.append(dict(case=case, file=name, case_files=len(files), case_records=len(records),
                                scanned_count=stats["files_scanned"], filtered_candidates=stats["filtered_non_kpi_candidates"],
                                record_name=record["name"] if record else None,
                                record_kind=record["detection_kind"] if record else None,
                                leap_anchor=record["file_line"] if record else None,
                                declaration=formula, simple_declaration=tagged["formula"] if tagged else None,
                                fixed_declaration_gate_passes=bool(record and formula == SOURCE),
                                first_ast_return=ast.unparse(ret.value), first_ast_return_line=ret.lineno,
                                ast_mismatch=declared_disagreement(formula, ret.value),
                                controlled_inputs=dict(zip(PARAMS, args)), observed=observed, policy_reference=ref,
                                execution_error=error, reference_error=ref_error, numeric_mismatch=numeric))
    single = {r["case"]: r for r in results if r["case_files"] == 1}
    # Duplicate-name winners can depend on filesystem scan order.
    duplicates = [r for r in results if r["case"] == "duplicate_names"]
    assert sum(r["record_name"] is not None for r in duplicates) == 1
    assert all(r["case_records"] == 1 for r in duplicates)
    assert single["zero_net_energy"]["execution_error"] == single["zero_net_energy"]["reference_error"] == "ZeroDivisionError"
    assert single["unannotated_same_function"]["record_kind"] == "logic_fallback"
    assert single["unannotated_same_function"]["declaration"] is None
    expected_flags = {
        "equivalent_reordering": (True, False), "stale_declaration": (False, True),
        "earlier_misleading_comment": (True, False), "zero_net_energy": (False, None),
        "unannotated_same_function": (None, False), "omission_masked_at_zero_scope2": (True, False),
        "unrelated_return_first": (False, True),
    }
    for key, expected in expected_flags.items():
        result = single[key]
        assert (result["ast_mismatch"], result["numeric_mismatch"]) == expected, key
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("baseline", type=Path)
    cli.add_argument("--out", type=Path, default=Path("source_audit_replay"))
    cli.add_argument("--original-source", type=Path)
    cli.add_argument("--git-workspace", type=Path)
    options = cli.parse_args()
    out = options.out
    out.mkdir(parents=True, exist_ok=True)
    with ScientificInputs(options.baseline) as baseline, tempfile.TemporaryDirectory() as temp:
        names = baseline.namelist()
        manifest = dict((n, h) for h, n in (line.split("  ", 1) for line in
                        baseline.read("SHA256SUMS.txt").decode().splitlines() if line.strip()))
        assert len(names) == len(set(names)) and set(names) - {"SHA256SUMS.txt"} == set(manifest)
        assert all(digest(baseline.read(n)) == h for n, h in manifest.items())
        receipt = provenance(baseline, options.original_source, options.git_workspace)
        root = Path(temp)
        scan = load_extractor(baseline, root)
        rows, cohorts = check_frozen(baseline, root, scan)
        cases = run_challenges(root, out, scan)
    write_csv(out / "fixture_comparison.csv", rows)
    write_json(out / "extension_outputs.json", cases)
    receipt.update(baseline_manifest_sha256=SCIENCE_MANIFEST_SHA256, all_manifest_members_verified=len(manifest), cohorts=cohorts,
                   challenge_scenarios=len(set(c["case"] for c in cases)), challenge_files=len(cases))
    write_json(out / "source_receipt.json", receipt)
    print(f"Verified {len(manifest)} public baseline entries, {len(rows)} fixture rows and {len(cases)} challenge files.")


if __name__ == "__main__":
    main()
