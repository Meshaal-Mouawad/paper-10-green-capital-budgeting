# Supplement S1 — Carbon-intensity screens and capital rationing

This release contains the complete generated data, executable KPI fixtures, original calculation and allocation drivers, study extensions, independent allocation algorithms, and publicly documented case records for the article. The source inputs and financial values describe a deliberately constructed, finite design. The main and distance-control cohorts each contain 48 projects in eight portfolios, 192 Python fixtures and 288 allocation conditions. All materials required to perform the scientific checks are in this folder.

## Run the study

Extract the ZIP, enter the `Supplement_S1` folder and use Python 3.11 or newer. The numerical, source and finance checks use the standard library. Rebuilding the two article figures and the original figures also requires Matplotlib and NumPy. The complete release replay used Python 3.12.7 and Matplotlib 3.11.2 and NumPy 2.5.5.

```sh
python3 reproduce.py --verify-only
python3 reproduce.py --output reproduced
```

For a standard-library-only run, use a fresh output directory.

```sh
python3 reproduce.py --without-figures --output reproduced_numbers
```

The run verifies the distribution manifest, rebuilds the original study in a separate directory, regenerates the article extensions and independently checks allocation choices, values, formula records and software challenges against the shipped outputs. The files `run_confirmation.json` and `file_comparison.json` in the output directory record which files reproduced byte for byte and which matched field by field. Numerical files are compared at absolute tolerance 10⁻⁷ when bytes differ. Calculations with rounded published summaries also receive a separate check at their stated reporting precision. The article's figures can be regenerated with a different Matplotlib version. The receipt records any differences in generated graphics.

## Contents

| Location | What it contains |
|---|---|
| `baseline/data` and `baseline/results` | Original project registers, main audit ledger, main and control allocation rows, sensitivity summaries and scan statistics. See [data dictionary](DATA_DICTIONARY.md). |
| `baseline/study` | Original generator, fixture writer, main simulation, boundary-control driver, internal verifier, original figure script, and all 384 original Python fixtures. |
| `baseline/reproducibility` | Byte-preserved LEAP extractor and formula parser, plus the archived package initializer. The driver imports the extraction module without starting the Bluebook application. |
| `baseline/figures` | The two original summary figures, each supplied as PDF and PNG. |
| `extensions` and `outputs/extensions` | Exact reciprocity sensitivity, adaptive eligibility-check computation, article plotting code and the specified extension data. |
| `audit` and `outputs/finance` | Independent exact-rational financial model and subset rankings, full side-by-side comparisons, feasibility and shortfall decomposition, audit of extensions, and design diagnostics. |
| `outputs/source` | Per-fixture source replay, outcomes from the simple declaration reader, the eight separate software challenges and their nine small source files. |
| `analysis/policy` and `outputs/policy` | Exact area computations for continuous emissions ceilings and budgets, the mixed eligibility decomposition and the independent dynamic-programming check of the assignment results. |
| `analysis/assignment` and `outputs/assignment` | Within-portfolio financial reassignment, sharp bounds and witnesses, plus an independent reconstruction of the policy geometry and mixed-mask identities. |
| `field_records` | Public sources and replayable arithmetic for the Vasilikos appraisal and Copiulemu verification record. |
| `figures` | Article figures `project_example.pdf` and `policy_geometry.pdf`, plus the earlier supplementary graphic `shortfall_sensitivity.pdf`. |
| `source_provenance.json`, `baseline/SHA256SUMS.txt`, `SHA256SUMS.txt` | Original archive and Git identities, original scientific-member hashes, and checksums of the distributed files. |
| `clean_run_confirmation.json` | A recorded clean replay of the complete supplement. |

## Scientific inputs and direct commands

For an exact replay of the two historical PDFs and the decoded pixels of both historical PNGs, use a Python environment with Matplotlib 3.10.8 and run `python3 audit/check_historical_figures.py baseline --output historical_figure_replay`. The script retains the originals’ build timestamp for PDF comparison. [Historical graphics replay](historical_figure_confirmation.json)

