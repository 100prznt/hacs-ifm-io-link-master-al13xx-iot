"""Port connection and process status flags."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import IfmEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for port in range(1, coordinator.identity["ports"] + 1):
        entities.append(IfmBinarySensor(coordinator, port))
        assigned = entry.options.get("ports", {}).get(str(port), {}).get("profile")
        profile = coordinator.library.all.get(assigned, {})
        entities.extend(
            IfmBinarySensor(coordinator, port, field) for field in profile.get("fields", []) if field["type"] == "bool"
        )
    async_add_entities(entities)


class IfmBinarySensor(IfmEntity, BinarySensorEntity):
    def __init__(self, coordinator, port, field=None):
        super().__init__(coordinator, port, field)
        self._attr_device_class = (field.get("device_class") or None) if field else "connectivity"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        if self.field is None:
            return self.port_data.get("connected", False)
        return self.port_data.get("values", {}).get(self.field["key"])
