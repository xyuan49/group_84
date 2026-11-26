from datetime import datetime, timedelta

import pytest

from app.alerts import Reading, bp_alerts, glucose_alerts, hba1c_alerts, sort_alerts
from app.models import GlucoseReading, Observation

T0 = datetime(2026, 10, 25, 8, 0)


def at(hours: float) -> datetime:
    return T0 + timedelta(hours=hours)


def rules(alerts):
    return {a.rule for a in alerts}


def in_range(n=10, value=120):
    return [Reading(value, at(i * 6)) for i in range(n)]


# --- glucose rules -----------------------------------------------------------


def test_steady_readings_give_only_time_in_range():
    alerts = glucose_alerts(in_range(), 7)
    assert rules(alerts) == {"in_range"}
    assert alerts[0].title == "Time in range: 100%"


@pytest.mark.parametrize("value, expected", [(70, set()), (69, {"low"}), (54, {"low"}), (53, {"low", "very_low"})])
def test_low_thresholds(value, expected):
    alerts = glucose_alerts([Reading(value, T0)], 7)
    assert rules(alerts) == expected


def test_very_low_is_urgent_emergency_and_says_it_is_simulated():
    alert = next(a for a in glucose_alerts([Reading(48, T0)], 7) if a.rule == "very_low")
    assert alert.severity == "urgent"
    assert alert.emergency
    assert alert.title == "Very low glucose: 48 mg/dL"
    assert "contacts no one" in alert.detail


def test_consecutive_cgm_lows_count_as_one_episode():
    readings = [Reading(65, at(i * 0.25)) for i in range(4)]  # 08:00-08:45, every 15 min
    readings.append(Reading(62, at(30)))  # next day, 14:00
    low = next(a for a in glucose_alerts(readings, 7) if a.rule == "low")
    assert low.title == "2 low readings (< 70 mg/dL) in 7 days"


def test_low_says_when_lows_happen():
    readings = [Reading(65, at(h)) for h in (24 * d + 5 for d in range(3))]  # 13:00 each day
    low = next(a for a in glucose_alerts(readings, 7) if a.rule == "low")
    assert low.detail == "Mostly in the afternoon."


def test_high_needs_more_than_a_quarter_above_180():
    quarter = in_range(6) + [Reading(200, at(100 + i)) for i in range(2)]  # 2 of 8 = 25%
    assert "high" not in rules(glucose_alerts(quarter + in_range(2), 7))  # 2 of 10 = 20%

    many = in_range(6) + [Reading(200, at(100 + i)) for i in range(4)]  # 4 of 10 = 40%
    high = next(a for a in glucose_alerts(many, 7) if a.rule == "high")
    assert high.title == "40% of readings above 180 mg/dL"


def test_percent_rules_need_ten_readings():
    alerts = glucose_alerts([Reading(250, at(i)) for i in range(9)], 7)
    assert rules(alerts) == set()


def test_fasting_above_target_on_most_days():
    readings = [Reading(150, at(24 * d), "fasting") for d in range(3)]
    readings.append(Reading(110, at(24 * 3), "fasting"))
    readings.append(Reading(160, at(24 * 3 + 3), "after_meal"))  # not fasting: ignored
    fasting = next(a for a in glucose_alerts(readings, 7) if a.rule == "fasting")
    assert fasting.title == "Fasting above 130 on 3 of 4 days"


def test_fasting_on_half_the_days_is_not_an_alert():
    readings = [Reading(150, at(0), "fasting"), Reading(110, at(24), "fasting")]
    assert "fasting" not in rules(glucose_alerts(readings, 7))


def test_no_readings_no_alerts():
    assert glucose_alerts([], 7) == []


# --- HbA1c and blood pressure -------------------------------------------------


def test_hba1c_above_goal_and_improving():
    alerts = hba1c_alerts([(datetime(2026, 5, 1), 8.0), (datetime(2026, 8, 12), 7.6)])
    assert {(a.rule, a.title) for a in alerts} == {
        ("hba1c", "HbA1c 7.6% is above the 7% goal"),
        ("hba1c_change", "HbA1c improved 0.4 points"),
    }


