"""Test habit creation and input validation without using a database."""

import unittest
from datetime import date, datetime, timezone

from habit_tracker.habit import Habit


class TestHabit(unittest.TestCase):
    """Check the public behaviour of the Habit class."""

    def setUp(self) -> None:
        """Prepare valid values that can be reused in each test."""
        self.valid_data = {
            "name": "Study Python",
            "description": "Practise Python for 30 minutes",
            "periodicity": "daily",
            "created_at": datetime(2026, 10, 1, 9, 0),
        }

    def test_create_daily_habit(self) -> None:
        """A new daily habit retains its details and has no database ID."""
        habit = Habit(**self.valid_data)

        self.assertEqual(habit.name, "Study Python")
        self.assertEqual(
            habit.description, "Practise Python for 30 minutes"
        )
        self.assertEqual(habit.periodicity, "daily")
        self.assertEqual(habit.created_at, datetime(2026, 10, 1, 9, 0))
        self.assertIsNone(habit.habit_id)

    def test_create_weekly_habit(self) -> None:
        """Weekly habits are also supported."""
        self.valid_data["periodicity"] = "weekly"

        habit = Habit(**self.valid_data)

        self.assertEqual(habit.periodicity, "weekly")

    def test_remove_surrounding_whitespace(self) -> None:
        """Spaces around text are removed without changing inner spaces."""
        self.valid_data["name"] = "  Study Python  "
        self.valid_data["description"] = "\tPractise Python for 30 minutes\n"

        habit = Habit(**self.valid_data)

        self.assertEqual(habit.name, "Study Python")
        self.assertEqual(
            habit.description, "Practise Python for 30 minutes"
        )

    def test_normalise_periodicity(self) -> None:
        """Periodicity accepts surrounding spaces and different cases."""
        examples = (
            (" DAILY ", "daily"),
            ("Weekly", "weekly"),
            ("\tWEEKLY\n", "weekly"),
        )

        for supplied, expected in examples:
            with self.subTest(periodicity=supplied):
                self.valid_data["periodicity"] = supplied

                habit = Habit(**self.valid_data)

                self.assertEqual(habit.periodicity, expected)

    def test_preserve_unicode_text(self) -> None:
        """Names and descriptions can contain Korean and German text."""
        self.valid_data["name"] = "독서"
        self.valid_data["description"] = "Übe Python für 30 Minuten."

        habit = Habit(**self.valid_data)

        self.assertEqual(habit.name, "독서")
        self.assertEqual(habit.description, "Übe Python für 30 Minuten.")

    def test_reject_blank_text_fields(self) -> None:
        """Empty strings and whitespace cannot describe a valid habit."""
        for field in ("name", "description", "periodicity"):
            for value in ("", "   ", "\t\n"):
                with self.subTest(field=field, value=value):
                    data = dict(self.valid_data)
                    data[field] = value

                    with self.assertRaises(ValueError):
                        Habit(**data)

    def test_reject_non_string_text_fields(self) -> None:
        """Text fields reject numbers, booleans, collections, and None."""
        for field in ("name", "description", "periodicity"):
            for value in (None, 123, 1.5, True, [], {}):
                with self.subTest(field=field, value=value):
                    data = dict(self.valid_data)
                    data[field] = value

                    with self.assertRaises(TypeError):
                        Habit(**data)

    def test_reject_unsupported_periodicity(self) -> None:
        """Only daily and weekly schedules are accepted."""
        for value in ("monthly", "yearly", "every day", "week"):
            with self.subTest(periodicity=value):
                self.valid_data["periodicity"] = value

                with self.assertRaisesRegex(
                    ValueError, "Periodicity must be 'daily' or 'weekly'"
                ):
                    Habit(**self.valid_data)

    def test_preserve_explicit_creation_time(self) -> None:
        """An existing timestamp is retained, including microseconds."""
        timestamp = datetime(2026, 9, 28, 14, 30, 15, 123456)
        self.valid_data["created_at"] = timestamp

        habit = Habit(**self.valid_data)

        self.assertEqual(habit.created_at, timestamp)

    def test_default_creation_time_uses_current_time(self) -> None:
        """Omitting the timestamp uses the current local time."""
        del self.valid_data["created_at"]
        before = datetime.now()

        habit = Habit(**self.valid_data)

        after = datetime.now()
        self.assertGreaterEqual(habit.created_at, before)
        self.assertLessEqual(habit.created_at, after)
        self.assertIsNone(habit.created_at.tzinfo)

    def test_none_creation_time_uses_current_time(self) -> None:
        """An explicit None also requests the current local time."""
        self.valid_data["created_at"] = None
        before = datetime.now()

        habit = Habit(**self.valid_data)

        after = datetime.now()
        self.assertGreaterEqual(habit.created_at, before)
        self.assertLessEqual(habit.created_at, after)
        self.assertIsNone(habit.created_at.tzinfo)

    def test_reject_invalid_creation_time_types(self) -> None:
        """A date without a time is not a complete creation timestamp."""
        invalid_values = (
            "2026-10-01",
            date(2026, 10, 1),
            123,
            False,
            [],
        )

        for value in invalid_values:
            with self.subTest(created_at=value):
                self.valid_data["created_at"] = value

                with self.assertRaises(TypeError):
                    Habit(**self.valid_data)

    def test_reject_timezone_aware_creation_time(self) -> None:
        """Timezone-aware values cannot be mixed with local timestamps."""
        self.valid_data["created_at"] = datetime(
            2026, 10, 1, 9, 0, tzinfo=timezone.utc
        )

        with self.assertRaisesRegex(ValueError, "without a timezone"):
            Habit(**self.valid_data)

    def test_accept_positive_database_id(self) -> None:
        """A habit loaded from storage can retain its database ID."""
        for habit_id in (1, 42):
            with self.subTest(habit_id=habit_id):
                habit = Habit(**self.valid_data, habit_id=habit_id)

                self.assertEqual(habit.habit_id, habit_id)

    def test_reject_non_positive_database_id(self) -> None:
        """Zero and negative numbers are not valid database IDs."""
        for habit_id in (0, -1, -100):
            with self.subTest(habit_id=habit_id):
                with self.assertRaises(ValueError):
                    Habit(**self.valid_data, habit_id=habit_id)

    def test_reject_invalid_database_id_types(self) -> None:
        """IDs reject booleans even though Python treats them as integers."""
        for habit_id in (True, False, "1", 1.0, [], {}):
            with self.subTest(habit_id=habit_id):
                with self.assertRaises(TypeError):
                    Habit(**self.valid_data, habit_id=habit_id)

    def test_public_properties_cannot_be_reassigned(self) -> None:
        """Ordinary assignment cannot bypass the model's validation."""
        habit = Habit(**self.valid_data)
        replacements = {
            "name": "",
            "description": "",
            "periodicity": "monthly",
            "created_at": "invalid",
            "habit_id": -1,
        }

        for attribute, replacement in replacements.items():
            with self.subTest(attribute=attribute):
                original = getattr(habit, attribute)

                with self.assertRaises(AttributeError):
                    setattr(habit, attribute, replacement)

                self.assertEqual(getattr(habit, attribute), original)


if __name__ == "__main__":
    unittest.main()