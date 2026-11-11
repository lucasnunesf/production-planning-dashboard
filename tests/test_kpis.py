"""The numbers quoted in the README come from the data (pandas mirror of the DAX measures)."""
import subprocess
import sys

import pytest

from conftest import ROOT
from kpi_snapshot import kpis, load


@pytest.fixture(scope="module")
def k():
    return kpis(*load())


def test_headline_numbers(k):
    assert k["operations"] == 3225 and k["orders"] == 754
    assert round(k["utilization"], 2) == 0.76
    assert round(k["adherence"], 3) == 0.719
    assert round(k["avg_delay_days"], 1) == 5.1
    assert round(k["backlog_hours"]) == 2038
    assert k["late_open_operations"] == 27


def test_welding_is_the_bottleneck(k):
    assert round(k["bottleneck_utilization"], 2) == 0.86
    assert k["bottleneck_overloaded_weeks"] == 7
    assert round(k["bottleneck_peak"], 2) == 1.38
    assert round(k["bottleneck_hours_deviation"], 3) == 0.195


def test_overloaded_weeks_measure(k):
    # DAX: SUMX over work centers of the weeks where Utilization % > 1
    assert k["overloaded_weeks_all"] == 13


def test_total_utilization_hides_the_bottleneck(k):
    assert k["utilization"] < 0.8 and k["bottleneck_peak"] > 1.3


def test_snapshot_script_runs():
    out = subprocess.run([sys.executable, "scripts/kpi_snapshot.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert "Welding utilization        86%" in out
