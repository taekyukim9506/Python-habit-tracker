"""Test functional analytics with fixed dates and completion records."""

import unittest
from datetime import datetime

from habit_tracker.analytics import (
    current_streak,
    filter_by_periodicity,
    list_all_habits,
    longest_streak,
    longest_streaks,
)
from habit_tracker.habit import Habit
from habit_tracker.storage import Completion


class TestHabitAnalytics(unittest.TestCase):
    """Check analytics without opening a database or reading the clock."""

    def setUp(self) -> None:
        """Create daily and weekly habits with predictable identifiers."""
        self.daily = Habit(
            "Read",
            "Read ten pages",
            "daily",
            created_at=datetime(2023, 12, 1),
            habit_id=1,
        )
        self.weekly = Habit(
            "Exercise",
            "Complete one workout",
            "weekly",
            created_at=datetime(2023, 12, 1),
            habit_id=2,
        )
        self.habits = [self.daily, self.weekly]

    @staticmethod
    def make_completions(
        habit_id: int, *timestamps: str
    ) -> list[Completion]:
        """Build records from readable ISO timestamps for test scenarios."""
        return [
            Completion(
                completion_id=index,
                habit_id=habit_id,
                completed_at=datetime.fromisoformat(timestamp),
            )
            for index, timestamp in enumerate(timestamps, start=1)
        ]

    def test_list_all_returns_a_separate_list(self) -> None:
        """Listing preserves the supplied order without sharing the list."""
        result = list_all_habits(self.habits)

        self.assertEqual(result, self.habits)
        self.assertIsNot(result, self.habits)

        result.clear()
        self.assertEqual(self.habits, [self.daily, self.weekly])

    def test_filter_daily_and_weekly_habits(self) -> None:
        """Filtering returns only habits with the selected periodicity."""
        self.assertEqual(
            filter_by_periodicity(self.habits, "daily"), [self.daily]
        )
        self.assertEqual(
            filter_by_periodicity(self.habits, "weekly"), [self.weekly]
        )

    def test_filter_normalises_periodicity(self) -> None:
        """Filtering accepts surrounding spaces and different cases."""
        self.assertEqual(
            filter_by_periodicity(self.habits, " WEEKLY "),
            [self.weekly],
        )

    def test_filter_rejects_invalid_periodicity(self) -> None:
        """Unsupported values must not silently produce empty results."""
        for value, error_type in (
            ("monthly", ValueError),
            ("", ValueError),
            (None, TypeError),
            (123, TypeError),
        ):
            with self.subTest(periodicity=value):
                with self.assertRaises(error_type):
                    filter_by_periodicity(self.habits, value)

    def test_empty_inputs(self) -> None:
        """Empty collections produce empty results or zero streaks."""
        as_of = datetime(2024, 1, 10, 12)

        self.assertEqual(list_all_habits([]), [])
        self.assertEqual(filter_by_periodicity([], "daily"), [])
        self.assertEqual(longest_streak(self.daily, [], as_of), 0)
        self.assertEqual(current_streak(self.daily, [], as_of), 0)
        self.assertEqual(longest_streaks([], [], as_of), [])

    def test_daily_longest_streak_handles_gaps(self) -> None:
        """A missed day separates two runs of consecutive completions."""
        records = self.make_completions(
            1,
            "2024-01-01T10:00",
            "2024-01-02T10:00",
            "2024-01-04T10:00",
            "2024-01-05T10:00",
            "2024-01-06T10:00",
        )

        self.assertEqual(
            longest_streak(self.daily, records, datetime(2024, 1, 7)),
            3,
        )

    def test_duplicate_and_unsorted_records_count_once_per_day(self) -> None:
        """Input order and repeated check-offs cannot inflate a streak."""
        records = self.make_completions(
            1,
            "2024-01-03T10:00",
            "2024-01-01T18:00",
            "2024-01-02T10:00",
            "2024-01-01T09:00",
        )

        self.assertEqual(
            longest_streak(self.daily, records, datetime(2024, 1, 4)),
            3,
        )

    def test_daily_streak_crosses_year_boundary(self) -> None:
        """Consecutive dates remain consecutive when the year changes."""
        records = self.make_completions(
            1,
            "2023-12-31T10:00",
            "2024-01-01T10:00",
            "2024-01-02T10:00",
        )

        self.assertEqual(
            longest_streak(self.daily, records, datetime(2024, 1, 3)),
            3,
        )

    def test_daily_streak_includes_leap_day(self) -> None:
        """February 29 is a normal daily period in a leap year."""
        records = self.make_completions(
            1,
            "2024-02-28T10:00",
            "2024-02-29T10:00",
            "2024-03-01T10:00",
        )

        self.assertEqual(
            longest_streak(self.daily, records, datetime(2024, 3, 2)),
            3,
        )

    def test_weekly_streak_uses_calendar_weeks(self) -> None:
        """Sunday and the following Monday belong to different weeks."""
        records = self.make_completions(
            2,
            "2024-01-07T10:00",
            "2024-01-08T10:00",
            "2024-01-14T18:00",
            "2024-01-15T10:00",
        )

        self.assertEqual(
            longest_streak(self.weekly, records, datetime(2024, 1, 16)),
            3,
        )

    def test_missed_week_breaks_weekly_streak(self) -> None:
        """A week without a completion separates weekly streaks."""
        records = self.make_completions(
            2,
            "2024-01-01T10:00",
            "2024-01-15T10:00",
            "2024-01-22T10:00",
        )

        self.assertEqual(
            longest_streak(self.weekly, records, datetime(2024, 1, 23)),
            2,
        )

    def test_current_daily_streak_allows_unfinished_today(self) -> None:
        """Yesterday's streak remains active while today is unfinished."""
        records = self.make_completions(
            1,
            "2024-01-01T10:00",
            "2024-01-02T10:00",
            "2024-01-03T10:00",
        )

        self.assertEqual(
            current_streak(self.daily, records, datetime(2024, 1, 4, 12)),
            3,
        )
        self.assertEqual(
            current_streak(self.daily, records, datetime(2024, 1, 5)),
            0,
        )

    def test_current_daily_streak_includes_today(self) -> None:
        """Completing today extends the active daily streak."""
        records = self.make_completions(
            1,
            "2024-01-01T10:00",
            "2024-01-02T10:00",
            "2024-01-03T10:00",
        )

        self.assertEqual(
            current_streak(self.daily, records, datetime(2024, 1, 3, 12)),
            3,
        )

    def test_current_weekly_streak_allows_unfinished_week(self) -> None:
        """The previous streak expires only after a full week is missed."""
        records = self.make_completions(
            2,
            "2024-01-01T10:00",
            "2024-01-08T10:00",
        )

        self.assertEqual(
            current_streak(
                self.weekly, records, datetime(2024, 1, 21, 23, 59)
            ),
            2,
        )
        self.assertEqual(
            current_streak(self.weekly, records, datetime(2024, 1, 22)),
            0,
        )

    def test_records_are_filtered_by_habit_and_reference_time(self) -> None:
        """Other habits and later check-offs cannot extend the result."""
        records = self.make_completions(
            1, "2024-01-01T10:00", "2024-01-02T18:00"
        )
        records += self.make_completions(2, "2024-01-02T10:00")
        as_of = datetime(2024, 1, 2, 12)

        self.assertEqual(longest_streak(self.daily, records, as_of), 1)
        self.assertEqual(current_streak(self.daily, records, as_of), 1)

    def test_creation_time_limits_eligible_records(self) -> None:
        """A valid completion in the partial creation day still counts."""
        habit = Habit(
            "Read",
            "Read ten pages",
            "daily",
            created_at=datetime(2024, 1, 2, 12),
            habit_id=3,
        )
        records = self.make_completions(
            3,
            "2024-01-01T10:00",
            "2024-01-02T11:00",
            "2024-01-02T12:00",
            "2024-01-03T10:00",
        )

        self.assertEqual(
            longest_streak(habit, records, datetime(2024, 1, 3, 12)),
            2,
        )

    def test_longest_across_habits_returns_all_ties_in_id_order(self) -> None:
        """Tied results retain their habits so their units remain known."""
        records = self.make_completions(
            1, "2024-01-01T10:00", "2024-01-02T10:00"
        )
        records += self.make_completions(
            2, "2024-01-01T10:00", "2024-01-08T10:00"
        )

        result = longest_streaks(
            [self.weekly, self.daily],
            records,
            datetime(2024, 1, 10),
        )

        self.assertEqual(result, [(self.daily, 2), (self.weekly, 2)])

    def test_longest_across_habits_returns_only_winners(self) -> None:
        """Habits with shorter streaks are excluded from the result."""
        records = self.make_completions(
            1, "2024-01-01T10:00", "2024-01-02T10:00"
        )
        records += self.make_completions(2, "2024-01-01T10:00")

        self.assertEqual(
            longest_streaks(
                self.habits, records, datetime(2024, 1, 10)
            ),
            [(self.daily, 2)],
        )

    def test_habits_without_completions_tie_at_zero(self) -> None:
        """Existing habits with no history all have a longest streak of zero."""
        self.assertEqual(
            longest_streaks(
                [self.weekly, self.daily], [], datetime(2024, 1, 10)
            ),
            [(self.daily, 0), (self.weekly, 0)],
        )

    def test_analytics_are_repeatable_and_do_not_change_inputs(self) -> None:
        """Repeated calculations preserve input order and object values."""
        records = self.make_completions(
            1, "2024-01-02T10:00", "2024-01-01T10:00"
        )
        original_records = list(records)
        original_habits = list(self.habits)
        original_details = [
            (h.name, h.description, h.periodicity, h.created_at, h.habit_id)
            for h in self.habits
        ]
        as_of = datetime(2024, 1, 3, 12)

        first_result = longest_streaks(self.habits, records, as_of)
        second_result = longest_streaks(self.habits, records, as_of)
        filter_by_periodicity(self.habits, "daily")
        current_streak(self.daily, records, as_of)

        self.assertEqual(first_result, second_result)
        self.assertEqual(records, original_records)
        self.assertEqual(self.habits, original_habits)
        self.assertEqual(
            [
                (h.name, h.description, h.periodicity, h.created_at, h.habit_id)
                for h in self.habits
            ],
            original_details,
        )


if __name__ == "__main__":
    unittest.main()