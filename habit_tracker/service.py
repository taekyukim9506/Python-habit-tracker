"""Connect habit management actions to the database repository."""

from habit_tracker.habit import Habit
from habit_tracker.storage import Completion, HabitRepository


class HabitService:
    """Provide application actions without terminal input or output.

    The caller supplies an open repository and remains responsible
    for closing it. Validation errors are passed to the caller so
    the interface can display a clear message.
    """

    def __init__(self, repository: HabitRepository) -> None:
        """Use the supplied repository for persistent storage."""
        self._repository = repository

    def create_habit(
        self,
        name: str,
        description: str,
        periodicity: str,
    ) -> Habit:
        """Validate a new habit and save it with its creation time."""
        habit = Habit(
            name=name,
            description=description,
            periodicity=periodicity,
        )

        return self._repository.add_habit(habit)

    def list_habits(self) -> list[Habit]:
        """Return all saved habits in database ID order."""
        return self._repository.list_habits()

    def get_habit(self, habit_id: int) -> Habit:
        """Return the selected habit or report that it does not exist."""
        return self._repository.get_habit(habit_id)

    def complete_habit(self, habit_id: int) -> Completion:
        """Check off a habit using the current local time.

        The ordinary application workflow records completion now.
        Explicit historical timestamps remain available through the
        repository for controlled demonstration data and tests.
        """
        return self._repository.add_completion(habit_id)

    def get_history(self, habit_id: int) -> list[Completion]:
        """Return the selected habit's completions chronologically."""
        return self._repository.list_completions(habit_id)

    def undo_completion(
        self,
        habit_id: int,
        completion_id: int,
        *,
        confirmed: bool = False,
    ) -> bool:
        """Remove one completion only when explicitly confirmed.

        Return True after deletion or False when cancelled.
        Invalid identifiers are checked when deletion is requested.
        """
        self._validate_confirmation(confirmed)

        if not confirmed:
            return False

        self._repository.delete_completion(habit_id, completion_id)
        return True

    def delete_habit(
        self,
        habit_id: int,
        *,
        confirmed: bool = False,
    ) -> bool:
        """Delete a habit and its history only when confirmed.

        Return True after deletion or False when cancelled.
        The interface must obtain confirmation before passing True.
        """
        self._validate_confirmation(confirmed)

        if not confirmed:
            return False

        self._repository.delete_habit(habit_id)
        return True

    @staticmethod
    def _validate_confirmation(confirmed: bool) -> None:
        """Accept only a real boolean as a confirmation decision."""
        # Strings such as "no" are truthy in Python but are not consent.
        if not isinstance(confirmed, bool):
            raise TypeError("Confirmation must be True or False.")