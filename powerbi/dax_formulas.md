# DAX Formulas — Orobic Precision Parts KPI Dashboard

All measures are written for the five processed CSV tables:
`kpi_daily`, `kpi_monthly`, `downtime_analysis`, `defect_analysis`, `machine_performance`.

---

## Table relationships (Power BI Model view)

```
kpi_daily          ──┐
                     │  Many-to-one on  Machine + Year + Month_Num
kpi_monthly        ──┤
                     │  Many-to-one on  Machine + Year
machine_performance──┘

downtime_analysis  ──→  kpi_monthly   (Machine + Year + Month_Num)
defect_analysis    ──→  kpi_monthly   (Machine + Year + Month_Num)
```

Create a shared `Date` table and relate it to `kpi_daily[Date]` and
`kpi_monthly[Year + Month_Num]` for time-intelligence functions.

---

## Shared Date table

```dax
DateTable =
ADDCOLUMNS(
    CALENDAR( DATE(2023,1,1), DATE(2024,12,31) ),
    "Year",       YEAR([Date]),
    "Month_Num",  MONTH([Date]),
    "Month_Name", FORMAT([Date], "MMM"),
    "Quarter",    "Q" & ROUNDUP( MONTH([Date]) / 3, 0),
    "Week",       WEEKNUM([Date], 2)
)
```

---

## Core KPI measures

### Plant OEE (average, all machines)
```dax
Plant OEE =
AVERAGEX(
    SUMMARIZE(
        kpi_monthly,
        kpi_monthly[Machine],
        kpi_monthly[Year],
        "MachineTotalPieces", SUM(kpi_monthly[Total_Pieces]),
        "MachineOEE",         AVERAGE(kpi_monthly[Avg_OEE])
    ),
    [MachineOEE]
)
```

### OEE (weighted by pieces)
```dax
OEE Weighted =
DIVIDE(
    SUMX( kpi_monthly, kpi_monthly[Avg_OEE] * kpi_monthly[Total_Pieces] ),
    SUM( kpi_monthly[Total_Pieces] )
)
```

### Availability
```dax
Avg Availability =
AVERAGE( kpi_monthly[Avg_Availability] )
```

### Performance
```dax
Avg Performance =
AVERAGE( kpi_monthly[Avg_Performance] )
```

### Quality / FPY
```dax
Avg Quality =
AVERAGE( kpi_monthly[Avg_Quality] )
```

### Scrap Rate
```dax
Scrap Rate =
DIVIDE(
    SUM( kpi_monthly[Rejected_Pieces] ),
    SUM( kpi_monthly[Total_Pieces] )
) * 100
```

### Total Downtime (hours)
```dax
Total Downtime Hours =
DIVIDE( SUM( kpi_monthly[Total_Downtime [sec]] ), 3600 )
```

---

## OEE vs benchmark

### OEE Gap to World-Class
```dax
OEE Gap to World-Class =
85 - [OEE Weighted]
```

### OEE Status (for conditional formatting)
```dax
OEE Status =
SWITCH(
    TRUE(),
    [OEE Weighted] >= 85,  "World-Class",
    [OEE Weighted] >= 70,  "Good",
    [OEE Weighted] >= 55,  "Average",
    "Below Average"
)
```

---

## Time-intelligence measures

All measures below require the shared `DateTable` to be marked as a
**Date Table** in Power BI (Table tools → Mark as date table → Date column).

### Month-over-month OEE change
```dax
OEE MoM Change =
VAR CurrentOEE = [OEE Weighted]
VAR PrevOEE =
    CALCULATE(
        [OEE Weighted],
        PREVIOUSMONTH( DateTable[Date] )
    )
RETURN
    IF( NOT ISBLANK(PrevOEE), CurrentOEE - PrevOEE, BLANK() )
```

### Year-to-date OEE
```dax
OEE YTD =
CALCULATE(
    [OEE Weighted],
    DATESYTD( DateTable[Date] )
)
```

### Rolling 3-month average OEE
```dax
OEE Rolling 3M =
CALCULATE(
    [OEE Weighted],
    DATESINPERIOD(
        DateTable[Date],
        LASTDATE( DateTable[Date] ),
        -3,
        MONTH
    )
)
```

### Same period prior year OEE
```dax
OEE SPLY =
CALCULATE(
    [OEE Weighted],
    SAMEPERIODLASTYEAR( DateTable[Date] )
)
```

### YoY OEE change
```dax
OEE YoY Change =
[OEE Weighted] - [OEE SPLY]
```

---

## Downtime measures

### Total downtime hours (current selection)
```dax
Downtime Hours =
DIVIDE(
    SUM( downtime_analysis[Total_Downtime [sec]] ),
    3600
)
```

### Top downtime cause
```dax
Top Downtime Cause =
CALCULATE(
    FIRSTNONBLANK( downtime_analysis[Downtime_Reason], 1 ),
    TOPN(
        1,
        SUMMARIZE(
            downtime_analysis,
            downtime_analysis[Downtime_Reason],
            "TotalDT", SUM( downtime_analysis[Total_Downtime [sec]] )
        ),
        [TotalDT],
        DESC
    )
)
```

### Downtime % of Planned
```dax
Downtime % Planned =
DIVIDE(
    SUM( kpi_monthly[Total_Downtime [sec]] ),
    COUNTROWS( kpi_daily ) * 28800
) * 100
```

---

## Defect measures

### Total rejected pieces
```dax
Total Rejected =
SUM( kpi_monthly[Rejected_Pieces] )
```

### Top defect type
```dax
Top Defect Type =
CALCULATE(
    FIRSTNONBLANK( defect_analysis[Defect_Type], 1 ),
    TOPN(
        1,
        SUMMARIZE(
            defect_analysis,
            defect_analysis[Defect_Type],
            "TotalRej", SUM( defect_analysis[Total_Rejected] )
        ),
        [TotalRej],
        DESC
    )
)
```

---

## Bottleneck identification

### Bottleneck machine (lowest OEE)
```dax
Bottleneck Machine =
CALCULATE(
    FIRSTNONBLANK( machine_performance[Machine], 1 ),
    TOPN(
        1,
        SUMMARIZE(
            machine_performance,
            machine_performance[Machine],
            "AvgOEE", AVERAGE( machine_performance[Avg_OEE] )
        ),
        [AvgOEE],
        ASC
    )
)
```

### Bottleneck OEE
```dax
Bottleneck OEE =
MINX(
    SUMMARIZE(
        machine_performance,
        machine_performance[Machine],
        "AvgOEE", AVERAGE( machine_performance[Avg_OEE] )
    ),
    [AvgOEE]
)
```
