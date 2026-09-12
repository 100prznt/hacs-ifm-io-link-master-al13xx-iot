"""Shared device and availability information."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class IfmEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, port, field=None):
        super().__init__(coordinator)
        self.port = str(port)
        self.field = field
        assignment = coordinator.entry.options.get("ports", {}).get(self.port, {})
        self.profile_id = assignment.get("profile", "unknown")
        profile = coordinator.library.all.get(self.profile_id, {})
        serial = coordinator.identity["serial"]
        suffix = f"{self.profile_id}_{field['key']}" if field else "connection"
        self._attr_unique_id = f"{serial}_port_{port}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{serial}_port_{port}")},
            via_device=(DOMAIN, serial),
            name=assignment.get("name") or f"{coordinator.entry.title} · Port {port}",
            manufacturer=profile.get("manufacturer") or "IO-Link",
            model=profile.get("model") or "Unbekannt",
            suggested_area=assignment.get("location") or None,
        )
        self._attr_name = field.get("name", field["key"]) if field else "Verbindung"

    @property
    def port_data(self):
        return (self.coordinator.data or {}).get(self.port, {})

    @property
    def available(self):
        return super().available and (
            self.field is None
            or (
                self.port_data.get("connected", False)
                and not self.port_data.get("error")
                and self.port_data.get("values", {}).get(self.field["key"]) is not None
            )
        )

    @property
    def extra_state_attributes(self):
        assignment = self.port_data.get("assignment", {})
        return {
            "port": int(self.port),
            "profile": self.profile_id,
            "location": assignment.get("location", ""),
            "purpose": assignment.get("purpose", ""),
            "decode_error": self.port_data.get("error"),
        }
