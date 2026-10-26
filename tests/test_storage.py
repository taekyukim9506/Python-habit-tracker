"""Test habit persistence using a separate temporary SQLite database."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from habit_tracker.habit import Habit
from habit_tracker.storage import HabitRepository


class TestHabitRepository(unittest.TestCase):
    """Check that database operations preserve the expected data."""

    def setUp(self) -> None:
        """Give each test its own database and arrange automatic cleanup."""
        temporary_directory = tempfile.TemporaryDirectory()

        # Cleanups run in reverse order: close the database, then delete it.
        self.addCleanup(temporary_directory.cleanup)

        self.database_path = (
            Path(temporary_directory.name) / "test_habits.db"
        )
        self.repository = HabitRepository(self.database_path)
        self.addCleanup(self.repository.close)

        self.habit = Habit(
            "Study Python",
            "Practise Python for 30 minutes",
            "daily",
            created_at=datetime(2026, 10, 1, 9, 0, 0, 123456),
        )

    def test_new_database_has_no_habits(self) -> None:
        """Opening a new database creates an empty habit collection."""
        self.assertTrue(self.database_path.exists())
        self.assertEqual(self.repository.list_habits(), [])

    def test_add_and_retrieve_habit(self) -> None:
        """All habit details survive saving and loading."""
        saved = self.repository.add_habit(self.habit)
        loaded = self.repository.get_habit(saved.habit_id)

        self.assertIsInstance(saved.habit_id, int)
        self.assertGreater(saved.habit_id, 0)
        self.assertEqual(loaded.habit_id, saved.habit_id)
        self.assertEqual(loaded.name, self.habit.name)
        self.assertEqual(loaded.description, self.habit.description)
        self.assertEqual(loaded.periodicity, self.habit.periodicity)
        self.assertEqual(loaded.created_at, self.habit.created_at)

    def test_saving_does_not_change_original_object(self) -> None:
        """Saving returns a new object without modifying the original."""
        saved = self.repository.add_habit(self.habit)

        self.assertIsNone(self.habit.habit_id)
        self.assertIsNot(saved, self.habit)
        self.assertIsNotNone(saved.habit_id)

    def test_data_survives_closing_and_reopening(self) -> None:
        """Committed data remains available through a new connection."""
        saved = self.repository.add_habit(self.habit)
        self.repository.close()

        reopened = HabitRepository(self.database_path)
        self.addCleanup(reopened.close)

        loaded = reopened.get_habit(saved.habit_id)

        self.assertEqual(loaded.name, self.habit.name)
        self.assertEqual(loaded.description, self.habit.description)
        self.assertEqual(loaded.periodicity, self.habit.periodicity)
        self.assertEqual(loaded.created_at, self.habit.created_at)
        self.assertEqual(len(reopened.list_habits()), 1)

    def test_list_habits_in_id_order(self) -> None:
        """Listing returns every habit in a predictable order."""
        first = self.repository.add_habit(self.habit)
        second = self.repository.add_habit(
            Habit("Review goals", "Review progress for the week", "weekly")
        )

        habits = self.repository.list_habits()

        self.assertEqual(
            [habit.habit_id for habit in habits],
            [first.habit_id, second.habit_id],
        )
        self.assertEqual(
            [habit.periodicity for habit in habits],
            ["daily", "weekly"],
        )

    def test_delete_preserves_unrelated_habit(self) -> None:
        """Deleting one habit leaves the other habit available."""
        first = self.repository.add_habit(self.habit)
        second = self.repository.add_habit(
            Habit("Read", "Read ten pages", "daily")
        )

        self.repository.delete_habit(first.habit_id)

        with self.assertRaises(LookupError):
            self.repository.get_habit(first.habit_id)

        self.assertEqual(
            [habit.habit_id for habit in self.repository.list_habits()],
            [second.habit_id],
        )

    def test_missing_habit_raises_lookup_error(self) -> None:
        """Reading or deleting a missing habit reports the problem."""
        for operation in (
            self.repository.get_habit,
            self.repository.delete_habit,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(LookupError):
                    operation(999)

                self.assertEqual(self.repository.list_habits(), [])

    def test_reject_invalid_ids_without_changing_data(self) -> None:
        """Invalid IDs cannot retrieve or delete an existing habit."""
        saved = self.repository.add_habit(self.habit)
        invalid_ids = (
            (True, TypeError),
            ("1", TypeError),
            (1.0, TypeError),
            (None, TypeError),
            (0, ValueError),
            (-1, ValueError),
        )

        for operation in (
            self.repository.get_habit,
            self.repository.delete_habit,
        ):
            for value, error_type in invalid_ids:
                with self.subTest(
                    operation=operation.__name__, habit_id=value
                ):
                    with self.assertRaises(error_type):
                        operation(value)

                    self.assertEqual(
                        [h.habit_id for h in self.repository.list_habits()],
                        [saved.habit_id],
                    )

    def test_reject_habit_that_already_has_id(self) -> None:
        """Reinserting a saved object must not create another row."""
        saved = self.repository.add_habit(self.habit)

        with self.assertRaises(ValueError):
            self.repository.add_habit(saved)

        self.assertEqual(len(self.repository.list_habits()), 1)

    def test_reject_non_habit_input(self) -> None:
        """Invalid objects cannot create database records."""
        for value in (None, "Study Python", 123):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.repository.add_habit(value)

                self.assertEqual(self.repository.list_habits(), [])

    def test_sql_like_text_is_stored_as_text(self) -> None:
        """Quotes and SQL-like content cannot change the database schema."""
        name = "Read'); DROP TABLE habits; --"
        habit = Habit(name, "Read a student's book", "daily")

        saved = self.repository.add_habit(habit)
        loaded = self.repository.get_habit(saved.habit_id)

        self.assertEqual(loaded.name, name)
        self.assertEqual(loaded.description, "Read a student's book")
        self.assertEqual(len(self.repository.list_habits()), 1)


if __name__ == "__main__":
    unittest.main()