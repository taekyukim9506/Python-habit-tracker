"""Provide pure functions for habit filtering and streak calculations."""

from collections.abc import Iterable
from datetime import datetime

from habit_tracker.habit import Habit
from habit_tracker.storage import Completion

def list_all_habits(habits: Iterable[Habit]) -> list[Habit]:
    """Return a list of all habits, preserving the supplied order."""
    return list(habits)


def filter_by_periodicity(
    habits: Iterable[Habit],
    periodicity: str,
) -> list[Habit]:
    """Return habits matching a daily or weekly schedule."""
    if not isinstance(periodicity, str):
        raise TypeError("Periodicity must be a string.")

    cleaned_periodicity = periodicity.strip().lower()

    if cleaned_periodicity not in Habit.VALID_PERIODICITIES:
        raise ValueError("Periodicity must be 'daily' or 'weekly'.")

    return list(
        filter(
            lambda habit: habit.periodicity == cleaned_periodicity,
            habits,
        )
    )


def _validate_reference_time(as_of: datetime) -> None:
    """Require a local datetime consistent with stored timestamps."""
    if not isinstance(as_of, datetime):
        raise TypeError("Reference time must be a datetime object.")

    if as_of.tzinfo is not None:
        raise ValueError(
            "Reference time must use local time without a timezone."
        )


def _period_number(timestamp: datetime, periodicity: str) -> int:
    """Convert a timestamp into a daily or Monday-based weekly number."""
    day_number = timestamp.date().toordinal()

    if periodicity == "daily":
        return day_number

    # Ordinal day 1 was a Monday, so each group of seven is one week.
    return (day_number - 1) // 7


def _completed_periods(
    habit: Habit,
    completions: Iterable[Completion],
    as_of: datetime,
) -> list[int]:
    """Return sorted, unique completed periods for one saved habit.

    Ignore other habits, records before creation, and records later
    than the reference time. A completion exactly at either boundary
    is included.
    """
    _validate_reference_time(as_of)

    if habit.habit_id is None:
        raise ValueError("Streak calculations require a saved habit.")

    eligible_records = filter(
        lambda record: (
            record.habit_id == habit.habit_id
            and habit.created_at <= record.completed_at <= as_of
        ),
        completions,
    )

    periods = map(
        lambda record: _period_number(
            record.completed_at, habit.periodicity
        ),
        eligible_records,
    )

    # Repeated check-offs in one period count only once.
    return sorted(set(periods))


def longest_streak(
    habit: Habit,
    completions: Iterable[Completion],
    as_of: datetime,
) -> int:
    """Return the longest run of completed daily or weekly periods.

    A gap starts a new run. Empty history returns zero. The result
    counts periods, so its unit depends on the habit's periodicity.
    """
    periods = _completed_periods(habit, completions, as_of)
    longest = 0
    running = 0
    previous = None

    for period in periods:
        if previous is not None and period == previous + 1:
            running += 1
        else:
            running = 1

        longest = max(longest, running)
        previous = period

    return longest


def current_streak(
    habit: Habit,
    completions: Iterable[Completion],
    as_of: datetime,
) -> int:
    """Return the streak active at the supplied reference time.

    If the current period is unfinished, a streak ending in the
    previous period remains active. Missing an entire period breaks
    the streak.
    """
    periods = _completed_periods(habit, completions, as_of)

    if not periods:
        return 0

    current_period = _period_number(as_of, habit.periodicity)
    latest_completed = periods[-1]

    if latest_completed < current_period - 1:
        return 0

    running = 1

    # Walk backwards from the most recent completion until a gap appears.
    for index in range(len(periods) - 2, -1, -1):
        if periods[index] != periods[index + 1] - 1:
            break

        running += 1

    return running


def longest_streaks(
    habits: Iterable[Habit],
    completions: Iterable[Completion],
    as_of: datetime,
) -> list[tuple[Habit, int]]:
    """Return every habit tied for the highest longest-streak count.
    Results are ordered by habit ID. Each pair contains the habit and its streak length, preserving the daily or weekly unit.
    No habits returns an empty list. If all histories are empty, every supplied habit ties at zero."""
    _validate_reference_time(as_of)

    # Materialise records once so every habit receives the same data,
    # including when the caller supplies a generator.
    records = tuple(completions)

    results = [
        (habit, longest_streak(habit, records, as_of))
        for habit in habits
    ]

    if not results:
        return []

    highest = max(length for _, length in results)

    winners = filter(
        lambda result: result[1] == highest,
        results,
    )

    return sorted(winners, key=lambda result: result[0].habit_id)