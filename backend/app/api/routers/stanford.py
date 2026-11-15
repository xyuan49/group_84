from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(
    prefix="/stanford",
    tags=["Stanford"],
)

DATA_FILE = Path("../data/data_cgm.csv")

@router.get("/subjects")
def get_subjects():
    df = pd.read_csv(DATA_FILE)

    return sorted(df["subject"].unique().tolist())

@router.get("/foods")
def get_foods(
    subject: str = Query(...),
):
    df = pd.read_csv(DATA_FILE)

    foods = (
        df[df["subject"] == subject]["food"]
        .dropna()
        .unique()
        .tolist()
    )

    return sorted(foods)

@router.get("/glucose")
def get_glucose_curve(
    subject: str = Query(...),
    food: str = Query(...),
):
    df = pd.read_csv(DATA_FILE)

    result = df[
        (df["subject"] == subject)
        & (df["food"] == food)
    ]

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail="No matching records found",
        )

    return [
        {
            "minutes": row["mins_since_start"],
            "glucose": row["glucose"],
        }
        for _, row in result.sort_values(
            "mins_since_start"
        ).iterrows()
    ]

@router.get("/summary")
def get_summary(
    subject: str = Query(...),
    food: str = Query(...),
):
    df = pd.read_csv(DATA_FILE)

    result = df[
        (df["subject"] == subject)
        & (df["food"] == food)
    ]

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail="No matching records found",
        )

    baseline = result.loc[
        result["mins_since_start"] <= 0,
        "glucose",
    ].mean()

    peak = result["glucose"].max()

    return {
        "subject": subject,
        "food": food,
        "baseline_glucose": round(float(baseline), 2),
        "peak_glucose": round(float(peak), 2),
        "increase": round(float(peak - baseline), 2),
        "samples": len(result),
    }