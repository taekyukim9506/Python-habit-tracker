"""Test due habits and completion summaries over four completed weeks."""

import unittest
from datetime import datetime

from habit_tracker.analytics import (
    attention_summary,
    due_habits,
    habits_needing_attention,
)
from habit_tracker.habit import Habit
from habit_tracker.storage import Completion


class TestHabitAttention(unittest.TestCase):
    """Check date windows, completion rates, and attention ranking."""

    def setUp(self) -> None:
        """Use January 1–28, 2024 as four completed calendar weeks."""
        self.as_of = datetime(2024, 1, 29, 12)
        self.daily = self.make_habit(1, "daily")
        self.weekly = self.make_habit(2, "weekly")

    @staticmethod
    def make_habit(
        habit_id: int,
        periodicity: str,
        created_at: datetime = datetime(2023, 12, 1),
    ) -> Habit:
        """Create a saved habit without opening a database."""
        return Habit(
            name=f"Habit {habit_id}",
            description="Complete the planned task",
            periodicity=periodicity,
            created_at=created_at,
            habit_id=habit_id,
        )

    @staticmethod
    def make_records(
        habit_id: int, *timestamps: str
    ) -> list[Completion]:
        """Build completion records from readable timestamps."""
        return [
            Completion(index, habit_id, datetime.fromisoformat(timestamp))
            for index, timestamp in enumerate(timestamps, start=1)
        ]

    def test_due_habits_without_completions(self) -> None:
        """Existing habits are due when their current periods are empty."""
        result = due_habits(
            [self.daily, self.weekly], [], self.as_of
        )

        self.assertEqual(result, [self.daily, self.weekly])

    def test_current_period_completions_remove_due_habits(self) -> None:
        """Today's and this week's completions satisfy their schedules."""
        records = self.make_records(1, "2024-01-29T10:00")
        records += self.make_records(2, "2024-01-29T11:00")

        self.assertEqual(
            due_habits([self.daily, self.weekly], records, self.as_of),
            [],
        )

    def test_previous_period_does_not_satisfy_current_period(self) -> None:
        """Sunday completions do not satisfy a new Monday."""
        records = self.make_records(1, "2024-01-28T10:00")
        records += self.make_records(2, "2024-01-28T11:00")

        self.assertEqual(
            due_habits([self.daily, self.weekly], records, self.as_of),
            [self.daily, self.weekly],
        )

    def test_weekly_completion_remains_valid_until_sunday(self) -> None:
        """A Monday check-off satisfies the same week's Sunday."""
        records = self.make_records(2, "2024-01-29T10:00")

        self.assertEqual(
            due_habits(
                [self.weekly], records, datetime(2024, 2, 4, 23, 59)
            ),
            [],
        )

    def test_due_ignores_later_records_and_future_habits(self) -> None:
        """Historical evaluation uses only habits and events already present."""
        future_habit = self.make_habit(
            3, "daily", datetime(2024, 1, 30)
        )
        records = self.make_records(1, "2024-01-29T18:00")

        self.assertEqual(
            due_habits([self.daily, future_habit], records, self.as_of),
            [self.daily],
        )

    def test_new_habit_is_due_immediately(self) -> None:
        """A partial creation period can still be completed."""
        habit = self.make_habit(
            3, "daily", datetime(2024, 1, 29, 11)
        )

        self.assertEqual(due_habits([habit], [], self.as_of), [habit])

    def test_daily_summary_counts_unique_completed_days(self) -> None:
        """Repeated check-offs do not increase the completion percentage."""
        records = self.make_records(
            1,
            "2024-01-01T10:00",
            "2024-01-01T18:00",
            "2024-01-02T10:00",
        )

        result = attention_summary(self.daily, records, self.as_of)

        self.assertEqual(result.habit, self.daily)
        self.assertEqual(result.eligible_periods, 28)
        self.assertEqual(result.completed_periods, 2)
        self.assertEqual(result.missed_periods, 26)
        self.assertAlmostEqual(result.completion_rate, 2 / 28 * 100)

    def test_weekly_summary_counts_completed_calendar_weeks(self) -> None:
        """Three completed weeks out of four produce a 75% rate."""
        records = self.make_records(
            2,
            "2024-01-01T10:00",
            "2024-01-07T10:00",
            "2024-01-15T10:00",
            "2024-01-28T10:00",
        )

        result = attention_summary(self.weekly, records, self.as_of)

        self.assertEqual(result.eligible_periods, 4)
        self.assertEqual(result.completed_periods, 3)
        self.assertEqual(result.missed_periods, 1)
        self.assertEqual(result.completion_rate, 75.0)

    def test_summary_excludes_outside_window_and_other_habits(self) -> None:
        """Only the selected habit's records within the window count."""
        records = self.make_records(
            1,
            "2023-12-31T23:59",
            "2024-01-01T00:00",
            "2024-01-28T23:59",
            "2024-01-29T00:00",
        )
        records += self.make_records(2, "2024-01-02T10:00")

        result = attention_summary(self.daily, records, self.as_of)

        self.assertEqual(result.completed_periods, 2)
        self.assertEqual(result.missed_periods, 26)

    def test_window_stays_fixed_through_current_week(self) -> None:
        """Advancing within the current week does not move the window."""
        records = self.make_records(1, "2024-01-01T10:00")

        monday_result = attention_summary(
            self.daily, records, self.as_of
        )
        sunday_result = attention_summary(
            self.daily, records, datetime(2024, 2, 4, 23, 59)
        )

        self.assertEqual(monday_result, sunday_result)

    def test_partial_creation_day_is_excluded(self) -> None:
        """A habit created at noon is assessed from the following day."""
        habit = self.make_habit(
            3, "daily", datetime(2024, 1, 15, 12)
        )
        records = self.make_records(
            3,
            "2024-01-15T18:00",
            "2024-01-16T10:00",
        )

        result = attention_summary(habit, records, self.as_of)

        self.assertEqual(result.eligible_periods, 13)
        self.assertEqual(result.completed_periods, 1)
        self.assertEqual(result.missed_periods, 12)

    def test_partial_creation_week_is_excluded(self) -> None:
        """A Wednesday creation makes the next Monday the first full week."""
        habit = self.make_habit(
            3, "weekly", datetime(2024, 1, 10, 12)
        )
        records = self.make_records(
            3,
            "2024-01-11T10:00",
            "2024-01-15T10:00",
        )

        result = attention_summary(habit, records, self.as_of)

        self.assertEqual(result.eligible_periods, 2)
        self.assertEqual(result.completed_periods, 1)
        self.assertEqual(result.completion_rate, 50.0)

    def test_creation_at_period_start_includes_that_period(self) -> None:
        """A habit created exactly at a period boundary gets a full period."""
        for periodicity, expected in (("daily", 14), ("weekly", 2)):
            with self.subTest(periodicity=periodicity):
                habit = self.make_habit(
                    3, periodicity, datetime(2024, 1, 15)
                )

                result = attention_summary(habit, [], self.as_of)

                self.assertEqual(result.eligible_periods, expected)
                self.assertEqual(result.missed_periods, expected)
                self.assertEqual(result.completion_rate, 0.0)

    def test_no_eligible_periods_means_insufficient_data(self) -> None:
        """A new habit must not receive a misleading zero-percent score."""
        habit = self.make_habit(
            3, "daily", datetime(2024, 1, 29, 10)
        )

        result = attention_summary(habit, [], self.as_of)

        self.assertEqual(result.eligible_periods, 0)
        self.assertEqual(result.completed_periods, 0)
        self.assertEqual(result.missed_periods, 0)
        self.assertIsNone(result.completion_rate)

    def test_attention_ranks_by_rate_then_habit_id(self) -> None:
        """Lower completion rates come first, with stable ordering for ties."""
        third = self.make_habit(3, "weekly")
        records = self.make_records(2, "2024-01-01T10:00")

        results = habits_needing_attention(
            [third, self.weekly, self.daily], records, self.as_of
        )

        self.assertEqual(
            [result.habit.habit_id for result in results], [1, 3, 2]
        )
        self.assertEqual(
            [result.completion_rate for result in results],
            [0.0, 0.0, 25.0],
        )

    def test_attention_excludes_perfect_and_insufficient_histories(self) -> None:
        """Only habits with eligible missed periods need attention."""
        new_habit = self.make_habit(
            3, "daily", datetime(2024, 1, 29, 10)
        )
        records = self.make_records(
            2,
            "2024-01-01T10:00",
            "2024-01-08T10:00",
            "2024-01-15T10:00",
            "2024-01-22T10:00",
        )

        results = habits_needing_attention(
            [self.daily, self.weekly, new_habit], records, self.as_of
        )

        self.assertEqual(
            [result.habit.habit_id for result in results], [1]
        )

    def test_empty_collections(self) -> None:
        """An application without habits has nothing due or needing attention."""
        self.assertEqual(due_habits([], [], self.as_of), [])
        self.assertEqual(habits_needing_attention([], [], self.as_of), [])

    def test_results_are_repeatable_without_changing_inputs(self) -> None:
        """Calculations preserve the supplied lists and their order."""
        habits = [self.weekly, self.daily]
        records = self.make_records(
            1, "2024-01-02T10:00", "2024-01-01T10:00"
        )
        original_habits = list(habits)
        original_records = list(records)

        first = habits_needing_attention(habits, records, self.as_of)
        second = habits_needing_attention(habits, records, self.as_of)
        due_habits(habits, records, self.as_of)

        self.assertEqual(first, second)
        self.assertEqual(habits, original_habits)
        self.assertEqual(records, original_records)


if __name__ == "__main__":
    unittest.main()