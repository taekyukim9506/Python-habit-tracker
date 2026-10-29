"""Test completion storage, undo operations, and database relationships."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from habit_tracker.habit import Habit
from habit_tracker.storage import HabitRepository


class TestCompletionStorage(unittest.TestCase):
    """Verify check-off behaviour using an isolated database."""

    def setUp(self) -> None:
        """Create two habits so tests can also check data separation."""
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)

        self.database_path = (
            Path(temporary_directory.name) / "test_completions.db"
        )
        self.repository = HabitRepository(self.database_path)
        self.addCleanup(self.repository.close)

        self.created_at = datetime(2020, 1, 1, 9, 0)
        self.completed_at = datetime(2020, 1, 2, 10, 30, 0, 123456)

        self.first = self.repository.add_habit(
            Habit(
                "Study Python",
                "Practise for 30 minutes",
                "daily",
                created_at=self.created_at,
            )
        )
        self.second = self.repository.add_habit(
            Habit(
                "Review goals",
                "Review progress for the week",
                "weekly",
                created_at=self.created_at,
            )
        )

    def test_new_habit_has_empty_history(self) -> None:
        """A habit starts without completion records."""
        self.assertEqual(
            self.repository.list_completions(self.first.habit_id), []
        )

    def test_save_and_load_completion(self) -> None:
        """Saving preserves the habit ID and exact timestamp."""
        saved = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )

        history = self.repository.list_completions(self.first.habit_id)

        self.assertGreater(saved.completion_id, 0)
        self.assertEqual(saved.habit_id, self.first.habit_id)
        self.assertEqual(saved.completed_at, self.completed_at)
        self.assertEqual(history, [saved])

    def test_default_completion_time(self) -> None:
        """Omitting the timestamp records the current local time."""
        before = datetime.now()

        saved = self.repository.add_completion(self.first.habit_id)

        after = datetime.now()
        self.assertGreaterEqual(saved.completed_at, before)
        self.assertLessEqual(saved.completed_at, after)
        self.assertIsNone(saved.completed_at.tzinfo)

    def test_completion_at_creation_time_is_allowed(self) -> None:
        """A habit can be completed immediately after it is created."""
        saved = self.repository.add_completion(
            self.first.habit_id, self.created_at
        )

        self.assertEqual(saved.completed_at, self.created_at)

    def test_history_is_chronological(self) -> None:
        """History is sorted by timestamp rather than insertion order."""
        later = self.repository.add_completion(
            self.first.habit_id, self.completed_at + timedelta(days=1)
        )
        earlier = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )

        self.assertEqual(
            self.repository.list_completions(self.first.habit_id),
            [earlier, later],
        )

    def test_repeated_checkoffs_have_separate_ids(self) -> None:
        """Equal timestamps remain separate records in a stable order."""
        first = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )
        second = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )

        self.assertNotEqual(first.completion_id, second.completion_id)
        self.assertEqual(
            self.repository.list_completions(self.first.habit_id),
            [first, second],
        )

    def test_reject_invalid_times_without_saving(self) -> None:
        """Rejected values leave the completion history unchanged."""
        invalid_values = (
            ("2020-01-02", TypeError),
            (123, TypeError),
            (False, TypeError),
            (self.completed_at.date(), TypeError),
            (
                self.completed_at.replace(tzinfo=timezone.utc),
                ValueError,
            ),
            (self.created_at - timedelta(microseconds=1), ValueError),
            (datetime.now() + timedelta(days=1), ValueError),
        )

        for value, error_type in invalid_values:
            with self.subTest(completed_at=value):
                with self.assertRaises(error_type):
                    self.repository.add_completion(
                        self.first.habit_id, value
                    )

                self.assertEqual(
                    self.repository.list_completions(self.first.habit_id),
                    [],
                )

    def test_missing_habit_cannot_receive_completion(self) -> None:
        """A check-off must belong to an existing habit."""
        with self.assertRaises(LookupError):
            self.repository.add_completion(999, self.completed_at)

        self.assertEqual(
            self.repository.list_completions(self.first.habit_id), []
        )

    def test_undo_removes_only_selected_completion(self) -> None:
        """Undo leaves other check-offs for the same habit untouched."""
        first = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )
        second = self.repository.add_completion(
            self.first.habit_id, self.completed_at + timedelta(hours=1)
        )

        self.repository.delete_completion(
            self.first.habit_id, first.completion_id
        )

        self.assertEqual(
            self.repository.list_completions(self.first.habit_id),
            [second],
        )

    def test_undo_cannot_delete_another_habits_completion(self) -> None:
        """A completion ID alone cannot bypass habit ownership."""
        saved = self.repository.add_completion(
            self.second.habit_id, self.completed_at
        )

        with self.assertRaises(LookupError):
            self.repository.delete_completion(
                self.first.habit_id, saved.completion_id
            )

        self.assertEqual(
            self.repository.list_completions(self.second.habit_id),
            [saved],
        )

    def test_reject_invalid_completion_ids(self) -> None:
        """Invalid undo requests preserve existing history."""
        saved = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )
        invalid_ids = (
            (True, TypeError),
            ("1", TypeError),
            (1.0, TypeError),
            (None, TypeError),
            (0, ValueError),
            (-1, ValueError),
        )

        for value, error_type in invalid_ids:
            with self.subTest(completion_id=value):
                with self.assertRaises(error_type):
                    self.repository.delete_completion(
                        self.first.habit_id, value
                    )

                self.assertEqual(
                    self.repository.list_completions(self.first.habit_id),
                    [saved],
                )

    def test_completion_survives_reopening(self) -> None:
        """Completion records persist after the connection is closed."""
        saved = self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )
        self.repository.close()

        reopened = HabitRepository(self.database_path)
        self.addCleanup(reopened.close)

        self.assertEqual(
            reopened.list_completions(self.first.habit_id), [saved]
        )

    def test_delete_habit_cascades_to_its_completions(self) -> None:
        """Deleting a habit removes its records and preserves others."""
        self.repository.add_completion(
            self.first.habit_id, self.completed_at
        )
        retained = self.repository.add_completion(
            self.second.habit_id, self.completed_at
        )

        self.repository.delete_habit(self.first.habit_id)

        # Inspect the table directly to detect hidden orphan records.
        connection = sqlite3.connect(self.database_path)
        self.addCleanup(connection.close)
        rows = connection.execute(
            "SELECT completion_id, habit_id FROM completions"
        ).fetchall()

        self.assertEqual(
            rows, [(retained.completion_id, self.second.habit_id)]
        )
        self.assertEqual(
            self.repository.list_completions(self.second.habit_id),
            [retained],
        )


if __name__ == "__main__":
    unittest.main()