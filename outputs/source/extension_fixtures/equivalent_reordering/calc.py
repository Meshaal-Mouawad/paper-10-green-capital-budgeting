# KPI: Green Financing Emissions Intensity
# Formula: (scope1_kg + scope2_kg) / net_mwh
def calculate_intensity(scope1_kg, scope2_kg, net_mwh, gross_mwh):
    return (scope2_kg + scope1_kg) / net_mwh
