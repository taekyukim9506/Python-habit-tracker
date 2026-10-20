"""Define the habit model and validate its basic information."""

from datetime import datetime


class Habit:
    """Represent a task that should be completed daily or weekly.

    Each habit stores its name, task description, periodicity, and
    creation time. Its database ID remains None until it is saved.

    Timestamps use local time without timezone information. The same
    convention must be used when recording habit completions.
    """

    VALID_PERIODICITIES = ("daily", "weekly")

    def __init__(
        self,
        name: str,
        description: str,
        periodicity: str,
        *,
        created_at: datetime | None = None,
        habit_id: int | None = None,
    ) -> None:
        """Create a habit after checking the supplied values.

        Args:
            name: A short name used to identify the habit.
            description: The task the user needs to complete.
            periodicity: Either "daily" or "weekly".
            created_at: Creation time, or None to use the current time.
            habit_id: An existing database ID, or None for a new habit.

        Raises:
            TypeError: If a value has an incorrect type.
            ValueError: If a value is empty or outside the allowed range.
        """
        self._name = self._validate_text(name, "Name")
        self._description = self._validate_text(
            description, "Description"
        )

        cleaned_periodicity = self._validate_text(
            periodicity, "Periodicity"
        ).lower()

        if cleaned_periodicity not in self.VALID_PERIODICITIES:
            raise ValueError("Periodicity must be 'daily' or 'weekly'.")

        self._periodicity = cleaned_periodicity

        if created_at is None:
            created_at = datetime.now()

        if not isinstance(created_at, datetime):
            raise TypeError("Creation time must be a datetime object.")

        # Mixing local and timezone-aware timestamps makes comparisons unsafe.
        if created_at.tzinfo is not None:
            raise ValueError(
                "Creation time must use local time without a timezone."
            )

        self._created_at = created_at

        if habit_id is not None:
            # Python treats bool as a subclass of int, but it is not a valid ID.
            if isinstance(habit_id, bool) or not isinstance(habit_id, int):
                raise TypeError("Habit ID must be an integer.")

            if habit_id <= 0:
                raise ValueError("Habit ID must be greater than zero.")

        self._habit_id = habit_id

    @staticmethod
    def _validate_text(value: str, field_name: str) -> str:
        """Return trimmed text, rejecting non-text and blank values."""
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError(f"{field_name} must not be empty.")

        return cleaned_value

    @property
    def name(self) -> str:
        """Return the habit's name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the task that needs to be completed."""
        return self._description

    @property
    def periodicity(self) -> str:
        """Return the daily or weekly schedule."""
        return self._periodicity

    @property
    def created_at(self) -> datetime:
        """Return the habit's creation time."""
        return self._created_at

    @property
    def habit_id(self) -> int | None:
        """Return the database ID, or None if the habit is not saved."""
        return self._habit_id