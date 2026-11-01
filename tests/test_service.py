"""Test application actions and their effects on stored habit data."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from habit_tracker.service import HabitService
from habit_tracker.storage import HabitRepository


class TestHabitServiceDecisions(unittest.TestCase):
    """Check service decisions without opening a database."""

    def setUp(self) -> None:
        """Use a mock repository to observe attempted storage operations."""
        self.repository = Mock(spec=HabitRepository)
        self.service = HabitService(self.repository)

    def test_invalid_habit_never_reaches_storage(self) -> None:
        """Validation must finish before an insert is attempted."""
        with self.assertRaises(ValueError):
            self.service.create_habit("", "Read ten pages", "daily")

        self.repository.add_habit.assert_not_called()

    def test_delete_requires_confirmation(self) -> None:
        """Omitting confirmation must not call the deletion method."""
        result = self.service.delete_habit(1)

        self.assertFalse(result)
        self.repository.delete_habit.assert_not_called()

    def test_undo_requires_confirmation(self) -> None:
        """Omitting confirmation must not attempt to remove a check-off."""
        result = self.service.undo_completion(1, 10)

        self.assertFalse(result)
        self.repository.delete_completion.assert_not_called()

    def test_non_boolean_confirmation_is_rejected(self) -> None:
        """Text and numbers cannot accidentally authorise deletion."""
        for value in ("yes", "no", 1, 0, None):
            with self.subTest(confirmed=value):
                with self.assertRaises(TypeError):
                    self.service.delete_habit(1, confirmed=value)

                with self.assertRaises(TypeError):
                    self.service.undo_completion(
                        1, 10, confirmed=value
                    )

        self.repository.delete_habit.assert_not_called()
        self.repository.delete_completion.assert_not_called()


class TestHabitServiceIntegration(unittest.TestCase):
    """Check application workflows against a real SQLite database."""

    def setUp(self) -> None:
        """Create an isolated repository for every test."""
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)

        database_path = Path(temporary_directory.name) / "service_test.db"
        self.repository = HabitRepository(database_path)
        self.addCleanup(self.repository.close)

        self.service = HabitService(self.repository)

    def test_create_and_retrieve_habit(self) -> None:
        """The service saves normalised details and returns a database ID."""
        saved = self.service.create_habit(
            "  Read  ",
            " Read ten pages ",
            " DAILY ",
        )

        loaded = self.service.get_habit(saved.habit_id)

        self.assertGreater(saved.habit_id, 0)
        self.assertEqual(loaded.name, "Read")
        self.assertEqual(loaded.description, "Read ten pages")
        self.assertEqual(loaded.periodicity, "daily")
        self.assertEqual(loaded.created_at, saved.created_at)

    def test_list_daily_and_weekly_habits(self) -> None:
        """Both supported schedules appear in the habit collection."""
        daily = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )
        weekly = self.service.create_habit(
            "Review goals", "Review this week's progress", "weekly"
        )

        habits = self.service.list_habits()

        self.assertEqual(
            [habit.habit_id for habit in habits],
            [daily.habit_id, weekly.habit_id],
        )
        self.assertEqual(
            [habit.periodicity for habit in habits],
            ["daily", "weekly"],
        )

    def test_create_complete_and_view_history(self) -> None:
        """A newly created habit can be checked off immediately."""
        habit = self.service.create_habit(
            "Study Python", "Practise for 30 minutes", "daily"
        )

        completion = self.service.complete_habit(habit.habit_id)

        self.assertEqual(completion.habit_id, habit.habit_id)
        self.assertGreaterEqual(
            completion.completed_at, habit.created_at
        )
        self.assertEqual(
            self.service.get_history(habit.habit_id), [completion]
        )

    def test_cancelled_undo_preserves_history(self) -> None:
        """Cancelling an undo leaves the selected completion stored."""
        habit = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )
        completion = self.service.complete_habit(habit.habit_id)

        result = self.service.undo_completion(
            habit.habit_id,
            completion.completion_id,
            confirmed=False,
        )

        self.assertFalse(result)
        self.assertEqual(
            self.service.get_history(habit.habit_id), [completion]
        )

    def test_confirmed_undo_preserves_habit(self) -> None:
        """Undo removes the selected record while retaining its habit."""
        habit = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )
        completion = self.service.complete_habit(habit.habit_id)

        result = self.service.undo_completion(
            habit.habit_id,
            completion.completion_id,
            confirmed=True,
        )

        self.assertTrue(result)
        self.assertEqual(self.service.get_history(habit.habit_id), [])
        self.assertEqual(
            self.service.get_habit(habit.habit_id).name, "Read"
        )

    def test_cancelled_deletion_preserves_habit_and_history(self) -> None:
        """Cancelling deletion leaves both tables' relevant data intact."""
        habit = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )
        completion = self.service.complete_habit(habit.habit_id)

        result = self.service.delete_habit(
            habit.habit_id, confirmed=False
        )

        self.assertFalse(result)
        self.assertEqual(
            self.service.get_habit(habit.habit_id).name, "Read"
        )
        self.assertEqual(
            self.service.get_history(habit.habit_id), [completion]
        )

    def test_confirmed_deletion_preserves_other_habit(self) -> None:
        """Deleting one habit does not remove another habit's history."""
        first = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )
        second = self.service.create_habit(
            "Exercise", "Complete one workout", "weekly"
        )
        self.service.complete_habit(first.habit_id)
        retained = self.service.complete_habit(second.habit_id)

        result = self.service.delete_habit(
            first.habit_id, confirmed=True
        )

        self.assertTrue(result)
        with self.assertRaises(LookupError):
            self.service.get_habit(first.habit_id)

        self.assertEqual(
            [habit.habit_id for habit in self.service.list_habits()],
            [second.habit_id],
        )
        self.assertEqual(
            self.service.get_history(second.habit_id), [retained]
        )

    def test_invalid_creation_preserves_existing_data(self) -> None:
        """An invalid schedule cannot create a partial habit record."""
        saved = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )

        with self.assertRaises(ValueError):
            self.service.create_habit(
                "Exercise", "Complete one workout", "monthly"
            )

        self.assertEqual(
            [habit.habit_id for habit in self.service.list_habits()],
            [saved.habit_id],
        )

    def test_wrong_habit_cannot_undo_completion(self) -> None:
        """Confirmed undo still checks that the record belongs to the habit."""
        first = self.service.create_habit(
            "Read", "Read ten pages", "daily"
        )
        second = self.service.create_habit(
            "Exercise", "Complete one workout", "weekly"
        )
        completion = self.service.complete_habit(second.habit_id)

        with self.assertRaises(LookupError):
            self.service.undo_completion(
                first.habit_id,
                completion.completion_id,
                confirmed=True,
            )

        self.assertEqual(
            self.service.get_history(second.habit_id), [completion]
        )


if __name__ == "__main__":
    unittest.main()