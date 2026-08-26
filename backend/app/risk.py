RISK_BY_CATEGORY = {
    1: ("low", "Air quality is good. No asthma-related precautions needed."),
    2: ("low", "Air quality is moderate. Unusually sensitive individuals may notice mild symptoms."),
    3: ("moderate", "Sensitive groups, including people with asthma, should limit prolonged outdoor exertion."),
    4: ("high", "Air quality is unhealthy. People with asthma should avoid prolonged outdoor exertion."),
    5: ("very_high", "Air quality is very unhealthy. People with asthma should avoid outdoor activity."),
    6: ("severe", "Air quality is hazardous. Everyone, especially people with asthma, should stay indoors."),
}


def assess_asthma_risk(observations):
    worst = max(observations, key=lambda obs: obs["AQI"])
    category_number = worst["Category"]["Number"]
    risk_level, message = RISK_BY_CATEGORY[category_number]

    return {
        "aqi": worst["AQI"],
        "category_name": worst["Category"]["Name"],
        "category_number": category_number,
        "dominant_pollutant": worst["ParameterName"],
        "risk_level": risk_level,
        "message": message,
    }
