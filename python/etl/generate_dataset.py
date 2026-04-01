"""
generate_dataset.py
===================
Generates data/raw/production_log.csv — the synthetic daily production log
for Orobic Precision Parts S.r.l. (fictional company, portfolio project).

Output: 4,386 rows  (6 machines × 731 days, 2023-01-01 to 2024-12-31)
Shift model: 1 shift per day, 8 hours → Planned Time = 28,800 sec

Run:
    python python/etl/generate_dataset.py

The file is not tracked in git. Run this script before etl_pipeline.py.
"""

import os
import numpy as np
import pandas as pd

# ── Reproducibility ────────────────────────────────────────────
np.random.seed(42)

# ── Output path ────────────────────────────────────────────────
OUTPUT = os.path.join("data", "raw", "production_log.csv")
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

# ── Constants ──────────────────────────────────────────────────
PLANNED_SEC = 28_800          # 1 shift × 8 h
MONTHS      = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"]
QUARTERS    = {m: f"Q{(m-1)//3+1}" for m in range(1, 13)}

# ── Machine profiles ───────────────────────────────────────────
# av  = target Availability  (%)
# pf  = target Performance   (%)
# ql  = target Quality / FPY (%)
# dt  = annual Total_Downtime (sec) per year [2023, 2024]
# pcs = annual Total_Pieces           [2023, 2024]
# Key inefficiency driver is reflected in which component is lowest.
#
# EDM: Performance is the bottleneck (slow wire cutting speed, ~56 %)
# CMM: Performance limited by probe-programming overhead
# CNC Milling/Lathe: Availability limited by complex setups / tool changes

PROFILES = {
    "Band Saw": dict(
        step=1,
        av=[83.4, 81.9], pf=[84.6, 83.8], ql=[91.3, 90.9],
        dt=[1_585_800, 1_624_000], pcs=[5_400, 5_390],
        downtime_reasons=["Blade Change", "Planned Maintenance",
                          "Unplanned Breakdown", "Material Shortage",
                          "Changeover / Setup"],
        defect_types=["Wrong Length", "Out-of-Square Cut",
                      "Burr / Rough Edge", "Dimensional Out-of-Tol."],
    ),
    "CNC Lathe": dict(
        step=2,
        av=[85.8, 84.5], pf=[86.8, 85.8], ql=[89.7, 89.4],
        dt=[1_485_000, 1_528_000], pcs=[5_400, 5_390],
        downtime_reasons=["Tool Breakage", "Changeover / Setup",
                          "Planned Maintenance", "Coolant System Issue",
                          "Unplanned Breakdown"],
        defect_types=["Diameter Out-of-Tol.", "Thread Error",
                      "Surface Finish Fail", "Runout / Concentricity"],
    ),
    "CNC Milling": dict(
        step=3,
        av=[82.8, 81.2], pf=[85.0, 84.2], ql=[88.9, 88.6],
        dt=[1_652_000, 1_705_000], pcs=[5_400, 5_390],
        downtime_reasons=["Changeover / Setup", "Program Error / Restart",
                          "Tool Breakage", "Planned Maintenance",
                          "Unplanned Breakdown"],
        defect_types=["Surface Finish Fail", "Positional Error",
                      "Dimensional Out-of-Tol.", "Flatness Out-of-Tol."],
    ),
    "EDM Wire-Cut": dict(
        step=4,
        av=[86.0, 84.9], pf=[56.5, 56.3], ql=[99.8, 99.7],
        dt=[1_400_000, 1_460_000], pcs=[5_400, 5_390],
        downtime_reasons=["Wire Break", "Planned Maintenance",
                          "Changeover / Setup", "Dielectric Fluid Change",
                          "Unplanned Breakdown"],
        defect_types=["Contour Deviation", "Surface Recast Layer",
                      "Wire Break Scar", "Profile Out-of-Tol."],
    ),
    "Surface Grinder": dict(
        step=5,
        av=[85.2, 83.8], pf=[85.8, 85.0], ql=[89.2, 88.9],
        dt=[1_552_000, 1_605_000], pcs=[5_400, 5_390],
        downtime_reasons=["Wheel Dressing", "Planned Maintenance",
                          "Coolant System Issue", "Changeover / Setup",
                          "Unplanned Breakdown"],
        defect_types=["Flatness Out-of-Tol.", "Burn Marks",
                      "Surface Finish Fail", "Parallelism Error"],
    ),
    "CMM Inspection": dict(
        step=6,
        av=[81.5, 80.0], pf=[83.2, 82.8], ql=[88.2, 87.9],
        dt=[1_755_000, 1_810_000], pcs=[5_400, 5_390],
        downtime_reasons=["Program / Fixture Setup", "Planned Maintenance",
                          "Probe Calibration", "Operator Absence",
                          "Unplanned Breakdown"],
        defect_types=["Measurement Abort", "Fixture Error",
                      "Probe Collision", "Out-of-Tolerance Report"],
    ),
}


