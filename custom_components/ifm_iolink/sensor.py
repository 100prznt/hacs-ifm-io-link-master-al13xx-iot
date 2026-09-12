"""Numeric process-data sensors."""

from homeassistant.components.sensor import SensorEntity

from .entity import IfmEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for port in range(1, coordinator.identity["ports"] + 1):
        assigned = entry.options.get("ports", {}).get(str(port), {}).get("profile")
        profile = coordinator.library.all.get(assigned, {})
        entities.extend(
            IfmSensor(coordinator, port, field) for field in profile.get("fields", []) if field["type"] != "bool"
        )
    async_add_entities(entities)


class IfmSensor(IfmEntity, SensorEntity):
    def __init__(self, coordinator, port, field):
        super().__init__(coordinator, port, field)
        self._attr_native_unit_of_measurement = field.get("unit") or None
        self._attr_device_class = field.get("device_class") or None
        self._attr_state_class = field.get("state_class") or None
        self._attr_suggested_display_precision = field.get("precision", 3)

    @property
    def native_value(self):
        return self.port_data.get("values", {}).get(self.field["key"])
