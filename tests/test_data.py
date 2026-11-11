"""The synthetic dataset: reproducible, consistent keys, and the planning rules hold."""
import pandas as pd
import pytest

from conftest import ROOT, load

DATA = ROOT / "data" / "production_planning.xlsx"
SNAPSHOT = pd.Timestamp("2026-10-31")


@pytest.fixture(scope="module")
def x():
    return load(DATA)


def test_generator_is_reproducible(fresh):
    work, logs = fresh
    assert "3,225 operations / 754 orders" in logs["generate"]
    new = load(work / "data" / "production_planning.xlsx")
    for sheet, df in load(DATA).items():
        pd.testing.assert_frame_equal(new[sheet], df, obj=sheet)


def test_keys(x):
    ops = x["fOperations"]
    assert ops.operation_id.is_unique and x["dOrder"].order_id.is_unique
    assert ops.order_id.isin(x["dOrder"].order_id).all()
    assert ops.work_center_id.isin(x["dWorkCenter"].work_center_id).all()
    assert x["fCapacity"].work_center_id.isin(x["dWorkCenter"].work_center_id).all()
    assert not x["fCapacity"].duplicated(["date", "work_center_id"]).any()
    assert x["dCalendar"].date.is_unique


def test_routing_follows_the_work_center_sequence(x):
    ops = x["fOperations"].merge(x["dWorkCenter"], on="work_center_id")
    for _, o in ops.sort_values("operation_sequence").groupby("order_id"):
        assert o.routing_sequence.is_monotonic_increasing
        assert o.planned_start.is_monotonic_increasing
        assert (o.planned_start.iloc[1:].values > o.planned_end.iloc[:-1].values).all()


def test_planned_dates_are_working_days(x):
    ops = x["fOperations"]
    assert (ops.planned_end >= ops.planned_start).all()
    assert (ops.planned_start.dt.dayofweek < 5).all() and (ops.planned_end.dt.dayofweek < 5).all()


def test_status_matches_actuals(x):
    ops = x["fOperations"]
    done = ops.status == "Done"
    assert set(ops.status) == {"Done", "In progress", "Planned"}
    assert ops.loc[done, ["actual_end", "actual_hours"]].notna().all().all()
    assert ops.loc[~done, ["actual_end", "actual_hours"]].isna().all().all()
    assert (ops.loc[done, "actual_end"] <= SNAPSHOT).all()
    assert (ops.loc[ops.status == "Planned", "planned_start"] > SNAPSHOT - pd.Timedelta(days=60)).all()


def test_holidays_have_no_capacity(x):
    cap = x["fCapacity"]
    for day in ["2026-09-07", "2026-10-12", "2026-11-02", "2026-11-20"]:
        assert cap.loc[cap.date == day, "capacity_hours"].sum() == 0
    assert (cap.date.dt.dayofweek < 5).all()


def test_calendar_covers_the_plan(x):
    cal, ops = x["dCalendar"], x["fOperations"]
    assert cal.date.min() <= ops.planned_start.min() and cal.date.max() >= ops.planned_start.max()
    assert set(cal.loc[cal.date > SNAPSHOT, "horizon"]) == {"Plan ahead"}
    # one sort number per week label, otherwise Power BI refuses the sort-by column
    assert cal.groupby("week_label").week_start_number.nunique().max() == 1
