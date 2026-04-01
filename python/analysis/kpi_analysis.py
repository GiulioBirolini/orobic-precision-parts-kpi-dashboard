"""
kpi_analysis.py
===============
Generates 8 publication-quality charts for the Orobic Precision Parts
KPI Dashboard.  All figures are saved to reports/figures/.

Charts produced:
  01_oee_trend.png          — Monthly OEE trend by machine
  02_oee_components.png     — OEE components: Availability, Performance, Quality
  03_downtime_pareto.png    — Downtime Pareto by cause (hours, all machines)
  04_downtime_heatmap.png   — Downtime heatmap: machine × cause
  05_machine_heatmap.png    — Machine performance heatmap (OEE components)
  06_oee_vs_downtime.png    — OEE vs total annual downtime scatter
  07_oee_distribution.png   — Daily OEE KDE distribution by machine
  08_scrap_rate_trend.png   — Monthly scrap rate trend by machine

Run:
    python python/analysis/kpi_analysis.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────
PROC_DIR = os.path.join("data", "processed")
FIG_DIR  = os.path.join("reports", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── Load tables ────────────────────────────────────────────────
kpi_daily  = pd.read_csv(os.path.join(PROC_DIR, "kpi_daily.csv"))
kpi_month  = pd.read_csv(os.path.join(PROC_DIR, "kpi_monthly.csv"))
machine_pf = pd.read_csv(os.path.join(PROC_DIR, "machine_performance.csv"))
downtime   = pd.read_csv(os.path.join(PROC_DIR, "downtime_analysis.csv"))

# ── Shared aesthetics ──────────────────────────────────────────
MACHINE_ORDER = [
    "Band Saw", "CNC Lathe", "CNC Milling",
    "EDM Wire-Cut", "Surface Grinder", "CMM Inspection",
]
PALETTE = sns.color_palette("tab10", n_colors=6)
MACHINE_COLORS = dict(zip(MACHINE_ORDER, PALETTE))

plt.rcParams.update({
    "figure.dpi":        150,
    "font.family":       "sans-serif",
    "font.size":         10,
    "axes.titlesize":    11,
    "axes.titleweight":  "bold",
    "axes.labelsize":    9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "legend.fontsize":   8,
    "legend.frameon":    False,
})

WORLD_CLASS_OEE = 85.0


def save(name: str) -> None:
    path = os.path.join(FIG_DIR, name)
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ══════════════════════════════════════════════════════════════
# 01 — Monthly OEE trend by machine
# ══════════════════════════════════════════════════════════════
print("01 — Monthly OEE trend …")

# Build a sortable period column
kpi_month["Period"] = pd.to_datetime(
    kpi_month["Year"].astype(str) + "-" + kpi_month["Month_Num"].astype(str).str.zfill(2)
)
kpi_month = kpi_month.sort_values("Period")

fig, ax = plt.subplots(figsize=(12, 5))
for machine in MACHINE_ORDER:
    sub = kpi_month[kpi_month["Machine"] == machine]
    ax.plot(sub["Period"], sub["Avg_OEE"],
            label=machine, color=MACHINE_COLORS[machine],
            linewidth=1.6, marker="o", markersize=3)

ax.axhline(WORLD_CLASS_OEE, color="red", linestyle="--",
           linewidth=1.2, label="World-class (85 %)")
ax.axvline(pd.Timestamp("2024-01-01"), color="grey",
           linestyle=":", linewidth=1.0, alpha=0.7)
ax.text(pd.Timestamp("2024-01-15"), ax.get_ylim()[0] + 1,
        "2024", color="grey", fontsize=8)

ax.set_title("Monthly OEE Trend by Machine — Orobic Precision Parts (2023–2024)")
ax.set_ylabel("OEE (%)")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
ax.set_ylim(0, 100)
ax.legend(loc="lower right", ncol=2)
fig.tight_layout()
save("01_oee_trend.png")


# ══════════════════════════════════════════════════════════════
# 02 — OEE components bar chart (avg 2023-2024)
# ══════════════════════════════════════════════════════════════
print("02 — OEE components …")

avg_mp = (machine_pf.groupby("Machine")[
    ["Avg_OEE", "Avg_Availability", "Avg_Performance", "Avg_Quality"]]
    .mean()
    .reindex(MACHINE_ORDER)
    .reset_index())

components = ["Avg_Availability", "Avg_Performance", "Avg_Quality", "Avg_OEE"]
comp_labels = ["Availability", "Performance", "Quality", "OEE"]
comp_colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]

x = np.arange(len(MACHINE_ORDER))
width = 0.18
fig, ax = plt.subplots(figsize=(12, 5))

for i, (col, label, color) in enumerate(zip(components, comp_labels, comp_colors)):
    offset = (i - 1.5) * width
    bars = ax.bar(x + offset, avg_mp[col], width,
                  label=label, color=color, alpha=0.85)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{bar.get_height():.1f}",
                ha="center", va="bottom", fontsize=7)

ax.axhline(WORLD_CLASS_OEE, color="red", linestyle="--",
           linewidth=1.1, label="World-class (85 %)")
ax.set_title("OEE Components by Machine — 2023–2024 Average")
ax.set_ylabel("(%)")
ax.set_xticks(x)
ax.set_xticklabels(MACHINE_ORDER, rotation=15, ha="right")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
ax.set_ylim(0, 110)
ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.02))
fig.tight_layout()
save("02_oee_components.png")


# ══════════════════════════════════════════════════════════════
# 03 — Downtime Pareto (all machines, all years, hours)
# ══════════════════════════════════════════════════════════════
print("03 — Downtime Pareto …")

pareto = (downtime.groupby("Downtime_Reason")["Total_Downtime [sec]"]
          .sum()
          .sort_values(ascending=False)
          .reset_index())
pareto["Hours"] = pareto["Total_Downtime [sec]"] / 3600
pareto["Cumulative %"] = (pareto["Hours"].cumsum()
                          / pareto["Hours"].sum() * 100)

fig, ax1 = plt.subplots(figsize=(12, 5))
ax2 = ax1.twinx()

bars = ax1.bar(pareto["Downtime_Reason"], pareto["Hours"],
               color="#4C72B0", alpha=0.85)
ax2.plot(pareto["Downtime_Reason"], pareto["Cumulative %"],
         color="red", marker="D", markersize=5, linewidth=1.5)
ax2.axhline(80, color="orange", linestyle="--", linewidth=1.0, alpha=0.7)

ax1.set_title("Downtime Pareto by Cause — All Machines 2023–2024 (hours)")
ax1.set_ylabel("Total Downtime (hours)")
ax1.set_xlabel("")
ax2.set_ylabel("Cumulative %")
ax2.set_ylim(0, 110)
ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))

plt.setp(ax1.get_xticklabels(), rotation=30, ha="right", fontsize=8)
fig.tight_layout()
save("03_downtime_pareto.png")


# ══════════════════════════════════════════════════════════════
# 04 — Downtime heatmap: machine × cause (hours)
# ══════════════════════════════════════════════════════════════
print("04 — Downtime heatmap …")

pivot = (downtime.groupby(["Machine", "Downtime_Reason"])["Total_Downtime [sec]"]
         .sum()
         .reset_index())
pivot["Hours"] = (pivot["Total_Downtime [sec]"] / 3600).round(0).astype(int)
heat = pivot.pivot(index="Machine", columns="Downtime_Reason",
                   values="Hours").reindex(MACHINE_ORDER).fillna(0)

fig, ax = plt.subplots(figsize=(13, 5))
sns.heatmap(heat, annot=True, fmt="g", cmap="YlOrRd",
            linewidths=0.5, linecolor="white",
            cbar_kws={"label": "Hours"}, ax=ax)
ax.set_title("Downtime by Machine and Root Cause — 2023–2024 (hours)")
ax.set_xlabel("")
ax.set_ylabel("")
plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=8)
fig.tight_layout()
save("04_downtime_heatmap.png")


# ══════════════════════════════════════════════════════════════
# 05 — Machine performance heatmap (OEE components, avg 2023-2024)
# ══════════════════════════════════════════════════════════════
print("05 — Machine performance heatmap …")

heat2 = avg_mp.set_index("Machine")[
    ["Avg_OEE", "Avg_Availability", "Avg_Performance", "Avg_Quality"]
].reindex(MACHINE_ORDER)
heat2.columns = ["OEE (%)", "Availability (%)", "Performance (%)", "Quality (%)"]

fig, ax = plt.subplots(figsize=(8, 4))
sns.heatmap(heat2, annot=True, fmt=".1f", cmap="RdYlGn",
            vmin=45, vmax=100,
            linewidths=0.5, linecolor="white",
            cbar_kws={"label": "%"}, ax=ax)
ax.set_title("Machine Performance Heatmap — 2023–2024 Average (%)")
ax.set_xlabel("")
ax.set_ylabel("")
fig.tight_layout()
save("05_machine_heatmap.png")


# ══════════════════════════════════════════════════════════════
# 06 — OEE vs Total Annual Downtime scatter
# ══════════════════════════════════════════════════════════════
print("06 — OEE vs downtime scatter …")

scatter = machine_pf.copy()
scatter["DT_hours"] = scatter["Total_Downtime [sec]"] / 3600

fig, ax = plt.subplots(figsize=(8, 5))
for machine in MACHINE_ORDER:
    sub = scatter[scatter["Machine"] == machine]
    ax.scatter(sub["DT_hours"], sub["Avg_OEE"],
               label=machine, color=MACHINE_COLORS[machine],
               s=90, zorder=3, edgecolors="white", linewidths=0.5)
    # Annotate with year
    for _, r in sub.iterrows():
        ax.annotate(str(int(r["Year"])),
                    (r["DT_hours"], r["Avg_OEE"]),
                    textcoords="offset points", xytext=(5, 3), fontsize=7)

ax.axhline(WORLD_CLASS_OEE, color="red", linestyle="--",
           linewidth=1.1, alpha=0.7, label="World-class (85 %)")
ax.set_title("OEE vs Total Annual Downtime per Machine (2023–2024)")
ax.set_xlabel("Total Annual Downtime (hours)")
ax.set_ylabel("Average OEE (%)")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
ax.legend(loc="upper right", ncol=2)
fig.tight_layout()
save("06_oee_vs_downtime.png")


# ══════════════════════════════════════════════════════════════
# 07 — Daily OEE KDE distribution by machine
# ══════════════════════════════════════════════════════════════
print("07 — OEE KDE distribution …")

fig, ax = plt.subplots(figsize=(10, 5))
for machine in MACHINE_ORDER:
    sub = kpi_daily[kpi_daily["Machine"] == machine]["Avg_OEE"]
    sns.kdeplot(sub, label=machine,
                color=MACHINE_COLORS[machine],
                linewidth=1.8, fill=True, alpha=0.12, ax=ax)

ax.axvline(WORLD_CLASS_OEE, color="red", linestyle="--",
           linewidth=1.2, label="World-class (85 %)")
ax.set_title("Daily OEE Distribution by Machine — KDE (2023–2024)")
ax.set_xlabel("OEE (%)")
ax.set_ylabel("Density")
ax.set_xlim(0, 100)
ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
ax.legend(ncol=2)
fig.tight_layout()
save("07_oee_distribution.png")


# ══════════════════════════════════════════════════════════════
# 08 — Monthly scrap rate trend by machine
# ══════════════════════════════════════════════════════════════
print("08 — Scrap rate trend …")

fig, ax = plt.subplots(figsize=(12, 5))
for machine in MACHINE_ORDER:
    sub = kpi_month[kpi_month["Machine"] == machine].sort_values("Period")
    ax.plot(sub["Period"], sub["Scrap_Rate"],
            label=machine, color=MACHINE_COLORS[machine],
            linewidth=1.6, marker="o", markersize=3)

ax.axhline(1.0, color="red", linestyle="--",
           linewidth=1.1, label="World-class target (1 %)")
ax.axvline(pd.Timestamp("2024-01-01"), color="grey",
           linestyle=":", linewidth=1.0, alpha=0.7)
ax.text(pd.Timestamp("2024-01-15"), ax.get_ylim()[1] * 0.95,
        "2024", color="grey", fontsize=8)

ax.set_title("Monthly Scrap Rate Trend by Machine — Orobic Precision Parts (2023–2024)")
ax.set_ylabel("Scrap Rate (%)")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
ax.legend(loc="upper right", ncol=2)
fig.tight_layout()
save("08_scrap_rate_trend.png")

print("\nAll 8 figures saved to", FIG_DIR)