The original generator equations, including all portfolio/within-portfolio offsets, Scope 2 shares, gross-to-net factors, capital costs, annual cash flows and discount rates, are specified in `baseline/study/run_study.py`, `generate_projects()`. That file's `FORMULA` and `RETURN_EXPR` constants give the four source expressions. Its `choose_portfolio()` and `main()` functions define the eligibility test, budget and reporting quantities. The distance-control substitutions appear in `baseline/study/run_boundary_controls.py`, `main()`. The second finance implementation writes the same design independently with exact fractions in `audit/independent_finance.py`, `records()` and `intensities()`.

The following commands can be run directly against the supplied inputs in addition to the complete replay above.

```sh
python3 extensions/decision_checks.py baseline my_extensions
python3 extensions/matched_direction.py baseline my_extensions
python3 audit/independent_finance.py baseline --output my_finance
python3 audit/independent_extensions.py --lead-directory my_extensions --output my_finance
python3 audit/finance_design.py --output my_finance
python3 audit/replay_source_audit.py baseline --out my_source
python3 extensions/draw_figures.py baseline my_figures
python3 analysis/policy/policy_surface.py baseline my_policy
python3 analysis/assignment/assignment_sensitivity.py . --output my_assignments
python3 analysis/policy/crosscheck_assignments.py baseline my_assignments --receipt my_policy/crosscheck.json
python3 analysis/assignment/crosscheck_policy.py . my_policy --output my_assignments
python3 analysis/policy/draw_policy_map.py my_policy/policy_cells.csv my_figures/policy_geometry.pdf
python3 field_records/replay.py
```

## Source and version identity

The 405 scientific members in `baseline` are byte-identical to their entries in the original R2 research package. The original research package has SHA-256 `480ca11087e384ca8801ddbf2c6cdaf102c71dd510c1b38ca0970867e936a9d0`. The extractor, parser and initializer were also directly compared with the original LEAP archive and Git tree `3d33a44371ff8634301b56116f838f3c03b3a8cd`. Their per-file provenance is in [the source receipt](source_provenance.json). The public independent audit scripts take the hash-verified `baseline` directory as input. This packaging change replaces their previous ZIP I/O, input hash and receipt field. The comparator, fixture, financial and optimization algorithms retain their original implementations.

The main R2 driver calls each fixture, records its value, extracts the source declaration and evidence, and compares a return expression against the declaration. The eligibility rule uses the executed value. The original control driver uses the four explicit mode formulas and scans all control fixtures. The independent source audit separately executes each control fixture. In both cohorts, one clean and three fault expressions repeat across 48 inputs. The tag-reader comparison covers the filename, normalized name, declared expression and declaration line on those annotated files. The reviewer-created challenge examples are separate from all project and allocation counts.


The reassignment program reads the original project register and the reciprocal direction ledger inside this distribution. Its receipt hashes the project register when invoked on the extracted folder. The earlier invocation hashed the complete previous supplement ZIP (`ad9e35bce48472c568ef6b9685f0de00be4c40e21bd7018623b534ae6d5c5edc`). All assignment results use the same underlying register. The complete replay tests all four new numerical programs against their tables and checks the public case arithmetic against its reference output. CSV files compressed with gzip compare exactly after decompression if local compression bytes vary.

## Current manuscript — Wiley BSE R26

- [R26 manuscript](manuscript/BSE/R26/Paper_10_BSE_R26.pdf)
- [R26 LaTeX source](manuscript/BSE/R26/source)
- [R26 validation](manuscript/BSE/R26/Validation.md)
- [Research state](RESEARCH_STATE.yaml)
- [Published Harvard Dataverse replication data](https://doi.org/10.7910/DVN/ZSXX0E)

The original research data and historical manuscript versions are preserved.
