"""
TalentLens Synthetic Data Generator

Produces ~100K employee records and ~2M HR events over a 24-month simulation
period (2024-01-01 → 2025-12-31) with statistically designed patterns:
  - Department-specific annual attrition rates (Sales 22%, Engineering 8%, etc.)
  - Attrition multipliers: low satisfaction (4x), stagnant career (2.5x),
    manager instability (2x), below-peer pay (1.8x)
  - Seasonal hiring spikes in Q1 and Q3
  - Manager-change cascades when a manager departs

Outputs:
  - data/raw/employees.parquet   — full employee roster
  - data/raw/events.parquet      — all HR events
  - Optionally loads directly into PostgreSQL (raw schema)

Usage:
  python data/synthetic_generator.py                   # write parquet only
  python data/synthetic_generator.py --load-db         # also load into postgres
  python data/synthetic_generator.py --fast            # 10K employees for dev
"""

import argparse
import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RANDOM_SEED = int(os.getenv("GENERATOR_SEED", 42))
N_EMPLOYEES_START = int(os.getenv("GENERATOR_N_EMPLOYEES", 85_000))
SIM_START = date(2024, 1, 1)
SIM_END = date(2025, 12, 31)
OUTPUT_DIR = Path(__file__).parent / "raw"

rng = np.random.default_rng(RANDOM_SEED)
fake = Faker()
Faker.seed(RANDOM_SEED)

# Department config: annual attrition rate and approximate headcount share
DEPARTMENTS = {
    "Engineering": {"attrition_annual": 0.08, "size_pct": 0.30},
    "Sales":       {"attrition_annual": 0.22, "size_pct": 0.20},
    "Finance":     {"attrition_annual": 0.12, "size_pct": 0.10},
    "HR":          {"attrition_annual": 0.10, "size_pct": 0.05},
    "Marketing":   {"attrition_annual": 0.15, "size_pct": 0.10},
    "Operations":  {"attrition_annual": 0.18, "size_pct": 0.15},
    "Legal":       {"attrition_annual": 0.07, "size_pct": 0.03},
    "Product":     {"attrition_annual": 0.10, "size_pct": 0.07},
}
DEPT_NAMES = list(DEPARTMENTS.keys())

# Monthly salary ranges (USD) by job level
SALARY_BY_LEVEL = {
    "IC1": (4_000,  6_000),
    "IC2": (6_000,  8_500),
    "IC3": (8_500, 12_000),
    "IC4": (12_000, 17_000),
    "IC5": (17_000, 25_000),
    "M1":  (10_000, 15_000),
    "M2":  (15_000, 20_000),
    "M3":  (20_000, 28_000),
    "M4":  (28_000, 40_000),
}
JOB_LEVELS = list(SALARY_BY_LEVEL.keys())
# Level distribution: IC-heavy pyramid
LEVEL_WEIGHTS = [0.25, 0.22, 0.18, 0.12, 0.07, 0.08, 0.05, 0.02, 0.01]

DEPT_SALARY_MULT = {
    "Engineering": 1.25, "Legal": 1.20, "Finance": 1.15, "Product": 1.10,
    "Marketing": 0.95, "HR": 0.90, "Operations": 0.85, "Sales": 1.00,
}

JOB_ROLES = {
    "Engineering": ["Software Engineer", "Staff Engineer", "Principal Engineer", "Engineering Manager", "VP Engineering"],
    "Sales":       ["Sales Rep", "Account Executive", "Sales Manager", "Regional Director", "VP Sales"],
    "Finance":     ["Financial Analyst", "Senior Analyst", "Finance Manager", "Controller", "CFO"],
    "HR":          ["HR Coordinator", "HR Business Partner", "HR Manager", "HR Director", "CHRO"],
    "Marketing":   ["Marketing Coordinator", "Marketing Manager", "Senior Manager", "Director Marketing", "CMO"],
    "Operations":  ["Operations Analyst", "Operations Manager", "Senior Manager", "Director Ops", "COO"],
    "Legal":       ["Legal Counsel", "Senior Counsel", "Associate GC", "Deputy GC", "GC"],
    "Product":     ["Product Manager", "Senior PM", "Staff PM", "Director Product", "VP Product"],
}

