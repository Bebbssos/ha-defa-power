"""IdAnonymizer util."""


class IdAnonymizer:
    """Anonymizes sensitive identifiers while maintaining consistency in mapping."""

    def __init__(self) -> None:
        """Initialize the ID anonymizer."""
        self._mapping: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}

    def anonymize(self, real_id: str, id_type: str) -> str:
        """Map a real ID to an anonymized ID based on its type.

        Args:
            real_id: The actual identifier to anonymize
            id_type: The type of identifier (e.g., "chargepoint", "connector")

        Returns:
            An anonymized ID that consistently maps to the same real_id for the same type
        """
        if not real_id or not id_type:
            return ""

        key = (real_id, id_type)

        if key in self._mapping:
            return self._mapping[key]

        # Create a new anonymized ID for this type
        if id_type not in self._counters:
            self._counters[id_type] = 0

        self._counters[id_type] += 1
        anonymous_id = f"<{id_type}_{self._counters[id_type]}>"
        self._mapping[key] = anonymous_id

        return anonymous_id

    def clear(self) -> None:
        """Clear all stored mappings and counters."""
        self._mapping.clear()
        self._counters.clear()
