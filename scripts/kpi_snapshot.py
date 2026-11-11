"""
Print the main numbers of the dashboard straight from the Excel file, using pandas.

The logic mirrors the DAX measures in build_pbip.py, so the numbers can be checked
without Power BI (and the tests compare both).
Usage:  python scripts/kpi_snapshot.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "production_planning.xlsx"
SNAPSHOT = pd.Timestamp("2026-10-31")
BOTTLENECK = "Welding / boilermaking"


def load(path=DATA):
    x = pd.read_excel(path, sheet_name=None)
    wc = x["dWorkCenter"]
    ops = x["fOperations"].merge(wc, on="work_center_id").merge(x["dOrder"], on="order_id")
    cap = x["fCapacity"].merge(wc, on="work_center_id")
    ops["delay_days"] = (ops.actual_end - ops.planned_end).dt.days.clip(lower=0).where(ops.status == "Done", 0)
    ops["is_late_open"] = (ops.status != "Done") & (ops.planned_end < SNAPSHOT)
    for t, d in ((ops, "planned_start"), (cap, "date")):
        t["week_start"] = t[d] - pd.to_timedelta(t[d].dt.dayofweek, unit="D")
    return ops, cap


def weekly_utilization(ops, cap):
    load = ops.groupby(["work_center", "week_start"]).planned_hours.sum()
    capacity = cap.groupby(["work_center", "week_start"]).capacity_hours.sum()
    return (load / capacity).dropna()


def kpis(ops, cap):
    done = ops[ops.status == "Done"]
    util = weekly_utilization(ops, cap)
    by_wc = ops.groupby("work_center").planned_hours.sum() / cap.groupby("work_center").capacity_hours.sum()
    hours = done.groupby("work_center")[["planned_hours", "actual_hours"]].sum()
    return {
        "operations": len(ops),
        "orders": ops.order_id.nunique(),
        "utilization": ops.planned_hours.sum() / cap.capacity_hours.sum(),
        "bottleneck_utilization": by_wc[BOTTLENECK],
        "bottleneck_overloaded_weeks": int((util[BOTTLENECK] > 1).sum()),
        "bottleneck_peak": util[BOTTLENECK].max(),
        "bottleneck_hours_deviation": hours.actual_hours[BOTTLENECK] / hours.planned_hours[BOTTLENECK] - 1,
        "overloaded_weeks_all": int((util > 1).sum()),
        "adherence": (done.delay_days == 0).mean(),
        "avg_delay_days": done[done.delay_days > 0].delay_days.mean(),
        "backlog_hours": ops[ops.status != "Done"].planned_hours.sum(),
        "late_open_operations": int(ops.is_late_open.sum()),
        "orders_in_wip": ops[ops.status == "In progress"].order_id.nunique(),
    }


if __name__ == "__main__":
    k = kpis(*load())
    print(f"Operations / orders        {k['operations']:,} / {k['orders']:,}")
    print(f"Utilization (all)          {k['utilization']:.0%}")
    print(f"Welding utilization        {k['bottleneck_utilization']:.0%}  "
          f"(> 100% in {k['bottleneck_overloaded_weeks']} weeks, peak {k['bottleneck_peak']:.0%})")
    print(f"Welding hours vs plan      {k['bottleneck_hours_deviation']:+.1%}")
    print(f"Schedule adherence         {k['adherence']:.1%}  (late ones: {k['avg_delay_days']:.1f} days)")
    print(f"Backlog                    {k['backlog_hours']:,.0f} h")
    print(f"Late open operations       {k['late_open_operations']}")
    print(f"Orders in WIP              {k['orders_in_wip']}")
