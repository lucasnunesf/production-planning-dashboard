# Production Planning · Capacity vs Load · Power BI

Power BI dashboard for **production planning (PCP)** in a metal fabrication shop: planned load vs capacity by work center and week, the bottleneck, the backlog, and how well the shop follows the plan.

The use case is based on **AC Metais**, a Brazilian laser-cutting and metal fabrication company. **All data is synthetic**, generated in Python.

> 📸 *Screenshots: `docs/images/` (add after opening the report in Power BI Desktop)*

## The problem

Every order follows a routing: **laser cutting → bending → welding → finishing → assembly → shipping**. Sales confirms delivery dates without seeing whether each work center has the hours available. The plan looks fine in total, but one work center is overloaded and every order behind it is late.

## Key findings (synthetic data, May – Nov 2026, snapshot 31 Oct)

- Overall utilization is **76%**, but **welding** is the bottleneck: 86% on average, above 100% in **7 weeks**, and up to **138%** in November after a large tank order was booked.
- Welding also takes **19.5% more hours than planned**, the largest deviation of all work centers.
- Only **71.9%** of operations finish by their planned end; the average delay of late operations is 5.1 days.
- Backlog of 2,038 planned hours; 27 operations are open past their planned end.

## Dashboard

**Page 1 · Capacity vs load** — *Can the shop deliver the plan, and where is the bottleneck?*
KPI cards (utilization, backlog hours, orders in WIP, overloaded weeks) · load vs capacity by week (column + line) · utilization by work center · backlog by work center · next weeks table (which work centers need overtime).

**Page 2 · Schedule adherence** — *Are we following the plan, and where do the hours go?*
KPI cards (adherence, avg delay, hours deviation, late open operations) · adherence by week · actual vs planned hours by work center · adherence by product family · list of late open operations.

## Data model

Two fact tables sharing conformed dimensions (galaxy schema), single-direction filters.

```
                dOrder        dWorkCenter
                  │ 1          1 │    │ 1
                  │              │    │
 fOperations * ───┘──────────── *┘    └──── * fCapacity
     * │ ┄┄┄ * (planned_end, inactive)          * │
       │ 1                                      │ 1
   dCalendar ───────────────────────────────────┘
   (planned_start)                          (date)
```

| Table | Grain | Rows |
|---|---|---|
| `fOperations` | one routing operation of an order | 3,225 |
| `fCapacity` | work center × working day (hours available) | 870 |
| `dOrder` | production order | 754 |
| `dWorkCenter` | work center | 6 |
| `dCalendar` | day (with week and horizon) | 203 |

Highlights:

- **Load vs capacity from two fact tables**: load comes from operations (by planned start), capacity from a separate table (by day), and both meet through the work center and calendar dimensions.
- **Two date roles**: planned start is active; planned end is inactive and activated with `USERELATIONSHIP` for adherence and delay.
- **Overloaded weeks** counts work center × week combinations above 100%:

```DAX
Overloaded Weeks =
SUMX (
    VALUES ( dWorkCenter[work_center] ),
    COUNTROWS ( FILTER ( VALUES ( dCalendar[week_start] ), [Utilization %] > 1 ) )
)
```

## Report as code

The report is a **Power BI Project (.pbip)** built by Python: semantic model in **TMDL**, report in **PBIR** (one JSON per page and visual) and a custom theme. `scripts/pbip_lib.py` is a small reusable builder; `scripts/build_pbip.py` only describes this dashboard. Every JSON file is validated against Microsoft's official schemas.

## Repository

```
data/production_planning.xlsx       synthetic data (5 sheets)
scripts/generate_data.py            data generator (seeded, reproducible)
scripts/pbip_lib.py                 reusable TMDL + PBIR builder
scripts/build_pbip.py               dashboard definition
scripts/validate_pbir.py            schema validation
powerbi/ProductionPlanning.pbip     open this in Power BI Desktop
docs/                               case study and screenshots
```

## How to run

```bash
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/build_pbip.py
```

1. Open `powerbi/ProductionPlanning.pbip` in Power BI Desktop (Windows).
2. *Transform data → Edit parameters →* set **DataFolder** to the full path of the `data` folder, ending with `\`.
3. *Refresh.*

Optional schema check: `git clone --depth 1 https://github.com/microsoft/json-schemas.git` and `python scripts/validate_pbir.py json-schemas`.

## Tools

Python (pandas, NumPy) · Excel · Power BI Desktop · Power Query (M) · DAX · TMDL · PBIR

## Author

[lucasnunesf](https://github.com/lucasnunesf)