def test_hba1c_at_goal_with_small_change():
    assert hba1c_alerts([(datetime(2026, 5, 1), 6.9), (datetime(2026, 8, 12), 6.8)]) == []


def test_hba1c_rise_is_reported():
    alerts = hba1c_alerts([(datetime(2026, 5, 1), 6.2), (datetime(2026, 8, 12), 6.6)])
    assert [a.title for a in alerts] == ["HbA1c rose 0.4 points"]


@pytest.mark.parametrize("sys_value, dia_value, fires", [
    (129, 79, False), (130, 70, True), (120, 80, True), (134, 84, True),
])
def test_bp_goal(sys_value, dia_value, fires):
    alerts = bp_alerts((datetime(2026, 9, 30), sys_value), (datetime(2026, 9, 30), dia_value))
    assert bool(alerts) == fires


def test_bp_needs_both_values():
    assert bp_alerts((datetime(2026, 9, 30), 150), None) == []


def test_sort_puts_urgent_first():
    alerts = glucose_alerts(in_range(9) + [Reading(50, at(100))], 7)
    assert [a.severity for a in sort_alerts(alerts)] == ["urgent", "warning", "info"]


# --- endpoint ----------------------------------------------------------------


@pytest.fixture
def record(db_session, patients):
    latest = datetime(2026, 11, 1, 20, 0)
    rows = [GlucoseReading(patient_id="p-1", value_mg_dl=120, measured_at=latest - timedelta(hours=6 * i),
                           source="cgm") for i in range(12)]
    rows += [
        GlucoseReading(patient_id="p-1", value_mg_dl=50, measured_at=latest - timedelta(days=2), source="cgm"),
        # older than the 7-day window: ignored
        GlucoseReading(patient_id="p-1", value_mg_dl=40, measured_at=latest - timedelta(days=10), source="cgm"),
        Observation(patient_id="p-1", loinc_code="4548-4", display="HbA1c", value=7.6, unit="%",
                    effective_at=datetime(2026, 8, 12)),
        Observation(patient_id="p-1", loinc_code="8480-6", display="Systolic", value=118, unit="mm[Hg]",
                    effective_at=datetime(2025, 1, 1)),
        Observation(patient_id="p-1", loinc_code="8462-4", display="Diastolic", value=76, unit="mm[Hg]",
                    effective_at=datetime(2025, 1, 1)),
        Observation(patient_id="p-1", loinc_code="8480-6", display="Systolic", value=134, unit="mm[Hg]",
                    effective_at=datetime(2026, 9, 30)),
        Observation(patient_id="p-1", loinc_code="8462-4", display="Diastolic", value=84, unit="mm[Hg]",
                    effective_at=datetime(2026, 9, 30)),
    ]
    db_session.add_all(rows)
    db_session.commit()


def test_alerts_endpoint(client, record):
    r = client.get("/api/patients/p-1/alerts")

    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7
    assert body["window_end"] == "2026-11-01T20:00:00"
    alerts = body["alerts"]
    assert [a["rule"] for a in alerts] == ["very_low", "low", "hba1c", "bp", "in_range"]
    assert alerts[0]["title"] == "Very low glucose: 50 mg/dL"  # the 40 is outside the window
    assert alerts[0]["emergency"] is True
    assert alerts[3]["title"] == "Blood pressure 134/84 is above the 130/80 goal"


def test_alerts_window_is_configurable(client, record):
    alerts = client.get("/api/patients/p-1/alerts", params={"days": 14}).json()["alerts"]
    assert alerts[0]["title"] == "Very low glucose: 40 mg/dL"


def test_alerts_for_patient_without_data(client, patients):
    body = client.get("/api/patients/p-2/alerts").json()
    assert body == {"days": 7, "window_start": None, "window_end": None, "alerts": []}


def test_alerts_unknown_patient(client, patients):
    assert client.get("/api/patients/nobody/alerts").status_code == 404
