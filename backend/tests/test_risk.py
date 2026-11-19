import pytest

from app.risk import assess_asthma_risk, categorize_aqi


@pytest.mark.parametrize(
    "aqi, number, name",
    [
        (0, 1, "Good"),
        (50, 1, "Good"),
        (51, 2, "Moderate"),
        (100, 2, "Moderate"),
        (101, 3, "Unhealthy for Sensitive Groups"),
        (151, 4, "Unhealthy"),
        (201, 5, "Very Unhealthy"),
        (301, 6, "Hazardous"),
        (999, 6, "Hazardous"),
    ],
)
def test_categorize_aqi_boundaries(aqi, number, name):
    assert categorize_aqi(aqi) == (number, name)


def test_worst_pollutant_drives_risk():
    result = assess_asthma_risk(
        [{"aqi": 30, "pollutant": "O3"}, {"aqi": 160, "pollutant": "PM2.5"}]
    )
    assert result["aqi"] == 160
    assert result["dominant_pollutant"] == "PM2.5"
    assert result["risk_level"] == "high"


def test_every_category_has_a_risk_level():
    levels = {assess_asthma_risk([{"aqi": aqi, "pollutant": "PM2.5"}])["risk_level"] for aqi in (10, 75, 125, 175, 250, 400)}
    assert levels == {"low", "moderate", "high", "very_high", "severe"}
