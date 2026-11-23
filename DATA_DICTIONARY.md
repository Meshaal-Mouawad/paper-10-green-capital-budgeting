# Data dictionary

CSV tables have a header and use a comma delimiter. Blank selection strings denote an empty set. Multiple project identifiers in a cell are separated by semicolons. File-level outcomes and receipts use UTF-8 JSON. A row keyed by portfolio, threshold, budget fraction and mode describes one deterministic scenario. A row keyed by project, threshold and mode describes a classification without a budget dimension. Repeated conditions reuse the underlying project data.

## Projects and implementations

| Field or file | Meaning |
|---|---|
| `data/synthetic_projects.csv`, `data/negative_control_projects.csv` | One row per designed project. Main IDs begin with P, control IDs with NC. `portfolio` runs from 1 to 8, with six project positions per portfolio. Paths in this section are relative to `baseline`. |
| `scope1_kg`, `scope2_kg` | Study-defined direct and purchased-energy emissions in kg CO₂e. |
| `net_mwh`, `gross_mwh` | Net and gross energy output in MWh. `scope2_fraction` describes the share of total emissions assigned to Scope 2. |
| `intensity_true` | Policy-reference intensity, (Scope 1 + Scope 2) / net energy in kg CO₂e/MWh. A lower value is preferred. |
| `capex_musd`, `annual_cash_flow_musd`, `discount_rate`, `npv_musd` | Initial outlay and annual cash flow in USD millions, yearly discount rate expressed as a fraction, and discounted sum of five year-end cash flows less the initial outlay. |
| `mode` | `correct` applies the policy formula. `gross_denominator` substitutes gross energy. `scope2_omission` retains Scope 1 alone. `net_output_undercount` uses 0.85 times net energy. |
| `data/code_audit.csv` | One row per main source fixture. `project_id` and `mode` are the key. `source_file`, `source_line`, `source_sha256` identify the file and the LEAP declaration anchor. `leap_detected_name`, `leap_detection_kind`, `leap_formula` record native LEAP outputs. `source_anchored` records nonempty returned context. |
| `implemented_expression`, `ast_syntax_disagreement`, `test_reference_disagreement` | First whole-file return as parsed by the experiment, inequality of the expression trees and absolute numeric deviation greater than 10⁻⁷ kg CO₂e/MWh on this project's input. |
| `intensity_reported`, `error_kg_mwh` | Implemented value and implemented minus reference intensity. |

## Allocation outcomes

| Field or file | Meaning |
|---|---|
| `data/scenario_decisions.csv` | All 288 main conditions. Eight portfolios × three ceilings × three budget fractions × four modes. |
| `threshold_kg_mwh` or `threshold` | Maximum allowed emissions intensity in kg CO₂e/MWh. Values at or below the ceiling qualify. |
| `budget_fraction`, `budget_musd` | Fraction of all six candidates' total capital cost and resulting maximum spending, in USD millions. |
| `baseline_selected`, `selected`, `selection_changed` | NPV-optimal reference set, set chosen with the mode-specific eligibility labels and an indicator that the sets differ. A project can qualify and remain unfunded. |
| `baseline_npv_musd`, `selected_nominal_npv_musd`, `eligible_npv_musd` | Total reference-optimal NPV, total reported-selection NPV and NPV of the reference-qualified members in that reported selection. |
| `valid_npv_regret_musd` | Qualified NPV shortfall. It is the reference-optimal NPV minus the reference-qualified NPV retained in the selected set, bounded below by zero. |
| `ineligible_capex_musd` | Initial outlay assigned to selected projects that exceed the policy-reference ceiling. |
| `false_eligible_projects`, `false_ineligible_projects` | Counts of wrongly admitted or excluded candidates among all six projects, irrespective of selection. `baseline_project_count` and `selected_project_count` count financed projects. |
| `data/negative_control_decisions.csv` | The original 288 compact control rows contain keys and a binary `changed` flag. `outputs/finance/independent_decisions.csv` supplies the independent recomputation and selected IDs for both cohorts. |
| `results/mode_summary.csv`, `results/budget_summary.csv`, `results/threshold_summary.csv` | Main summaries with condition counts, changes, monetary sums and/or means. Mode rows have 72 decisions. Each threshold-by-mode or budget-by-mode row has 24. Sums across scenarios refer to repeated alternative allocations. |
| `results/study_results.json`, `results/negative_control_results.json` | Original machine-readable counts, settings and aggregate conclusions. |

## Extensions and independent audits

