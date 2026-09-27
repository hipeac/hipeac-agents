"""Tests for the vision-watch weekly cadence."""

from datetime import date, timedelta

import pytest

from hipeac_agents.agents.vision_watch import cadence


FRIDAY = date(2026, 9, 25)


@pytest.mark.parametrize("offset", range(7))
def test_last_closed_window_never_ends_after_today(offset):
    today = FRIDAY + timedelta(days=offset)

    start, end = cadence.last_closed_window(today)

    assert end <= today
    assert end.weekday() == 4
    assert start == end - timedelta(days=6)
    assert (today - end).days < 7


def test_friday_closes_its_own_window():
    assert cadence.last_closed_window(FRIDAY) == (date(2026, 9, 19), FRIDAY)


def test_thursday_targets_the_previous_week():
    assert cadence.last_closed_window(date(2026, 10, 1)) == (date(2026, 9, 19), FRIDAY)


@pytest.mark.parametrize(
    ("week", "back", "expected"),
    [("2026-W39", 8, "2026-W31"), ("2026-W02", 3, "2025-W51"), ("2026-W39", 0, "2026-W39")],
)
def test_weeks_before(week, back, expected):
    assert cadence.weeks_before(week, back) == expected
