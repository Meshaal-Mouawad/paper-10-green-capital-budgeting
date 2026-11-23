"""Reconcile the transcribed public records. Uses only Python's standard library."""
import argparse
import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATA = Path(__file__).resolve().parent


def read_table(name):
    with (DATA / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def whole(value):
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def reconcile():
    inputs = {r["variable"]: Decimal(r["value"]) for r in read_table("observations.csv")}
    eib = {fuel: {standard: int(inputs[fuel] - inputs[standard])
                  for standard in ("earlier_standard", "later_standard")}
           for fuel in ("gas_estimate", "distillate_estimate")}
    if inputs["approved_maximum"] != inputs["signed"]:
        raise ValueError("Approved cap and recorded loan signature differ.")
    md = read_table("copiulemu_months.csv")
    months = {}
    for row in md:
        corrected = (Decimal(row["mdproject_tco2e"]) - Decimal(row["mdreg_tco2e"])
                     - Decimal(row["electricity_tco2e"]))
        if whole(corrected) != int(row["verified_v3_tco2e"]):
            raise ValueError("Published rounded quantity differs in " + row["month"])
        months[row["month"]] = str(corrected)
    period = inputs["mdproject_total"] - inputs["mdreg_total"] - inputs["electricity_total"]
    monthly_sum = sum(int(row["verified_v3_tco2e"]) for row in md)
    if not (monthly_sum == whole(period) == inputs["verified_v3_total"]):
        raise ValueError("Published monthly and total quantities differ.")
    return {"vasilikos_estimate_minus_standard_g_co2_per_kwh": eib,
            "vasilikos_approved_maximum_and_signed_eur": int(inputs["signed"]),
            "copiulemu_verified_monthly_tco2e_from_displayed_components": months,
            "copiulemu_verified_period_tco2e_from_displayed_total_components": str(period),
            "copiulemu_verified_period_rounded_tco2e": whole(period),
            "copiulemu_sum_of_whole_monthly_tco2e": monthly_sum,
            "copiulemu_v3_minus_v2_tco2e": int(inputs["verified_v3_total"] - inputs["verified_v2_total"]),
            "copiulemu_v3_minus_initial_tco2e": int(inputs["verified_v3_total"] - inputs["reported_total"]),
            "copiulemu_request_cers": int(inputs["requested"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write JSON to a file. Default: print to stdout.")
    destination = parser.parse_args().output
    rendered = json.dumps(reconcile(), indent=2, ensure_ascii=False) + "\n"
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