EDUCATION_FIELDS = ["Life Sciences", "Medical", "Marketing", "Technical Degree", "Human Resources", "Other"]
MARITAL_STATUSES = ["Single", "Married", "Divorced"]
GENDERS = ["Male", "Female", "Non-binary"]
GENDER_WEIGHTS = [0.48, 0.48, 0.04]

AGE_BAND_BREAKS = [18, 30, 40, 50, 65]
AGE_BAND_LABELS = ["18-29", "30-39", "40-49", "50-65"]

# Seasonal hiring: relative monthly hire rate multipliers
# Q1 (Jan-Mar) and Q3 (Jul-Sep) are high-hiring seasons
MONTHLY_HIRE_MULT = {
    1: 1.5, 2: 1.4, 3: 1.3,   # Q1 spike
    4: 0.8, 5: 0.7, 6: 0.7,   # Q2 slow
    7: 1.4, 8: 1.3, 9: 1.2,   # Q3 spike
    10: 0.8, 11: 0.6, 12: 0.5, # Q4 slow (holiday freeze)
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def new_id() -> str:
    return str(uuid.uuid4())


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta + 1)))


def months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def salary_for(level: str, dept: str) -> float:
    lo, hi = SALARY_BY_LEVEL[level]
    base = rng.uniform(lo, hi)
    mult = DEPT_SALARY_MULT[dept]
    noise = rng.normal(1.0, 0.05)
    return round(base * mult * max(0.8, noise), 2)


# ---------------------------------------------------------------------------
# Employee generation
# ---------------------------------------------------------------------------

def generate_employees(n: int, hire_date_start: date, hire_date_end: date) -> pd.DataFrame:
    """Generate n employee records with random hire dates in [hire_date_start, hire_date_end]."""
    dept_choices = rng.choice(
        DEPT_NAMES,
        size=n,
        p=[DEPARTMENTS[d]["size_pct"] for d in DEPT_NAMES],
    )
    level_choices = rng.choice(JOB_LEVELS, size=n, p=LEVEL_WEIGHTS)

    hire_days = rng.integers(0, (hire_date_end - hire_date_start).days + 1, size=n)
    hire_dates = [hire_date_start + timedelta(days=int(d)) for d in hire_days]

    ages = rng.integers(22, 62, size=n)
    age_bands = pd.cut(ages, bins=AGE_BAND_BREAKS, labels=AGE_BAND_LABELS, right=False)

    monthly_incomes = np.array([
        salary_for(level_choices[i], dept_choices[i]) for i in range(n)
    ])

    # Satisfaction and behavioral attributes (1–4 scale)
    job_satisfaction = rng.integers(1, 5, size=n)
    env_satisfaction = rng.integers(1, 5, size=n)
    work_life_balance = rng.integers(1, 5, size=n)
    performance_rating = rng.integers(1, 5, size=n)

    years_since_promotion = rng.integers(0, 4, size=n).astype(float)
    years_with_manager = rng.integers(0, 4, size=n).astype(float)
    distance_from_home = rng.integers(1, 61, size=n)
    num_companies_worked = rng.integers(0, 10, size=n)
    training_times = rng.integers(0, 7, size=n)
    overtime_flag = rng.random(size=n) < 0.28

    education = rng.integers(1, 6, size=n)
    education_field = rng.choice(EDUCATION_FIELDS, size=n)
    marital_status = rng.choice(MARITAL_STATUSES, size=n, p=[0.35, 0.50, 0.15])
    gender = rng.choice(GENDERS, size=n, p=GENDER_WEIGHTS)

    roles = [
        JOB_ROLES[dept_choices[i]][min(JOB_LEVELS.index(level_choices[i]), len(JOB_ROLES[dept_choices[i]]) - 1)]
        for i in range(n)
    ]

    employee_ids = [new_id() for _ in range(n)]

    df = pd.DataFrame({
        "employee_id": employee_ids,
        "first_name": [fake.first_name() for _ in range(n)],
        "last_name": [fake.last_name() for _ in range(n)],
        "department": dept_choices,
        "job_level": level_choices,
        "job_role": roles,
        "hire_date": hire_dates,
        "termination_date": [None] * n,
        "is_active": [True] * n,
        "monthly_income": monthly_incomes,
        "job_satisfaction": job_satisfaction,
        "environment_satisfaction": env_satisfaction,
        "work_life_balance": work_life_balance,
        "performance_rating": performance_rating,
        "years_since_last_promotion": years_since_promotion,
        "years_with_current_manager": years_with_manager,
        "distance_from_home": distance_from_home,
        "num_companies_worked": num_companies_worked,
        "training_times_last_year": training_times,
        "overtime_flag": overtime_flag,
        "education": education,
        "education_field": education_field,
        "marital_status": marital_status,
        "gender": gender,
        "age": ages,
        "age_band": age_bands.astype(str),
        "manager_id": [None] * n,  # assigned after initial pool is created
        "last_promotion_date": [None] * n,
        "manager_change_count_12m": [0] * n,
    })
    df["email"] = df["employee_id"].str.lower() + "@talentlens.internal"
    return df


