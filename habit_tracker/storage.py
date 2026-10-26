"""Store habits in a local SQLite database."""

import sqlite3
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from habit_tracker.habit import Habit

@dataclass(frozen=True)
class Completion:
    """Represent one saved check-off with its database identifiers."""

    completion_id: int
    habit_id: int
    completed_at: datetime

class HabitRepository:
    """Manage database operations without handling user input.

    Each repository owns one database connection. Call close() when
    finished so the database file is released.
    """

    def __init__(self, database_path: str | Path) -> None:
        """Open a database and create its tables if they do not exist.

        The parent folder must already exist. SQLite creates the
        database file when it is opened for the first time.
        """
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row

        try:
            # SQLite requires foreign keys to be enabled per connection.
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._create_tables()
        except sqlite3.Error:
            self._connection.close()
            raise

    def _create_tables(self) -> None:
        """Create the habit and completion tables without removing data."""
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS habits (
                    habit_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                    description TEXT NOT NULL
                        CHECK(length(trim(description)) > 0),
                    periodicity TEXT NOT NULL
                        CHECK(periodicity IN ('daily', 'weekly')),
                    created_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS completions (
                    completion_id INTEGER PRIMARY KEY,
                    habit_id INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    FOREIGN KEY (habit_id)
                        REFERENCES habits(habit_id)
                        ON DELETE CASCADE
                )
                """
            )

    @staticmethod
    def _validate_id(habit_id: int) -> None:
        """Reject invalid IDs before sending a query to the database."""
        if isinstance(habit_id, bool) or not isinstance(habit_id, int):
            raise TypeError("Habit ID must be an integer.")

        if habit_id <= 0:
            raise ValueError("Habit ID must be greater than zero.")

    @staticmethod
    def _row_to_habit(row: sqlite3.Row) -> Habit:
        """Convert a database row into a validated Habit object."""
        return Habit(
            name=row["name"],
            description=row["description"],
            periodicity=row["periodicity"],
            created_at=datetime.fromisoformat(row["created_at"]),
            habit_id=row["habit_id"],
        )

    def add_habit(self, habit: Habit) -> Habit:
        """Save a new habit and return a separate object with its ID.

        The supplied object remains unchanged. A habit that already
        has a database ID cannot be inserted through this method.
        """
        if not isinstance(habit, Habit):
            raise TypeError("Expected a Habit object.")

        if habit.habit_id is not None:
            raise ValueError("Only habits without a database ID can be added.")

        # Parameters keep user text separate from the SQL command.
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO habits (
                    name, description, periodicity, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    habit.name,
                    habit.description,
                    habit.periodicity,
                    habit.created_at.isoformat(timespec="microseconds"),
                ),
            )

            saved_habit = Habit(
                name=habit.name,
                description=habit.description,
                periodicity=habit.periodicity,
                created_at=habit.created_at,
                habit_id=cursor.lastrowid,
            )

        return saved_habit

    def get_habit(self, habit_id: int) -> Habit:
        """Return one habit, raising LookupError if it does not exist."""
        self._validate_id(habit_id)

        row = self._connection.execute(
            "SELECT * FROM habits WHERE habit_id = ?",
            (habit_id,),
        ).fetchone()

        if row is None:
            raise LookupError(f"Habit {habit_id} was not found.")

        return self._row_to_habit(row)

    def list_habits(self) -> list[Habit]:
        """Return all stored habits in ascending database ID order."""
        rows = self._connection.execute(
            "SELECT * FROM habits ORDER BY habit_id"
        ).fetchall()

        return [self._row_to_habit(row) for row in rows]

    def delete_habit(self, habit_id: int) -> None:
        """Delete a habit and its completions, or report a missing ID.

        Confirmation belongs in the command-line interface. This
        method performs the deletion once the caller requests it.
        """
        self._validate_id(habit_id)

        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM habits WHERE habit_id = ?",
                (habit_id,),
            )

            if cursor.rowcount == 0:
                raise LookupError(f"Habit {habit_id} was not found.")

    def close(self) -> None:
        """Close the connection and release the database file."""
        self._connection.close()