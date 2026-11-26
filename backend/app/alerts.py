"""Rule-based alerts for one patient.

Thresholds follow the ADA Standards of Care in Diabetes (glycemic targets,
CGM metrics, hypertension):

| Rule      | Fires when                                                         | Severity |
|-----------|--------------------------------------------------------------------|----------|
| very_low  | any glucose < 54 mg/dL (level 2 hypoglycemia)                      | urgent   |
| low       | any glucose < 70 mg/dL (level 1)                                   | warning  |
| high      | > 25% of readings above 180 mg/dL (needs 10+ readings)             | warning  |
| fasting   | fasting glucose above 130 mg/dL on more than half of fasting days  | warning  |
| hba1c     | latest HbA1c >= 7%                                                 | warning  |
| bp        | latest blood pressure >= 130/80 mm Hg                              | warning  |
| in_range  | share of readings 70-180 mg/dL (needs 10+ readings)                | info     |
| hba1c_change | latest HbA1c moved 0.3 points or more from the one before       | info     |

GlucoTrack is a student project, not a medical device. The very_low alert
only shows what a real app would do (prompt to call emergency services); it
contacts no one.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

LOW = 70
VERY_LOW = 54
HIGH = 180
FASTING_HIGH = 130
HBA1C_GOAL = 7.0
HBA1C_CHANGE = 0.3
SYSTOLIC_GOAL = 130
DIASTOLIC_GOAL = 80
MAX_TIME_ABOVE_RANGE = 0.25
MIN_READINGS_FOR_PERCENT = 10
EPISODE_GAP = timedelta(minutes=30)  # CGM lows closer than this are one episode

SEVERITY_ORDER = {"urgent": 0, "warning": 1, "info": 2}


@dataclass
class Reading:
    value: float
    at: datetime
    meal_context: str | None = None


@dataclass
class Alert:
    rule: str
    severity: str  # urgent / warning / info
    title: str
    detail: str
    emergency: bool = False


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def part_of_day(at: datetime) -> str:
    if 5 <= at.hour < 12:
        return "morning"
    if 12 <= at.hour < 17:
        return "afternoon"
    if 17 <= at.hour < 22:
        return "evening"
    return "night"


def episodes(readings: list[Reading]) -> list[list[Reading]]:
    """Group time-sorted readings into runs with gaps of at most EPISODE_GAP."""
    groups: list[list[Reading]] = []
    for r in readings:
        if groups and r.at - groups[-1][-1].at <= EPISODE_GAP:
            groups[-1].append(r)
        else:
            groups.append([r])
    return groups


def glucose_alerts(readings: list[Reading], days: int) -> list[Alert]:
    readings = sorted(readings, key=lambda r: r.at)
    alerts = []

    very_low = [r for r in readings if r.value < VERY_LOW]
    if very_low:
        lowest = min(very_low, key=lambda r: r.value)
        alerts.append(Alert(
            "very_low", "urgent",
            f"Very low glucose: {lowest.value:g} mg/dL",
            f"Below {VERY_LOW} mg/dL on {lowest.at:%b %d at %H:%M}. In a real app GlucoTrack would prompt the "
            "patient to treat the low and offer to call emergency services. This demo contacts no one.",
            emergency=True,
        ))

    lows = episodes([r for r in readings if r.value < LOW])
    if lows:
        when = Counter(part_of_day(e[0].at) for e in lows).most_common(1)[0][0]
        alerts.append(Alert(
            "low", "warning",
            f"{plural(len(lows), 'low reading')} (< {LOW} mg/dL) in {days} days",
            f"Mostly in the {when}.",
        ))

    if len(readings) >= MIN_READINGS_FOR_PERCENT:
        above = sum(r.value > HIGH for r in readings) / len(readings)
        in_range = sum(LOW <= r.value <= HIGH for r in readings) / len(readings)
        if above > MAX_TIME_ABOVE_RANGE:
            alerts.append(Alert(
                "high", "warning",
                f"{above:.0%} of readings above {HIGH} mg/dL",
                f"Goal is under {MAX_TIME_ABOVE_RANGE:.0%} of readings above {HIGH} mg/dL.",
            ))
        alerts.append(Alert(
            "in_range", "info",
            f"Time in range: {in_range:.0%}",
            f"{len(readings)} readings in the last {days} days; goal is over 70% within {LOW}-{HIGH} mg/dL.",
        ))

    fasting_days: dict = {}
    for r in readings:
        if r.meal_context == "fasting":
            day = r.at.date()
            fasting_days[day] = max(fasting_days.get(day, 0), r.value)
    high_days = sum(v > FASTING_HIGH for v in fasting_days.values())
    if fasting_days and high_days * 2 > len(fasting_days):
        alerts.append(Alert(
            "fasting", "warning",
            f"Fasting above {FASTING_HIGH} on {high_days} of {len(fasting_days)} days",
            f"Pre-meal target is 80-{FASTING_HIGH} mg/dL.",
        ))

    return alerts


def hba1c_alerts(results: list[tuple[datetime, float]]) -> list[Alert]:
    """`results` = (date, HbA1c %) for every HbA1c on record."""
    if not results:
        return []
    results = sorted(results)
    latest_at, latest = results[-1]
    alerts = []
    if latest >= HBA1C_GOAL:
        alerts.append(Alert(
            "hba1c", "warning",
            f"HbA1c {latest:g}% is above the {HBA1C_GOAL:g}% goal",
            f"Latest result {latest_at:%b %d, %Y}.",
        ))
    if len(results) >= 2:
        previous_at, previous = results[-2]
        change = round(latest - previous, 1)
        if abs(change) >= HBA1C_CHANGE:
            direction = "improved" if change < 0 else "rose"
            alerts.append(Alert(
                "hba1c_change", "info",
                f"HbA1c {direction} {abs(change):g} points",
                f"{previous:g}% on {previous_at:%b %d, %Y} to {latest:g}% on {latest_at:%b %d, %Y}.",
            ))
    return alerts


def bp_alerts(systolic: tuple[datetime, float] | None, diastolic: tuple[datetime, float] | None) -> list[Alert]:
    """Latest systolic and diastolic (date, mm Hg); Synthea records them together."""
    if not systolic or not diastolic:
        return []
    at, sys_value = systolic
    dia_value = diastolic[1]
    if sys_value < SYSTOLIC_GOAL and dia_value < DIASTOLIC_GOAL:
        return []
    return [Alert(
        "bp", "warning",
        f"Blood pressure {sys_value:g}/{dia_value:g} is above the {SYSTOLIC_GOAL}/{DIASTOLIC_GOAL} goal",
        f"Latest reading {at:%b %d, %Y}.",
    )]


def sort_alerts(alerts: list[Alert]) -> list[Alert]:
    return sorted(alerts, key=lambda a: SEVERITY_ORDER[a.severity])
