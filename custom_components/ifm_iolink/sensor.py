"""Numeric process-data sensors and read-only manufacturer-parameter sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .decoder import parameter_entity_kind
from .entity import IfmEntity, IfmParameterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for port in range(1, coordinator.identity["ports"] + 1):
        assigned = entry.options.get("ports", {}).get(str(port), {}).get("profile")
        profile = coordinator.library.all.get(assigned, {})
        entities.extend(
            IfmSensor(coordinator, port, field) for field in profile.get("fields", []) if field["type"] != "bool"
        )
        parameters = {p["index"]: p for p in profile.get("parameters", [])}
        selected = entry.options.get("ports", {}).get(str(port), {}).get("entities", [])
        entities.extend(
            IfmParameterSensor(coordinator, port, parameters[index])
            for index in selected
            if index in parameters and parameter_entity_kind(parameters[index]) == "sensor"
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


class IfmParameterSensor(IfmParameterEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, port, parameter):
        super().__init__(coordinator, port, parameter)
        decoder = parameter.get("decoder")
        field = decoder["fields"][0] if decoder and len(decoder.get("fields", [])) == 1 else None
        if field:
            self._attr_native_unit_of_measurement = field.get("unit") or None
            if field["type"] in ("uint", "int"):
                self._attr_suggested_display_precision = field.get("precision", 3)

    @property
    def native_value(self):
        return self._value
