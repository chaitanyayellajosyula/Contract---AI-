from dataclasses import dataclass
from typing import Any, Callable

from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector


@dataclass(frozen=True)
class SourceConfiguration:
    """Approved configuration for one externally accessible job source."""

    source: str
    identifier: str
    enabled: bool
    connector_factory: Callable[[str], Any]


class SourceRegistry:
    """Registry of explicitly approved source configurations."""

    def __init__(self) -> None:
        self._configurations: dict[tuple[str, str], SourceConfiguration] = {}

    def register(self, configuration: SourceConfiguration) -> None:
        key = (configuration.source.lower(), configuration.identifier)
        self._configurations[key] = configuration

    def register_greenhouse_board(self, board: str, enabled: bool = True) -> None:
        board = board.strip()
        if not board:
            raise ValueError("Greenhouse board is required")
        self.register(
            SourceConfiguration(
                source="greenhouse",
                identifier=board,
                enabled=enabled,
                connector_factory=GreenhouseConnector,
            )
        )

    def resolve(self, source: str, identifier: str) -> SourceConfiguration | None:
        configuration = self._configurations.get((source.lower(), identifier))
        if configuration is None or not configuration.enabled:
            return None
        return configuration


source_registry = SourceRegistry()
source_registry.register_greenhouse_board("stripe")