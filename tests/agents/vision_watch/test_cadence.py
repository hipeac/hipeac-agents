"""Tests for the vision-watch weekly cadence: Monday–Sunday, the ISO week."""

from datetime import date, timedelta

import pytest

from hipeac_agents.agents.vision_watch import cadence


MONDAY = date(2026, 10, 5)
W39 = (date(2026, 9, 21), date(2026, 9, 27))


@pytest.mark.parametrize("offset", range(7))
def test_last_closed_window_ends_before_today(offset):
    today = MONDAY + timedelta(days=offset)

    start, end = cadence.last_closed_window(today)

    assert end < today
    assert (start.weekday(), end.weekday()) == (0, 6)
    assert start == end - timedelta(days=6)
    assert (today - end).days <= 7


def test_monday_run():
    """Monday 5 October targets the week that closed the day before."""
    start, end = cadence.last_closed_window(MONDAY)

    assert (start, end) == (date(2026, 9, 28), date(2026, 10, 4))
    assert cadence.weekly_label(end) == "2026-W40"


@pytest.mark.parametrize("today", [date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4)])
def test_friday_saturday_and_sunday_runs_target_the_week_before(today):
    """W40 is still open until the end of Sunday 4 October."""
    assert cadence.last_closed_window(today) == W39


def test_week_window_round_trips_the_label():
    assert cadence.week_window("2026-W39") == W39
    assert cadence.weekly_label(W39[0]) == cadence.weekly_label(W39[1]) == "2026-W39"


def test_year_boundary():
    """2026 has 53 ISO weeks; W53 runs from Monday 28 December to Sunday 3 January."""
    assert cadence.week_window("2026-W53") == (date(2026, 12, 28), date(2027, 1, 3))
    assert cadence.last_closed_window(date(2027, 1, 4)) == (date(2026, 12, 28), date(2027, 1, 3))
    assert cadence.weeks_before("2027-W01", 1) == "2026-W53"


@pytest.mark.parametrize(
    ("week", "back", "expected"),
    [("2026-W39", 8, "2026-W31"), ("2026-W02", 3, "2025-W51"), ("2026-W39", 0, "2026-W39")],
)
def test_weeks_before(week, back, expected):
    assert cadence.weeks_before(week, back) == expected
