"""
Cohort Retention Engine
Core analytics logic — cohort matrix construction, retention curves, drop-off analysis.
"""

import pandas as pd
import numpy as np


def load_and_validate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects columns: user_id, event_date, event_type (optional).
    Normalizes column names and parses dates.
    """
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = {"user_id", "event_date"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required}. Got: {set(df.columns)}")

    df["event_date"] = pd.to_datetime(df["event_date"])
    df["user_id"] = df["user_id"].astype(str)
    return df


def build_cohort_matrix(df: pd.DataFrame, period: str = "M") -> pd.DataFrame:
    """
    Builds a cohort retention matrix.
    period: 'M' for monthly, 'W' for weekly.
    Returns a DataFrame where rows = cohort period, columns = period index (0, 1, 2...).
    """
    df = df.copy()

    # Cohort = the period of the user's first event
    df["cohort"] = df.groupby("user_id")["event_date"].transform("min").dt.to_period(period)
    df["event_period"] = df["event_date"].dt.to_period(period)

    # Period index = how many periods after acquisition
    df["period_index"] = (df["event_period"] - df["cohort"]).apply(lambda x: x.n)

    # Count distinct users per cohort x period
    cohort_data = (
        df.groupby(["cohort", "period_index"])["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id": "users"})
    )

    # Pivot to matrix
    matrix = cohort_data.pivot_table(index="cohort", columns="period_index", values="users")
    matrix.index = matrix.index.astype(str)
    matrix.columns = [f"Period {c}" for c in matrix.columns]

    return matrix


def build_retention_pct(matrix: pd.DataFrame) -> pd.DataFrame:
    """Convert absolute counts to retention percentages relative to cohort size (Period 0)."""
    cohort_sizes = matrix.iloc[:, 0]
    pct = matrix.div(cohort_sizes, axis=0) * 100
    return pct.round(1)


def compute_dropoff(pct_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Period-over-period drop-off: how much retention fell from one period to the next.
    Returns a DataFrame of the same shape with drop-off values.
    """
    cols = pct_matrix.columns.tolist()
    dropoff = pd.DataFrame(index=pct_matrix.index)
    for i in range(1, len(cols)):
        dropoff[f"{cols[i-1]} → {cols[i]}"] = (
            pct_matrix[cols[i]] - pct_matrix[cols[i - 1]]
        ).round(1)
    return dropoff


def avg_retention_curve(pct_matrix: pd.DataFrame) -> pd.Series:
    """Mean retention across all cohorts at each period index."""
    return pct_matrix.mean(axis=0).round(1)


def cohort_summary(matrix: pd.DataFrame, pct_matrix: pd.DataFrame) -> pd.DataFrame:
    """Summary table: cohort, size, and retention at key periods."""
    sizes = matrix.iloc[:, 0].rename("Cohort Size")
    cols = pct_matrix.columns.tolist()

    summary = pd.DataFrame({"Cohort Size": sizes})
    for label, idx in [("Period 1 Retention %", 1), ("Period 2 Retention %", 2), ("Period 3 Retention %", 3)]:
        if idx < len(cols):
            summary[label] = pct_matrix.iloc[:, idx]
    return summary


def generate_sample_data(n_users: int = 400, n_months: int = 8, seed: int = 42) -> pd.DataFrame:
    """Generate realistic synthetic event data with natural churn curve."""
    rng = np.random.default_rng(seed)
    rows = []

    base = pd.Timestamp("2023-01-01")
    cohort_sizes = rng.integers(30, 80, size=n_months)

    for month_offset, size in enumerate(cohort_sizes):
        acquisition_date = base + pd.DateOffset(months=month_offset)
        user_ids = [f"u_{month_offset}_{i}" for i in range(size)]

        for uid in user_ids:
            rows.append({"user_id": uid, "event_date": acquisition_date, "event_type": "acquisition"})
            # Retention probability decays each period (natural churn)
            for p in range(1, n_months - month_offset):
                retention_prob = 0.65 * (0.72 ** p) + rng.uniform(-0.05, 0.05)
                if rng.random() < max(retention_prob, 0.05):
                    event_date = acquisition_date + pd.DateOffset(months=p)
                    rows.append({"user_id": uid, "event_date": event_date, "event_type": "active"})

    return pd.DataFrame(rows)
