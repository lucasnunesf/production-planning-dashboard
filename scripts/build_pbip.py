"""
Build the Power BI Project for the production planning dashboard.
Usage:  python scripts/build_pbip.py   ->  powerbi/ProductionPlanning.pbip
"""
from pathlib import Path

from pbip_lib import (CARD_H, CARD_W, CARD_X, CARD_Y, SLICER_1, SLICER_2, Model, Page, Style,
                      build_project, categorical_filter, col, meas)

ROOT = Path(__file__).resolve().parents[1]


def m(name):
    return meas("fOperations", name)


TABLES = {
    "fOperations": [
        ("operation_id", "type text", "string", "none", None),
        ("order_id", "type text", "string", "none", None),
        ("work_center_id", "type text", "string", "none", None),
        ("operation_sequence", "Int64.Type", "int64", "none", "0"),
        ("planned_start", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("planned_end", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("planned_hours", "type number", "double", "sum", "#,0.0"),
        ("actual_hours", "type number", "double", "sum", "#,0.0"),
        ("actual_end", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("status", "type text", "string", "none", None),
    ],
    "fCapacity": [
        ("date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("work_center_id", "type text", "string", "none", None),
        ("capacity_hours", "type number", "double", "sum", "#,0.0"),
    ],
    "dOrder": [
        ("order_id", "type text", "string", "none", None),
        ("customer", "type text", "string", "none", None),
        ("product_family", "type text", "string", "none", None),
        ("quantity", "Int64.Type", "int64", "sum", "#,0"),
        ("release_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("due_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
    ],
    "dWorkCenter": [
        ("work_center_id", "type text", "string", "none", None),
        ("work_center", "type text", "string", "none", None),
        ("routing_sequence", "Int64.Type", "int64", "none", "0"),
        ("capacity_hours_per_day", "Int64.Type", "int64", "none", "0"),
    ],
    "dCalendar": [
        ("date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("week_start", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("week_start_number", "Int64.Type", "int64", "none", "0"),
        ("week_label", "type text", "string", "none", None),
        ("year_month_number", "Int64.Type", "int64", "none", "0"),
        ("month_label", "type text", "string", "none", None),
        ("horizon", "type text", "string", "none", None),
    ],
}
SORT_BY = {("dCalendar", "week_label"): "week_start_number",
           ("dCalendar", "month_label"): "year_month_number",
           ("dWorkCenter", "work_center"): "routing_sequence"}

CALC = {"fOperations": [
    ("delay_days", "int64", "0", None, [
        "-- calendar days finished after the planned end (0 if on time or not finished)",
        "IF (",
        "    fOperations[status] = \"Done\",",
        "    MAX ( 0, INT ( fOperations[actual_end] - fOperations[planned_end] ) ),",
        "    0",
        ")",
    ]),
    ("is_late_open", "string", None, None, [
        "-- not finished although the planned end is already in the past",
        "VAR snapshot = DATE ( 2026, 10, 31 )",
        "RETURN IF ( fOperations[status] <> \"Done\" && fOperations[planned_end] < snapshot, \"Yes\", \"No\" )",
    ]),
]}

MEASURES = {"fOperations": [
    ("Planned Load (h)", "1 Capacity", "#,0", ["SUM ( fOperations[planned_hours] )"]),
    ("Capacity (h)", "1 Capacity", "#,0", ["SUM ( fCapacity[capacity_hours] )"]),
    ("Utilization %", "1 Capacity", "0%", ["DIVIDE ( [Planned Load (h)], [Capacity (h)] )"]),
    ("Backlog (h)", "1 Capacity", "#,0", [
        "-- planned hours not finished yet",
        "CALCULATE ( [Planned Load (h)], fOperations[status] <> \"Done\" )",
    ]),
    ("Orders in WIP", "1 Capacity", "#,0", [
        "CALCULATE ( DISTINCTCOUNT ( fOperations[order_id] ), fOperations[status] = \"In progress\" )",
    ]),
    ("Overloaded Weeks", "1 Capacity", "#,0", [
        "-- number of (work center x week) combinations where load > capacity",
        "SUMX (",
        "    VALUES ( dWorkCenter[work_center] ),",
        "    COUNTROWS ( FILTER ( VALUES ( dCalendar[week_start] ), [Utilization %] > 1 ) )",
        ")",
    ]),
    ("Operations Done", "2 Execution", "#,0", [
        "CALCULATE (",
        "    COUNTROWS ( fOperations ),",
        "    fOperations[status] = \"Done\",",
        "    USERELATIONSHIP ( fOperations[planned_end], dCalendar[date] )",
        ")",
    ]),
    ("Schedule Adherence %", "2 Execution", "0.0%", [
        "-- operations finished on or before the planned end, by week of planned end",
        "VAR on_time =",
        "    CALCULATE (",
        "        COUNTROWS ( fOperations ),",
        "        fOperations[status] = \"Done\",",
        "        fOperations[delay_days] = 0,",
        "        USERELATIONSHIP ( fOperations[planned_end], dCalendar[date] )",
        "    )",
        "RETURN DIVIDE ( on_time, [Operations Done] )",
    ]),
    ("Avg Delay (days)", "2 Execution", "#,0.0", [
        "-- only operations that finished late",
        "CALCULATE (",
        "    AVERAGE ( fOperations[delay_days] ),",
        "    fOperations[delay_days] > 0,",
        "    USERELATIONSHIP ( fOperations[planned_end], dCalendar[date] )",
        ")",
    ]),
    ("Hours Deviation %", "2 Execution", "+0.0%;-0.0%;0.0%", [
        "-- actual vs planned hours of finished operations",
        "VAR planned = CALCULATE ( SUM ( fOperations[planned_hours] ), fOperations[status] = \"Done\" )",
        "VAR actual = CALCULATE ( SUM ( fOperations[actual_hours] ), fOperations[status] = \"Done\" )",
        "RETURN DIVIDE ( actual - planned, planned )",
    ]),
    ("Late Open Operations", "2 Execution", "#,0",
     ["CALCULATE ( COUNTROWS ( fOperations ), fOperations[is_late_open] = \"Yes\" )"]),
]}

RELS = [
    ("fOperations", "order_id", "dOrder", "order_id", True),
    ("fOperations", "work_center_id", "dWorkCenter", "work_center_id", True),
    ("fOperations", "planned_start", "dCalendar", "date", True),
    ("fOperations", "planned_end", "dCalendar", "date", False),
    ("fCapacity", "work_center_id", "dWorkCenter", "work_center_id", True),
    ("fCapacity", "date", "dCalendar", "date", True),
]

STYLE = Style(dark="#14213D", accent="#3A86FF", subtitle="#A9C7FF", bg="#EEF1F6",
              palette=["#3A86FF", "#14213D", "#FCA311", "#2A9D8F", "#C8553D", "#8D99AE"])
FOOT = "AC Metais · synthetic data · snapshot 31 Oct 2026"


def pages():
    s = STYLE
    p1 = Page("capacity_vs_load", "Capacity vs load", s)
    p1.header("Production planning · Capacity vs load",
              "Can the shop deliver the plan, and where is the bottleneck?", FOOT)
    for x, name in zip(CARD_X, ["Utilization %", "Backlog (h)", "Orders in WIP", "Overloaded Weeks"]):
        p1.add("card " + name, x, CARD_Y, CARD_W, CARD_H, p1.card(m(name)))
    p1.add("slicer wc", *SLICER_1, p1.slicer(col("dWorkCenter", "work_center"), "Work center"))
    p1.add("slicer family", *SLICER_2, p1.slicer(col("dOrder", "product_family"), "Product family"))
    p1.add("combo load capacity", 16, 186, 820, 250, p1.chart(
        "lineClusteredColumnComboChart", col("dCalendar", "week_label"), m("Planned Load (h)"),
        "Does the load fit the capacity? (hours by week)", y2=m("Capacity (h)"),
        sort=col("dCalendar", "week_label"), sort_dir="Ascending", labels=False,
        series_colors=[(m("Planned Load (h)"), s.accent), (m("Capacity (h)"), "#FCA311")]))
    p1.add("bar util wc", 848, 186, 416, 250, p1.chart(
        "clusteredBarChart", col("dWorkCenter", "work_center"), m("Utilization %"),
        "Where is the bottleneck? (utilization by work center)", sort=m("Utilization %"), fill=s.dark))
    p1.add("bar backlog wc", 16, 448, 404, 240, p1.chart(
        "clusteredBarChart", col("dWorkCenter", "work_center"), m("Backlog (h)"),
        "How much work is waiting? (backlog hours)", sort=m("Backlog (h)"), fill=s.accent))
    p1.add("table next weeks", 432, 448, 832, 240, p1.table(
        [col("dCalendar", "week_label"), col("dWorkCenter", "work_center"), m("Planned Load (h)"),
         m("Capacity (h)"), m("Utilization %")],
        "Next weeks: which work centers need overtime?", sort=m("Utilization %")),
        filters=[categorical_filter("dCalendar", "horizon", "Plan ahead", "p1 plan ahead")])

    p2 = Page("schedule_adherence", "Schedule adherence", s)
    p2.header("Production planning · Schedule adherence",
              "Are we following the plan, and where do the hours go?", FOOT)
    for x, name in zip(CARD_X, ["Schedule Adherence %", "Avg Delay (days)", "Hours Deviation %",
                                "Late Open Operations"]):
        p2.add("card " + name, x, CARD_Y, CARD_W, CARD_H, p2.card(m(name)))
    p2.add("slicer wc", *SLICER_1, p2.slicer(col("dWorkCenter", "work_center"), "Work center"))
    p2.add("slicer month", *SLICER_2, p2.slicer(col("dCalendar", "month_label"), "Month"))
    p2.add("line adherence", 16, 186, 620, 250, p2.chart(
        "lineChart", col("dCalendar", "week_label"), m("Schedule Adherence %"),
        "Are operations finished on time? (adherence by week)",
        sort=col("dCalendar", "week_label"), sort_dir="Ascending", fill=s.accent, labels=False),
        filters=[categorical_filter("dCalendar", "horizon", "History", "p2 history")])
    p2.add("bar deviation wc", 648, 186, 616, 250, p2.chart(
        "clusteredBarChart", col("dWorkCenter", "work_center"), m("Hours Deviation %"),
        "Which work centers take longer than planned? (actual vs planned hours)",
        sort=m("Hours Deviation %"), fill="#FCA311"))
    p2.add("col delay family", 16, 448, 404, 240, p2.chart(
        "clusteredColumnChart", col("dOrder", "product_family"), m("Schedule Adherence %"),
        "Which products are hardest to plan? (adherence)", sort=m("Schedule Adherence %"),
        sort_dir="Ascending", fill=s.dark))
    p2.add("table late open", 432, 448, 832, 240, p2.table(
        [col("fOperations", "operation_id"), col("dOrder", "customer"), col("dOrder", "product_family"),
         col("dWorkCenter", "work_center"), col("fOperations", "planned_end"),
         col("fOperations", "planned_hours"), col("fOperations", "status")],
        "What is late right now? (open operations past their planned end)",
        sort=col("fOperations", "planned_end"), sort_dir="Ascending"),
        filters=[categorical_filter("fOperations", "is_late_open", "Yes", "p2 late open")])
    return [p1, p2]


if __name__ == "__main__":
    model = Model("production_planning.xlsx", TABLES, MEASURES, RELS, calc=CALC, sort_by=SORT_BY,
                  data_folder="C:\\production-planning-dashboard\\data\\")
    build_project(ROOT / "powerbi", "ProductionPlanning", model, pages(), STYLE, "Production Planning")
