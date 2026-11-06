"""Provide pure functions for habit filtering and streak calculations."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

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

@dataclass(frozen=True)
class AttentionSummary:
    """Describe a habit's performance over eligible completed periods.

    A completion rate of None means there are no eligible periods.
    The interface can display this as "Insufficient data".
    """

    habit: Habit
    eligible_periods: int
    completed_periods: int
    missed_periods: int
    completion_rate: float | None


def due_habits(
    habits: Iterable[Habit],
    completions: Iterable[Completion],
    as_of: datetime,
) -> list[Habit]:
    """Return existing habits not completed in their current period.

    Newly created habits are immediately due. Habits created after
    the reference time are excluded. Results preserve input order.
    """
    _validate_reference_time(as_of)
    records = tuple(completions)
    result = []

    for habit in habits:
        if habit.created_at > as_of:
            continue

        completed = _completed_periods(habit, records, as_of)
        current_period = _period_number(as_of, habit.periodicity)

        if current_period not in completed:
            result.append(habit)

    return result


def _period_start(timestamp: datetime, periodicity: str) -> datetime:
    """Return midnight at the start of the containing day or week."""
    midnight = timestamp.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if periodicity == "weekly":
        return midnight - timedelta(days=midnight.weekday())

    return midnight


def attention_summary(
    habit: Habit,
    completions: Iterable[Completion],
    as_of: datetime,
) -> AttentionSummary:
    """Summarise the previous four completed Monday-to-Sunday weeks.

    Daily habits have at most 28 eligible periods; weekly habits have
    at most four. Periods before creation and a partial creation
    period are excluded. The current calendar week is not assessed.
    """
    _validate_reference_time(as_of)

    if habit.habit_id is None:
        raise ValueError("Attention calculations require a saved habit.")

    window_end = _period_start(as_of, "weekly")
    window_start = window_end - timedelta(weeks=4)

    period_length = timedelta(
        days=1 if habit.periodicity == "daily" else 7
    )
    first_full_period = _period_start(
        habit.created_at, habit.periodicity
    )

    # Only a habit created exactly at the boundary has a full first period.
    if habit.created_at > first_full_period:
        first_full_period += period_length

    eligible_start = max(window_start, first_full_period)

    if eligible_start >= window_end:
        return AttentionSummary(
            habit=habit,
            eligible_periods=0,
            completed_periods=0,
            missed_periods=0,
            completion_rate=None,
        )

    eligible_count = (window_end - eligible_start) // period_length

    first_period = _period_number(eligible_start, habit.periodicity)
    end_period = _period_number(window_end, habit.periodicity)
    completed = _completed_periods(habit, completions, as_of)

    # The upper boundary is exclusive: this week's records do not count.
    completed_count = sum(
        1 for period in completed
        if first_period <= period < end_period
    )

    missed_count = eligible_count - completed_count
    completion_rate = completed_count / eligible_count * 100

    return AttentionSummary(
        habit=habit,
        eligible_periods=eligible_count,
        completed_periods=completed_count,
        missed_periods=missed_count,
        completion_rate=completion_rate,
    )


def habits_needing_attention(
    habits: Iterable[Habit],
    completions: Iterable[Completion],
    as_of: datetime,
) -> list[AttentionSummary]:
    """Return habits with missed eligible periods, lowest rate first.

    Perfect histories and histories with insufficient data are
    excluded. Equal completion rates are ordered by habit ID.
    """
    _validate_reference_time(as_of)
    records = tuple(completions)

    summaries = map(
        lambda habit: attention_summary(habit, records, as_of),
        habits,
    )

    needing_attention = filter(
        lambda summary: summary.missed_periods > 0,
        summaries,
    )

    return sorted(
        needing_attention,
        key=lambda summary: (
            summary.completion_rate,
            summary.habit.habit_id,
        ),
    )