def assign_managers(df: pd.DataFrame) -> pd.DataFrame:
    """Assign manager_id: M1+ employees manage IC employees within same dept."""
    df = df.copy()
    manager_mask = df["job_level"].isin(["M1", "M2", "M3", "M4", "IC5"])
    for dept in DEPT_NAMES:
        dept_mask = df["department"] == dept
        managers = df[dept_mask & manager_mask]["employee_id"].values
        non_managers = df[dept_mask & ~manager_mask].index
        if len(managers) == 0:
            continue
        df.loc[non_managers, "manager_id"] = rng.choice(managers, size=len(non_managers))
    return df


# ---------------------------------------------------------------------------
# Attrition probability
# ---------------------------------------------------------------------------

def compute_monthly_attrition_prob(df: pd.DataFrame, sim_month: date) -> np.ndarray:
    """
    Monthly attrition probability per employee based on department rate
    and individual risk factor multipliers.
    """
    probs = np.array([
        DEPARTMENTS[dept]["attrition_annual"] / 12
        for dept in df["department"]
    ])

    # Risk multipliers — additive not fully multiplicative, capped so annual
    # attrition stays realistic (~15% overall, up to ~25% in high-risk depts).
    # Each factor contributes to a risk score; score is capped at 2.5x base.
    risk_score = np.zeros(len(df))
    risk_score[df["job_satisfaction"].values < 2] += 1.5        # low satisfaction
    risk_score[df["years_since_last_promotion"].values > 3] += 0.8   # stagnant career
    risk_score[df["manager_change_count_12m"].values >= 2] += 0.6   # manager instability
    risk_score[df["performance_rating"].values >= 4] -= 0.5     # high performer: reduces risk

    # Below peer median income
    df_tmp = df.copy()
    df_tmp["peer_median"] = df_tmp.groupby(["department", "job_level"])["monthly_income"].transform("median")
    below_median = df_tmp["monthly_income"].values < df_tmp["peer_median"].values
    risk_score[below_median] += 0.4

    mult = 1.0 + np.clip(risk_score, -0.5, 1.5)  # mult range: 0.5x – 2.5x

    probs = np.clip(probs * mult, 0, 0.05)  # hard cap: 5% monthly ≈ 46% annual max
    return probs


# ---------------------------------------------------------------------------
# Event generation helpers
# ---------------------------------------------------------------------------

