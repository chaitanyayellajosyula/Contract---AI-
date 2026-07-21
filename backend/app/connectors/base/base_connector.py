from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Abstract base class for future connector implementations."""

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the external source."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch data from the external source."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close any active connection or session."""
        raise NotImplementedError
