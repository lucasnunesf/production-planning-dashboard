"""
Generate synthetic data for the production planning (capacity vs load) dashboard.

Scenario (inspired by AC Metais, a Brazilian laser-cutting and metal fabrication shop):
every production order follows a routing through work centers
(laser cutting -> bending -> welding -> finishing -> assembly -> shipping).
Planning compares the planned load (hours) of each work center with its capacity, and
execution compares actual hours and finish dates with the plan.
Welding is the bottleneck, and a large tank order booked for November overloads it.

All numbers are synthetic. Snapshot ("today") = 31 Oct 2026; the plan runs to 22 Nov 2026.
Output: data/production_planning.xlsx
Sheets: fOperations, fCapacity, dOrder, dWorkCenter, dCalendar

Usage:  python scripts/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 11
START, SNAPSHOT, END = pd.Timestamp("2026-05-04"), pd.Timestamp("2026-10-31"), pd.Timestamp("2026-11-22")
OUT = Path(__file__).resolve().parents[1] / "data" / "production_planning.xlsx"
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- dWorkCenter
# id, name, seq, capacity h/day (Mon-Fri), share of orders that use it, hour overrun factor, delay prob
WC = [
    ("WC10", "Laser cutting",          1, 32, 1.00, 1.02, 0.08),
    ("WC20", "Press brake bending",    2, 24, 0.80, 1.05, 0.12),
    ("WC30", "Welding / boilermaking", 3, 40, 0.60, 1.18, 0.30),
    ("WC40", "Finishing & painting",   4, 16, 0.70, 1.06, 0.15),
    ("WC50", "Assembly",               5, 16, 0.30, 1.08, 0.12),
    ("WC60", "Shipping",               6, 8,  1.00, 1.00, 0.05),
]
dWorkCenter = pd.DataFrame([dict(work_center_id=w[0], work_center=w[1], routing_sequence=w[2],
                                 capacity_hours_per_day=w[3]) for w in WC])

# product family -> average hours per work center (laser, bending, welding, finishing, assembly, shipping)
FAMILIES = {
    "Brackets & small parts": ([3.0, 3.0, 4.0, 2.0, 3.0, 0.8], 0.35),
    "Machine guards":         ([5.0, 4.5, 9.0, 3.5, 6.0, 1.0], 0.25),
    "Structural frames":      ([6.0, 3.0, 18.0, 4.0, 7.0, 1.2], 0.20),
    "Tanks & hoppers":        ([6.5, 4.0, 22.0, 5.0, 8.0, 1.5], 0.10),
    "Custom assemblies":      ([4.5, 3.5, 12.0, 3.0, 9.0, 1.0], 0.10),
}
CUSTOMERS = [f"Customer {i:02d}" for i in range(1, 31)]
fam_names = list(FAMILIES)
fam_p = np.array([FAMILIES[f][1] for f in fam_names])

workdays = pd.bdate_range(START, END)


def add_workdays(d, n):
    return d + pd.offsets.BDay(n)


orders, ops = [], []
for d in pd.bdate_range(START - pd.Timedelta(days=21), pd.Timestamp("2026-11-20")):
    n = rng.poisson(5.2)
    for _ in range(n):
        fam = fam_names[rng.choice(len(fam_names), p=fam_p)]
        # November: a large order of tanks for one customer is booked
        if pd.Timestamp("2026-10-26") <= d <= pd.Timestamp("2026-11-13") and rng.random() < 0.35:
            fam, cust = "Tanks & hoppers", "Customer 07"
        else:
            cust = rng.choice(CUSTOMERS)
        oid = f"PO{len(orders) + 1:05d}"
        qty = int(rng.integers(1, 40))
        start = add_workdays(d, 1)
        seq_start = start
        routing = []
        for (wid, _, _, _, share, overrun, p_delay), avg_h in zip(WC, FAMILIES[fam][0]):
            if wid not in ("WC10", "WC60") and rng.random() > share:
                continue
            ph = round(max(0.5, avg_h * rng.lognormal(0, 0.35)), 1)
            dur = max(1, int(np.ceil(ph / 8)))
            ps, pe = seq_start, add_workdays(seq_start, dur - 1)
            seq_start = add_workdays(pe, 1)
            routing.append((wid, ph, ps, pe, overrun, p_delay))
        due = add_workdays(seq_start, 2)
        orders.append(dict(order_id=oid, customer=cust, product_family=fam, quantity=qty,
                           release_date=start, due_date=due))

        shift = 0                                                # delays push the next operations
        for k, (wid, ph, ps, pe, overrun, p_delay) in enumerate(routing, 1):
            ps_a, pe_a = add_workdays(ps, shift), add_workdays(pe, shift)
            delay = int(rng.gamma(1.5, 1.6)) + 1 if rng.random() < p_delay else 0
            actual_end = add_workdays(pe_a, delay)
            ah = round(ph * overrun * rng.lognormal(0, 0.12), 1)
            if actual_end <= SNAPSHOT:
                status, a_end, a_h = "Done", actual_end, ah
            elif ps_a <= SNAPSHOT:
                status, a_end, a_h = "In progress", pd.NaT, None
            else:
                status, a_end, a_h = "Planned", pd.NaT, None
            shift += delay
            if ps < START or ps > END:
                continue
            ops.append(dict(operation_id=f"{oid}-{k * 10:03d}", order_id=oid, work_center_id=wid,
                            operation_sequence=k * 10, planned_start=ps, planned_end=pe,
                            planned_hours=ph, actual_hours=a_h, actual_end=a_end, status=status))

dOrder = pd.DataFrame(orders)
fOperations = pd.DataFrame(ops)
dOrder = dOrder[dOrder.order_id.isin(fOperations.order_id)].reset_index(drop=True)

# ---------------------------------------------------------------- fCapacity
cap = [dict(date=d, work_center_id=w[0], capacity_hours=float(w[3])) for d in workdays for w in WC]
fCapacity = pd.DataFrame(cap)
# planned maintenance / holidays
fCapacity.loc[(fCapacity.work_center_id == "WC10") & fCapacity.date.between("2026-08-10", "2026-08-12"),
              "capacity_hours"] = 16.0
fCapacity.loc[fCapacity.date.isin(pd.to_datetime(["2026-09-07", "2026-10-12", "2026-11-02", "2026-11-20"])),
              "capacity_hours"] = 0.0

# ---------------------------------------------------------------- dCalendar
cal = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
cal["week_start"] = cal.date - pd.to_timedelta(cal.date.dt.dayofweek, unit="D")
cal["week_start_number"] = cal.week_start.dt.strftime("%Y%m%d").astype(int)
cal["week_label"] = cal.week_start.dt.strftime("%d %b")
cal["year_month_number"] = cal.date.dt.year * 100 + cal.date.dt.month
cal["month_label"] = cal.date.dt.strftime("%b %Y")
cal["horizon"] = np.where(cal.date > SNAPSHOT, "Plan ahead", "History")

OUT.parent.mkdir(parents=True, exist_ok=True)
with pd.ExcelWriter(OUT, engine="openpyxl", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as w:
    fOperations.to_excel(w, sheet_name="fOperations", index=False)
    fCapacity.to_excel(w, sheet_name="fCapacity", index=False)
    dOrder.to_excel(w, sheet_name="dOrder", index=False)
    dWorkCenter.to_excel(w, sheet_name="dWorkCenter", index=False)
    cal.to_excel(w, sheet_name="dCalendar", index=False)
print(f"{len(fOperations):,} operations / {len(dOrder):,} orders written to {OUT}")
