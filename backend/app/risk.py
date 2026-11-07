# (upper AQI bound, category name) per US EPA AQI category, numbered from 1.
AQI_CATEGORIES = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
    (float("inf"), "Hazardous"),
]

RISK_BY_CATEGORY = {
    1: ("low", "Air quality is good. No asthma-related precautions needed."),
    2: ("low", "Air quality is moderate. Unusually sensitive individuals may notice mild symptoms."),
    3: ("moderate", "Sensitive groups, including people with asthma, should limit prolonged outdoor exertion."),
    4: ("high", "Air quality is unhealthy. People with asthma should avoid prolonged outdoor exertion."),
    5: ("very_high", "Air quality is very unhealthy. People with asthma should avoid outdoor activity."),
    6: ("severe", "Air quality is hazardous. Everyone, especially people with asthma, should stay indoors."),
}


def categorize_aqi(aqi):
    for number, (upper_bound, name) in enumerate(AQI_CATEGORIES, start=1):
        if aqi <= upper_bound:
            return number, name


def assess_asthma_risk(observations):
    worst = max(observations, key=lambda obs: obs["aqi"])
    category_number, category_name = categorize_aqi(worst["aqi"])
    risk_level, message = RISK_BY_CATEGORY[category_number]

    return {
        "aqi": worst["aqi"],
        "category_name": category_name,
        "category_number": category_number,
        "dominant_pollutant": worst["pollutant"],
        "risk_level": risk_level,
        "message": message,
    }
