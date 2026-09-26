"""The vision-watch agent's weekly cadence: windows and file labels.

Agent-owned: the Saturday-through-Friday cycle is this agent's editorial
calendar, not a storage rule. Generic storage primitives live in
``hipeac_agents.storage``.
"""

from datetime import date, timedelta


def weekly_label(closing_friday: date) -> str:
    """Compute the weekly file label for a harvest window.

    The weekly cycle runs Saturday through Friday; the label's ``Www`` is the
    ISO week number of the window's closing Friday.

    :param closing_friday: The closing Friday of the weekly window.
    :returns: A label such as ``"2026-W24"``.
    """
    iso = closing_friday.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def current_window(today: date) -> tuple[date, date]:
    """Compute the weekly window a given day falls in (Saturday through Friday).

    :param today: Any day within the week.
    :returns: A ``(window_start, window_end)`` pair; ``window_end`` is the
        closing Friday.
    """
    offset_to_saturday = (today.weekday() - 5) % 7
    window_start = today - timedelta(days=offset_to_saturday)
    return window_start, window_start + timedelta(days=6)


def last_closed_window(today: date) -> tuple[date, date]:
    """Compute the most recently closed weekly window as of a given day.

    A Friday closes its own window; any other day belongs to a window still
    open, so the last closed one is the window ending the previous Friday.

    :param today: The day of the run.
    :returns: A ``(window_start, window_end)`` pair with ``window_end <= today``.
    """
    window_start, window_end = current_window(today)
    if window_end > today:
        return window_start - timedelta(days=7), window_end - timedelta(days=7)
    return window_start, window_end
