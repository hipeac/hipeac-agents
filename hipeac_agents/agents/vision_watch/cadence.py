"""The vision-watch agent's weekly cadence: windows and file labels.

Agent-owned: the Monday-through-Sunday cycle is this agent's editorial
calendar, not a storage rule. A week is exactly an ISO week, so its label is
the ISO week of any of its days. Generic storage primitives live in
``hipeac_agents.storage``.
"""

from datetime import date, timedelta


def weekly_label(day: date) -> str:
    """Compute the weekly file label of the week a day belongs to.

    :param day: Any day of the week, usually the window's closing Sunday.
    :returns: A label such as ``"2026-W24"``.
    """
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def current_window(today: date) -> tuple[date, date]:
    """Compute the weekly window a given day falls in (Monday through Sunday).

    :param today: Any day within the week.
    :returns: A ``(window_start, window_end)`` pair; ``window_end`` is the
        closing Sunday.
    """
    window_start = today - timedelta(days=today.weekday())
    return window_start, window_start + timedelta(days=6)


def week_window(week: str) -> tuple[date, date]:
    """Return the Monday and Sunday of a labelled week.

    :param week: A week label such as ``"2026-W39"``.
    :returns: The week's ``(monday, sunday)``.
    """
    year, number = week.split("-W")
    monday = date.fromisocalendar(int(year), int(number), 1)
    return monday, monday + timedelta(days=6)


def weeks_before(week: str, weeks: int) -> str:
    """Return the label of the week a number of weeks before another.

    :param week: A week label such as ``"2026-W39"``.
    :param weeks: How many weeks back.
    :returns: The earlier week's label, e.g. ``"2026-W31"`` for 8 weeks back.
    """
    monday, _sunday = week_window(week)
    return weekly_label(monday - timedelta(weeks=weeks))


def last_closed_window(today: date) -> tuple[date, date]:
    """Compute the most recently closed weekly window as of a given day.

    A week closes at the end of its Sunday, so on any day, Sunday included,
    the last closed week is the one before today's: a Monday run targets the
    week that ended the day before.

    :param today: The day of the run.
    :returns: A ``(window_start, window_end)`` pair with ``window_end < today``.
    """
    window_start, window_end = current_window(today)
    return window_start - timedelta(days=7), window_end - timedelta(days=7)
