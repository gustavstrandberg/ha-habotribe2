"""Base entities for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HaboTribe2Coordinator


class HaboTribe2Entity(CoordinatorEntity[HaboTribe2Coordinator]):
    """Base class for HABO Tribe2 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HaboTribe2Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="HABO",
            model="Tribe2 Smart Lock",
            name=coordinator.data.name or "HABO Tribe2 Smart Lock",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        return super().available and self.coordinator.data.connected is not False
