"""Home Assistant's built-in download diagnostics action."""


async def async_get_config_entry_diagnostics(hass, entry):
    return entry.runtime_data.diagnostic()
