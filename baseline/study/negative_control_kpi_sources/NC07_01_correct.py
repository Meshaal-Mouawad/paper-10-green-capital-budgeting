# KPI: Synthetic Green Financing Emissions Intensity NC07_01 correct
# Description: Source-traceable emissions intensity for investment screening.
# Objective: Test a study-defined eligibility rule for SDG-linked capital allocation.
# Formula: (scope1_kg + scope2_kg) / net_mwh
# Unit: kgCO2e/MWh
# Data Source: deterministic synthetic project register; Scope 1 and Scope 2.
# Accountable Owner: Scenario Researcher
# Input: scope1_kg, scope2_kg, net_mwh, gross_mwh.
def calculate_intensity(scope1_kg, scope2_kg, net_mwh, gross_mwh):
    return (scope1_kg + scope2_kg) / net_mwh