| Output | Meaning |
|---|---|
| `outputs/extensions/decision_checks.csv` | Per portfolio, threshold, budget and model. The common model varies one shared formula mode. The project-specific model allows all combinations of the attainable project labels. `ambiguous_projects` counts projects whose labels vary, `eligibility_patterns` counts possible masks, and `distinct_winners` counts distinct optimal funded sets. |
| `worst_case_checks`, `reference_path_checks`, `reference_path` | Minimum worst-case adaptive eligibility-query count, number of checks along the policy-reference path in the chosen optimal query tree, and their project IDs in order. `decision_checks_summary.json` reports sums and frequency distributions across conditions. |
| `outputs/extensions/matched_directions.csv` | Per portfolio, threshold, budget, factor family and direction. `down` divides the reference intensity by the factor and `up` multiplies it. `gross_to_net` is gross/net energy. `total_to_scope1` is total/Scope 1 emissions. `fixed_output` is 1/0.85. These reciprocal comparisons use exact nominal boundary factors. |
| `false_admitted_capex`, `shortfall` | USD millions of financed reference-ineligible capital and policy-qualified NPV shortfall in the reciprocal comparisons. `matched_directions_summary.csv` gives change counts and means over 72 conditions per factor/direction. |
| `outputs/finance/*_diff.csv` | Side-by-side checks. Fields beginning `delta_` give independent minus archived amounts. `differing_fields` lists fields outside the stated tolerance. `permitted_rounding` and `matches` apply to already-rounded aggregate cells. Empty archived selection fields in the control section of the comparison indicate that R2 stored the change flag alone. |
| `outputs/finance/decision_mechanism.csv` and `mechanism_summary.csv` | Tests of whether the reference set remains feasible and whether a newly admissible competitor outranks it. The exclusion component values lost feasible reference projects; displacement values the additional reduction in achievable reference-qualified NPV from allocating budget to false admissions. The sum equals the qualified shortfall. See `evaluate_grid()` in the independent finance audit for the subset definitions. |
| `outputs/finance/project_thresholds.csv` | Per project, ceiling and mode. Includes true and reported labels, false admission/exclusion, signed intensity error and margin certification. The strict margin test compares absolute error to absolute reference distance from the ceiling. |
| `outputs/finance/relative_and_design_checks.csv`, `project_design_summary.csv` | Relative shortfall calculations, design ranges, marginal counts, dependence among design quantities and target-range diagnostics. Exact numerator and denominator constructions are in `audit/finance_design.py`. |
| `outputs/finance/audit.json`, `posthoc_audit.json` | Machine summaries from the independent original and extension checks, including tolerance and residual counts. |
| `outputs/source/fixture_comparison.csv` | One row per fixture across both cohorts. `declaration_anchor` and `return_line` locate separate source lines. `simple_fields_match` checks filename, normalized name, declaration and anchor against the explicit-comment reader. `return_in_context` checks that the native LEAP source window includes the executable line. |
| `outputs/source/extension_outputs.json`, `extension_fixtures/` | Nine small files in eight separate reviewer-constructed software scenarios. The JSON retains record promotion, declaration, AST comparison, invoked output, policy reference, runtime errors and fixed-declaration-gate outcome. A null numeric disagreement indicates that a comparable numerical result was unavailable. Duplicate-name retention can depend on filesystem traversal order. |


## Policy geometry and mixed eligibility

The policy and assignment analyses use the original main-cohort project register. A budget share is a proportion of its own portfolio's total capital. Emissions ceilings have units kg CO₂e per MWh. All shortfalls and costs in the constructed registers use synthetic USD millions. Exact endpoints stored as strings of integers or fractions identify the rational value before decimal display.

| File | Unit of observation and purpose |
|---|---|
| `outputs/policy/policy_cells.csv` | One finite rectangle in ceiling and budget coordinates for a portfolio and altered formula. The project-score and feasible-subset-cost breakpoints define its edges. |
| `outputs/policy/policy_areas.csv`, `policy_summary.csv` | Exact and displayed fractions of each policy window with changed selection or positive qualified-value shortfall, keyed by mode and portfolio or averaged over portfolios. Areas use uniform coordinate measure. |
| `outputs/policy/mixed_decomposition.csv` | One admissible subset of ambiguous candidates for a portfolio, ceiling and budget. Tracks total, exclusion and displacement losses. |
| `outputs/policy/crosscheck.json` | Independent dynamic-programming verification of assignment contrasts, sharp endpoints and largest difference in displayed values. |
| `outputs/assignment/policy_area_crosscheck.csv`, `policy_area_verified_summary.csv` | Independent optimal-region reconstruction by portfolio/window/mode, plus summary percentages. |
| `outputs/assignment/mixed_state_crosscheck.csv.gz`, `policy_crosscheck.json` | Second implementation of the decomposition and slack test, with the all-mask count and largest discrepancy. |

## Financial reassignment and public cases

| File | Unit of observation and purpose |
|---|---|
| `outputs/assignment/condition_results.csv.gz` | One portfolio, permutation, matched perturbation factor, ceiling and budget, containing both directional allocations and their consequences. A permutation lists financial donor slots in environmental-slot order. |
| `portfolio_assignment_results.csv.gz`, `synchronized_assignment_means.csv.gz` (in `outputs/assignment`) | Results averaged over nine policy settings for each portfolio mapping and factor, or across portfolios using a common permutation. |
| `by_portfolio.csv`, `cell_summary.csv`, `within_condition_counts.csv`, `averaged_ordering.csv`, `portfolio_mean_ordering.csv` | Summaries and directional sign counts for the aggregation named in each table. Up minus down has units of synthetic USD millions. |
| `cell_extreme_witnesses.csv`, `joint_assignment_sharp_bounds.csv`, `policy_settings_sharp_bounds.csv`, `budget_weight_tipping.csv`, `common_tight_budget_witnesses.csv` | Extremal values and realizing permutations, budget-specific limits, exact critical weights on the 45% budget and a set of jointly reversing assignments. |
| `identity_comparison.csv`, `validation.json` | Reconciliation of the unpermuted register, coverage, optimization checks and input hash. |
| `field_records/source_register.csv`, `observations.csv`, `copiulemu_months.csv`, `verified_quantities.json` | Public source identifiers, dated editions, page locators and available source hashes; transcribed scalars with their original physical or monetary units; eight verified monthly components; calculated case results. The generation metric and CER record use different definitions. |

The field-record note links the primary material. The code references for continuous breakpoints and rational areas are `analysis/policy/policy_surface.py`. The allocation permutation, exact financial comparisons and weight roots are implemented in `analysis/assignment/assignment_sensitivity.py`. The two cross-check programs document their independent recurrences.
