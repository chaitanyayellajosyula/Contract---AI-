from dataclasses import dataclass, field
from typing import Any, Callable

from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector
from app.connectors.lever.lever_connector import LeverConnector


@dataclass(frozen=True)
class SourceConfiguration:
    """Approved configuration for one externally accessible job source."""

    source: str
    identifier: str
    enabled: bool
    connector_factory: Callable[[str], Any]
    connector_type: str = ""
    settings: dict[str, Any] = field(default_factory=dict)


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
                connector_type="greenhouse",
            )
        )

    def register_lever_site(
        self,
        site: str,
        enabled: bool = True,
        settings: dict[str, Any] | None = None,
    ) -> None:
        site = site.strip()
        if not site:
            raise ValueError("Lever site is required")
        self.register(
            SourceConfiguration(
                source="lever",
                identifier=site,
                enabled=enabled,
                connector_factory=LeverConnector,
                connector_type="lever",
                settings=settings or {},
            )
        )

    def resolve(self, source: str, identifier: str) -> SourceConfiguration | None:
        configuration = self._configurations.get((source.lower(), identifier))
        if configuration is None or not configuration.enabled:
            return None
        return configuration

    def enabled_configurations(self) -> list[SourceConfiguration]:
        """Return approved configurations that are enabled for execution."""
        return [configuration for configuration in self._configurations.values() if configuration.enabled]


source_registry = SourceRegistry()
source_registry.register_greenhouse_board("stripe")