# ── Helper: allocate annual total across n_days ─────────────────
def allocate_annual(annual_val: int, n_days: int,
                    cv: float = 0.18,
                    clip_lo: int = 0,
                    clip_hi: int | None = None) -> np.ndarray:
    """
    Return integer array of length n_days that sums exactly to annual_val.
    Values follow a log-normal-like distribution with coefficient of
    variation cv, clipped to [clip_lo, clip_hi].
    """
    raw = np.random.normal(1.0, cv, n_days)
    raw = np.clip(raw, 0.2, 2.5)
    raw = raw / raw.sum() * annual_val
    if clip_hi is not None:
        raw = np.clip(raw, clip_lo, clip_hi)
        raw = raw / raw.sum() * annual_val   # rescale after clipping
    ints = np.round(raw).astype(int)
    # Fix rounding so sum == annual_val exactly
    diff = annual_val - ints.sum()
    step = 1 if diff > 0 else -1
    idx  = np.argsort(raw - ints)[::-1 if diff > 0 else 1]
    for i in range(abs(diff)):
        ints[idx[i]] += step
    return ints


# ── Main generation loop ────────────────────────────────────────
all_dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")
rows = []

for machine, prof in PROFILES.items():
    step = prof["step"]

    for yi, year in enumerate([2023, 2024]):
        dates_yr   = all_dates[all_dates.year == year]
        n_days     = len(dates_yr)
        pcs_annual = prof["pcs"][yi]
        dt_annual  = prof["dt"][yi]
        av_target  = prof["av"][yi] / 100
        pf_target  = prof["pf"][yi] / 100
        ql_target  = prof["ql"][yi] / 100
        scrap_rate = 1.0 - ql_target

        # Distribute annual totals across days
        pcs_day = allocate_annual(pcs_annual, n_days, cv=0.18, clip_lo=0)
        dt_day  = allocate_annual(
            dt_annual, n_days, cv=0.20,
            clip_lo=500,
            clip_hi=int(PLANNED_SEC * 0.82),   # max 82 % of shift as downtime
        )

        # Daily Performance noise (±4 % CV around yearly target)
        pf_noise = np.random.normal(pf_target, pf_target * 0.04, n_days)
        pf_noise = np.clip(pf_noise, pf_target * 0.65,
                           min(pf_target * 1.35, 0.995))

        for i, d in enumerate(dates_yr):
            pcs = int(pcs_day[i])
            dt  = int(dt_day[i])
            run = PLANNED_SEC - dt

            # Rejected pieces via binomial draw
            rej  = int(np.random.binomial(pcs, scrap_rate)) if pcs > 0 else 0
            rej  = min(rej, pcs)
            good = pcs - rej

            av  = run / PLANNED_SEC * 100
            ql  = (good / pcs * 100) if pcs > 0 else ql_target * 100
            pf  = pf_noise[i] * 100
            oee = av * pf * ql / 1e4
            scr = rej / pcs * 100 if pcs > 0 else 0.0
            fpy = good / pcs * 100 if pcs > 0 else 100.0

            rows.append({
                "Date":                  d.strftime("%d/%m/%Y"),
                "Year":                  year,
                "Month_Num":             d.month,
                "Month_Name":            MONTHS[d.month - 1],
                "Quarter":               QUARTERS[d.month],
                "Week":                  int(d.isocalendar()[1]),
                "Machine":               machine,
                "Process_Step":          step,
                "Total_Pieces":          pcs,
                "Good_Pieces":           good,
                "Rejected_Pieces":       rej,
                "Total_Downtime [sec]":  dt,
                "Total_Run_Time [sec]":  run,
                "Total_Planned [sec]":   PLANNED_SEC,
                "Avg_OEE":               round(oee, 1),
                "Avg_Availability":      round(av,  1),
                "Avg_Performance":       round(pf,  1),
                "Avg_Quality":           round(ql,  1),
                "Shifts_Run":            1,
                "Scrap_Rate":            round(scr, 2),
                "FPY":                   round(fpy, 2),
            })

df = pd.DataFrame(rows)

# ── Sanity checks ──────────────────────────────────────────────
assert len(df) == 4_386, f"Expected 4386 rows, got {len(df)}"
assert (df["Total_Run_Time [sec]"] + df["Total_Downtime [sec]"]
        == PLANNED_SEC).all(), "Run + Downtime != Planned"
assert (df["Total_Downtime [sec]"] <= PLANNED_SEC).all(), "Downtime > Planned"
assert (df["Good_Pieces"] + df["Rejected_Pieces"]
        == df["Total_Pieces"]).all(), "Good + Rejected != Total"

df.to_csv(OUTPUT, index=False)
print(f"Generated {len(df):,} rows → {OUTPUT}")
print(f"  Planned time per shift: {PLANNED_SEC:,} sec (8 h)")
print(f"  Date range: {df['Date'].iloc[0]} – {df['Date'].iloc[-1]}")
print(f"  Machines: {sorted(df['Machine'].unique())}")
print(f"  Annual pieces per machine (2023 Band Saw): "
      f"{df[(df['Machine']=='Band Saw')&(df['Year']==2023)]['Total_Pieces'].sum()}")