def make_event(employee_id: str, event_type: str, event_date: date, dept: str, payload: dict) -> dict:
    return {
        "event_id": new_id(),
        "employee_id": employee_id,
        "event_type": event_type,
        "event_date": event_date,
        "department": dept,
        "payload": json.dumps(payload),
    }


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def simulate(fast: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_start = 8_000 if fast else N_EMPLOYEES_START
    print(f"Generating {n_start:,} initial employees...")

    # Employees hired in the 5 years before simulation starts
    employees = generate_employees(
        n_start,
        hire_date_start=date(2019, 1, 1),
        hire_date_end=date(2023, 12, 31),
    )
    employees = assign_managers(employees)

    # Set initial years_since_last_promotion based on hire date vs SIM_START
    employees["last_promotion_date"] = employees["hire_date"] + pd.to_timedelta(
        (employees["years_since_last_promotion"] * 365).astype(int), unit="D"
    )
    employees["last_promotion_date"] = employees["last_promotion_date"].apply(
        lambda d: d if isinstance(d, date) and d < SIM_START else SIM_START - timedelta(days=180)
    )

    # Build initial HIRE events (pre-simulation, date = hire_date)
    events: list[dict] = []
    for _, emp in employees.iterrows():
        events.append(make_event(
            emp["employee_id"], "HIRE", emp["hire_date"], emp["department"],
            {"job_level": emp["job_level"], "monthly_income": emp["monthly_income"]},
        ))

    print("Starting 24-month simulation...")

    # Hires must roughly offset attrition (~15% annual × 2 yrs × n_start) + growth
    target_new_hires = 3_000 if fast else 15_000
    months = pd.date_range(SIM_START, SIM_END, freq="MS").date

    for month_date in months:
        month_num = month_date.month
        active = employees[employees["is_active"]].copy()
        if len(active) == 0:
            break

        # ── Attrition ──────────────────────────────────────────────────────
        probs = compute_monthly_attrition_prob(active, month_date)
        rolls = rng.random(size=len(active))
        churned_idx = active.index[rolls < probs]

        term_date = month_date + timedelta(days=int(rng.integers(1, 28)))
        employees.loc[churned_idx, "termination_date"] = term_date
        employees.loc[churned_idx, "is_active"] = False

        for idx in churned_idx:
            emp = employees.loc[idx]
            events.append(make_event(
                emp["employee_id"], "TERMINATE", term_date, emp["department"],
                {"reason": rng.choice(["voluntary", "voluntary", "involuntary"])},
            ))

        # ── Manager-change cascades ─────────────────────────────────────────
        # Direct reports of churned managers get a MANAGER_CHANGE event
        churned_ids = set(employees.loc[churned_idx, "employee_id"])
        cascade_mask = (
            employees["is_active"] &
            employees["manager_id"].isin(churned_ids)
        )
        cascade_idx = employees[cascade_mask].index

        # Reassign to a new manager within the same department
        for idx in cascade_idx:
            emp = employees.loc[idx]
            dept_managers = employees[
                employees["is_active"] &
                (employees["department"] == emp["department"]) &
                employees["job_level"].isin(["M1", "M2", "M3", "M4", "IC5"]) &
                (employees["employee_id"] != emp["employee_id"])
            ]["employee_id"].values

            if len(dept_managers) > 0:
                new_mgr = rng.choice(dept_managers)
                employees.loc[idx, "manager_id"] = new_mgr
            employees.loc[idx, "manager_change_count_12m"] += 1
            employees.loc[idx, "years_with_current_manager"] = 0
            events.append(make_event(
                emp["employee_id"], "MANAGER_CHANGE",
                month_date + timedelta(days=int(rng.integers(1, 15))),
                emp["department"],
                {"previous_manager_id": emp["manager_id"]},
            ))

        # ── New hires (seasonal) ───────────────────────────────────────────
        monthly_rate = MONTHLY_HIRE_MULT[month_num]
        base_hires_per_month = target_new_hires / (len(months) * sum(MONTHLY_HIRE_MULT.values()) / 12)
        n_hires = max(0, int(rng.normal(base_hires_per_month * monthly_rate, 5)))

        if n_hires > 0:
            hire_date = month_date + timedelta(days=int(rng.integers(1, 20)))
            new_emps = generate_employees(n_hires, hire_date, hire_date)
            new_emps = assign_managers(new_emps)  # assign from full active pool
            employees = pd.concat([employees, new_emps], ignore_index=True)

            for _, emp in new_emps.iterrows():
                events.append(make_event(
                    emp["employee_id"], "HIRE", hire_date, emp["department"],
                    {"job_level": emp["job_level"], "monthly_income": emp["monthly_income"]},
                ))

        # Re-fetch active set for remaining events
        active = employees[employees["is_active"]].copy()

        # ── Performance reviews (quarterly: Jan, Apr, Jul, Oct) ────────────
        if month_num in (1, 4, 7, 10):
            for _, emp in active.iterrows():
                new_rating = int(np.clip(
                    rng.integers(emp["performance_rating"] - 1, emp["performance_rating"] + 2),
                    1, 4
                ))
                employees.loc[emp.name, "performance_rating"] = new_rating
                events.append(make_event(
                    emp["employee_id"], "PERFORMANCE_REVIEW",
                    month_date + timedelta(days=int(rng.integers(1, 25))),
                    emp["department"],
                    {"rating": new_rating, "previous_rating": int(emp["performance_rating"])},
                ))

        # ── Promotions (biannual: Jan, Jul — top 5% performers) ───────────
        if month_num in (1, 7):
            promo_threshold = np.percentile(active["performance_rating"], 95)
            promo_eligible = active[
                (active["performance_rating"] >= promo_threshold) &
                (active["years_since_last_promotion"] >= 1)
            ]
            promo_n = max(1, int(len(promo_eligible) * 0.40))
            promo_sample = promo_eligible.sample(min(promo_n, len(promo_eligible)), random_state=RANDOM_SEED)

            for _, emp in promo_sample.iterrows():
                cur_idx = JOB_LEVELS.index(emp["job_level"])
                new_level = JOB_LEVELS[min(cur_idx + 1, len(JOB_LEVELS) - 1)]
                raise_pct = rng.uniform(0.08, 0.20)
                new_income = round(emp["monthly_income"] * (1 + raise_pct), 2)

                employees.loc[emp.name, "job_level"] = new_level
                employees.loc[emp.name, "monthly_income"] = new_income
                employees.loc[emp.name, "years_since_last_promotion"] = 0
                employees.loc[emp.name, "last_promotion_date"] = month_date

                events.append(make_event(
                    emp["employee_id"], "PROMOTE",
                    month_date + timedelta(days=int(rng.integers(1, 20))),
                    emp["department"],
                    {"new_level": new_level, "old_level": emp["job_level"],
                     "new_income": new_income, "raise_pct": round(float(raise_pct), 4)},
                ))

        # ── Annual salary changes (February) ──────────────────────────────
        if month_num == 2:
            for _, emp in active.iterrows():
                raise_pct = rng.uniform(0.02, 0.08)
                new_income = round(emp["monthly_income"] * (1 + raise_pct), 2)
                employees.loc[emp.name, "monthly_income"] = new_income
                events.append(make_event(
                    emp["employee_id"], "SALARY_CHANGE",
                    month_date + timedelta(days=int(rng.integers(1, 20))),
                    emp["department"],
                    {"old_income": float(emp["monthly_income"]),
                     "new_income": new_income, "raise_pct": round(float(raise_pct), 4)},
                ))

        # ── Absence events (random, higher for low satisfaction) ──────────
        absence_prob = np.where(active["job_satisfaction"].values <= 2, 0.20, 0.08)
        absent_idx = active.index[rng.random(len(active)) < absence_prob]
        for idx in absent_idx:
            emp = employees.loc[idx]
            n_days = int(rng.integers(1, 6))
            events.append(make_event(
                emp["employee_id"], "ABSENCE",
                month_date + timedelta(days=int(rng.integers(0, 25))),
                emp["department"],
                {"days": n_days, "is_approved": bool(rng.random() > 0.15)},
            ))

        # ── Overtime events ───────────────────────────────────────────────
        overtime_prob = np.where(active["overtime_flag"].values, 0.60, 0.10)
        ot_idx = active.index[rng.random(len(active)) < overtime_prob]
        for idx in ot_idx:
            emp = employees.loc[idx]
            events.append(make_event(
                emp["employee_id"], "OVERTIME",
                month_date + timedelta(days=int(rng.integers(0, 28))),
                emp["department"],
                {"hours": int(rng.integers(2, 25))},
            ))

        # ── Training events ───────────────────────────────────────────────
        training_prob = 0.12
        train_idx = active.index[rng.random(len(active)) < training_prob]
        for idx in train_idx:
            emp = employees.loc[idx]
            employees.loc[idx, "training_times_last_year"] = min(
                int(employees.loc[idx, "training_times_last_year"]) + 1, 6
            )
            events.append(make_event(
                emp["employee_id"], "TRAINING",
                month_date + timedelta(days=int(rng.integers(0, 28))),
                emp["department"],
                {"program": rng.choice(["Technical", "Leadership", "Compliance", "Soft Skills"])},
            ))

        # ── Increment time-based fields ───────────────────────────────────
        employees.loc[employees["is_active"], "years_since_last_promotion"] += 1 / 12
        employees.loc[employees["is_active"], "years_with_current_manager"] += 1 / 12

        # Decay manager_change_count_12m after 12 months (rough approximation)
        if month_num == 1:
            employees.loc[employees["is_active"], "manager_change_count_12m"] = (
                (employees.loc[employees["is_active"], "manager_change_count_12m"] * 0.5).astype(int)
            )

        active_count = employees["is_active"].sum()
        print(f"  {month_date} — active: {active_count:,}  events so far: {len(events):,}")

    # Generate hiring funnel events
    print("Generating hiring funnel events...")
    funnel_events = generate_hiring_funnel(len(events))
    events.extend(funnel_events)

    emp_df = employees.copy()
    emp_df["years_at_company"] = emp_df["hire_date"].apply(
        lambda d: round((SIM_END - d).days / 365, 2)
    )

    events_df = pd.DataFrame(events)

    return emp_df, events_df


def generate_hiring_funnel(base_event_count: int) -> list[dict]:
    """Generate hiring funnel events (APPLICATION → SCREEN → INTERVIEW → OFFER → HIRE/REJECT)."""
    funnel_events = []
    n_applications = 50_000
    app_dates = [random_date(SIM_START, SIM_END) for _ in range(n_applications)]
    dept_choices = rng.choice(DEPT_NAMES, size=n_applications)

    for i in range(n_applications):
        candidate_id = new_id()
        dept = dept_choices[i]
        app_date = app_dates[i]

        funnel_events.append({
            "event_id": new_id(),
            "employee_id": candidate_id,
            "event_type": "APPLICATION",
            "event_date": app_date,
            "department": dept,
            "payload": json.dumps({"role": JOB_ROLES[dept][0]}),
        })

        # ~60% pass to phone screen
        if rng.random() > 0.40:
            screen_date = app_date + timedelta(days=int(rng.integers(3, 10)))
            funnel_events.append({
                "event_id": new_id(),
                "employee_id": candidate_id,
                "event_type": "PHONE_SCREEN",
                "event_date": screen_date,
                "department": dept,
                "payload": json.dumps({"passed": bool(rng.random() > 0.45)}),
            })

            # ~55% pass to interview
            if rng.random() > 0.45:
                int_date = screen_date + timedelta(days=int(rng.integers(5, 15)))
                funnel_events.append({
                    "event_id": new_id(),
                    "employee_id": candidate_id,
                    "event_type": "INTERVIEW",
                    "event_date": int_date,
                    "department": dept,
                    "payload": json.dumps({"round": 1, "interviewer_count": int(rng.integers(2, 5))}),
                })

                # ~40% get offer
                if rng.random() > 0.60:
                    offer_date = int_date + timedelta(days=int(rng.integers(5, 14)))
                    offer_income = salary_for(rng.choice(["IC1", "IC2", "IC3"]), dept)
                    funnel_events.append({
                        "event_id": new_id(),
                        "employee_id": candidate_id,
                        "event_type": "OFFER",
                        "event_date": offer_date,
                        "department": dept,
                        "payload": json.dumps({"offered_salary": offer_income, "accepted": bool(rng.random() > 0.25)}),
                    })

    return funnel_events


# ---------------------------------------------------------------------------
# Database loader
# ---------------------------------------------------------------------------

def load_to_postgres(emp_df: pd.DataFrame, events_df: pd.DataFrame) -> None:
    import psycopg2
    from psycopg2.extras import execute_batch

    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://talentlens:talentlens@localhost:5434/talentlens"))
    cur = conn.cursor()

    print("Loading employees into raw.hris_employee_snapshot...")
    emp_records = []
    for _, row in emp_df.iterrows():
        emp_records.append((
            row["employee_id"], row["first_name"], row["last_name"], row["email"],
            row["department"], row["job_level"], row["job_role"],
            row["hire_date"],
            row["termination_date"] if row["termination_date"] is not None else None,
            bool(row["is_active"]),
            float(row["monthly_income"]),
            int(row["job_satisfaction"]), int(row["environment_satisfaction"]),
            int(row["work_life_balance"]), int(row["performance_rating"]),
            float(row["years_since_last_promotion"]),
            float(row["years_with_current_manager"]),
            float(row.get("years_at_company", 0)),
            int(row["distance_from_home"]),
            int(row["num_companies_worked"]),
            int(row["training_times_last_year"]),
            bool(row["overtime_flag"]),
            int(row["education"]), row["education_field"],
            row["marital_status"], row["gender"],
            int(row["age"]), row["age_band"],
            row["manager_id"],
        ))

    execute_batch(cur, """
        INSERT INTO raw.hris_employee_snapshot (
            employee_id, first_name, last_name, email,
            department, job_level, job_role,
            hire_date, termination_date, is_active,
            monthly_income,
            job_satisfaction, environment_satisfaction, work_life_balance, performance_rating,
            years_since_last_promotion, years_with_current_manager, years_at_company,
            distance_from_home, num_companies_worked, training_times_last_year,
            overtime_flag, education, education_field,
            marital_status, gender, age, age_band, manager_id
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (employee_id) DO NOTHING
    """, emp_records, page_size=1000)

    print("Loading events into raw.employee_events...")
    event_records = [
        (row["event_id"], row["employee_id"], row["event_type"],
         row["event_date"], row["department"], row["payload"])
        for _, row in events_df.iterrows()
        if row["event_type"] not in ("APPLICATION", "PHONE_SCREEN", "INTERVIEW", "OFFER")
    ]
    execute_batch(cur, """
        INSERT INTO raw.employee_events (event_id, employee_id, event_type, event_date, department, payload)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id) DO NOTHING
    """, event_records, page_size=2000)

    print("Loading hiring funnel events into raw.hiring_funnel_events...")
    funnel_types = {"APPLICATION", "PHONE_SCREEN", "INTERVIEW", "OFFER"}
    funnel_records = [
        (row["event_id"], row["employee_id"], row["event_type"],
         row["event_date"], row["department"], row["payload"])
        for _, row in events_df.iterrows()
        if row["event_type"] in funnel_types
    ]
    execute_batch(cur, """
        INSERT INTO raw.hiring_funnel_events (event_id, candidate_id, stage, event_date, department, payload)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id) DO NOTHING
    """, funnel_records, page_size=2000)

    conn.commit()
    cur.close()
    conn.close()
    print("Database load complete.")


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

def print_validation_report(emp_df: pd.DataFrame, events_df: pd.DataFrame) -> None:
    active = emp_df[emp_df["is_active"]]
    churned = emp_df[~emp_df["is_active"]]
    total = len(emp_df)
    attrition_rate = len(churned) / total

    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print(f"Total employees generated : {total:,}")
    print(f"Active at simulation end  : {len(active):,}")
    print(f"Churned during simulation : {len(churned):,}")
    print(f"Overall attrition rate    : {attrition_rate:.1%}  (target ~15%)")
    print(f"Total events              : {len(events_df):,}  (target 2M+)")
    print()
    print("Department attrition rates:")
    dept_churn = emp_df.groupby("department").apply(
        lambda g: (~g["is_active"]).sum() / len(g)
    ).sort_values(ascending=False)
    for dept, rate in dept_churn.items():
        target = DEPARTMENTS[dept]["attrition_annual"]
        print(f"  {dept:<15} {rate:.1%}  (annual target {target:.0%})")

    print()
    print("Event type breakdown:")
    print(events_df["event_type"].value_counts().to_string())
    print()
    print("Monthly income by level (median):")
    print(emp_df.groupby("job_level")["monthly_income"].median().apply(lambda x: f"${x:,.0f}").to_string())
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TalentLens Synthetic Data Generator")
    parser.add_argument("--load-db", action="store_true", help="Load data into PostgreSQL after generation")
    parser.add_argument("--fast", action="store_true", help="Fast mode: 10K employees for dev/testing")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Directory to write parquet files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    emp_df, events_df = simulate(fast=args.fast)

    print_validation_report(emp_df, events_df)

    emp_path = output_dir / "employees.parquet"
    events_path = output_dir / "events.parquet"

    print(f"\nWriting {len(emp_df):,} employees to {emp_path} ...")
    emp_df.to_parquet(emp_path, index=False)

    print(f"Writing {len(events_df):,} events to {events_path} ...")
    events_df.to_parquet(events_path, index=False)

    print("Done.")

    if args.load_db:
        load_to_postgres(emp_df, events_df)


if __name__ == "__main__":
    main()
