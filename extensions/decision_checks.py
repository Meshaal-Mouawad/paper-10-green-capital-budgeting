"""Exact allocation identification under two alternative models of formula uncertainty.

Usage: python decision_checks.py BASELINE_DIR OUTPUT_DIR
Inputs are frozen CSVs. Uses only Python's standard library. No study code is imported.
"""
import argparse
import csv
import itertools
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def solve_case(projects, scores, threshold, fraction):
    index = {p["id"]: i for i, p in enumerate(projects)}
    capex = [float(p["capex_musd"]) for p in projects]
    values = [float(p["npv_musd"]) for p in projects]
    budget = sum(capex) * fraction
    masks = range(1 << len(projects))
    ranking = []
    for subset in masks:
        chosen = [i for i in range(len(projects)) if subset & (1 << i)]
        capital = sum(capex[i] for i in chosen)
        if capital <= budget:
            ranking.append((-sum(values[i] for i in chosen), capital, tuple(chosen), subset))
    ranking.sort()
    winner = {world: next(s for _, _, _, s in ranking if s & world == s) for world in masks}
    reported = {mode: sum(1 << index[k] for k, v in table.items()
                          if k in index and v <= threshold) for mode, table in scores.items()}
    common = tuple(sorted(set(reported.values())))
    lower = upper = common[0]
    for mask in common:
        lower &= mask
        upper |= mask
    independent = tuple(w for w in masks if w & lower == lower and w & upper == w)
    rows = []
    for model, worlds in (("common", common), ("project_specific", independent)):
        @lru_cache(maxsize=None)
        def solve(possible):
            if len({winner[w] for w in possible}) == 1:
                return 0, None
            paths = []
            for i in range(len(projects)):
                yes = tuple(w for w in possible if w & (1 << i))
                no = tuple(w for w in possible if not w & (1 << i))
                if yes and no:
                    paths.append((1 + max(solve(yes)[0], solve(no)[0]), i))
            return min(paths)

        remaining = worlds
        reference = reported["correct"]
        queries = []
        while True:
            depth, first = solve(remaining)
            if not depth:
                assert all(winner[w] == winner[reference] for w in remaining)
                break
            bit = 1 << first
            queries.append(projects[first]["id"])
            remaining = tuple(w for w in remaining if w & bit == reference & bit)
        if model == "project_specific":
            for lo in independent:
                for hi in independent:
                    if lo & hi == lo:
                        mid = [w for w in independent if lo & w == lo and w & hi == w]
                        assert (winner[lo] == winner[hi]) == (len({winner[w] for w in mid}) == 1)
        rows.append({"portfolio":projects[0]["portfolio"], "threshold":threshold, "budget_fraction":fraction,
                     "model":model, "ambiguous_projects":(upper ^ lower).bit_count(),
                     "eligibility_patterns":len(worlds), "distinct_winners":len({winner[w] for w in worlds}),
                     "worst_case_checks":solve(worlds)[0], "reference_path_checks":len(queries),
                     "reference_path":";".join(queries)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    projects = read_csv(args.baseline / "data/synthetic_projects.csv")
    scores = defaultdict(dict)
    for row in read_csv(args.baseline / "data/code_audit.csv"):
        scores[row["mode"]][row["project_id"]] = float(row["intensity_reported"])
    rows = []
    for pid, group in itertools.groupby(sorted(projects, key=lambda p: (p["portfolio"], p["id"])), key=lambda p:p["portfolio"]):
        pool = list(group)
        for tau, f in itertools.product((380,400,420),(.45,.60,.75)):
            rows.extend(solve_case(pool, scores, tau, f))
    summary = {}
    for model in ("common","project_specific"):
        subset = [r for r in rows if r["model"] == model]
        summary[model] = {key: {"sum":sum(r[key] for r in subset), "distribution":dict(sorted(Counter(r[key] for r in subset).items()))}
                          for key in ("ambiguous_projects","eligibility_patterns","distinct_winners","worst_case_checks","reference_path_checks")}
    write_csv(args.output/"decision_checks.csv", rows)
    (args.output/"decision_checks_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
