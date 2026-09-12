"""Read manufacturer parameters and persist port backups and restore reports."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

from .api import IfmError, data_value
from .const import DOMAIN, port_path
from .decoder import decode


async def read_parameter_value(coordinator, port, parameter):
    data = await coordinator.client.request(
        port_path(port, "iolreadacyclic"), {"index": parameter["index"], "subindex": 0}
    )
    raw = data.get("value", data.get("data"))
    if not isinstance(raw, str) or len(raw) > 2048 or len(raw) % 2:
        raise ValueError("Ungültige Parameterantwort")
    bytes.fromhex(raw)
    value, unit = raw, ""
    if parameter.get("decoder"):
        value = decode(parameter["decoder"], raw)["value"]
        unit = parameter["decoder"]["fields"][0].get("unit", "")
    elif parameter.get("datatype") == "StringT":
        value = bytes.fromhex(raw).decode("utf-8", errors="replace").rstrip("\x00")
    return {"value": value, "raw": raw, "unit": unit}


async def read_identity(coordinator, port):
    names = ("vendorid", "deviceid", "serial", "status")
    paths = [port_path(port, name) for name in names]
    response = await coordinator.client.multi(paths)
    identity = {name: data_value(response, path) for name, path in zip(names, paths, strict=True)}
    if identity["status"] != 2 or not identity["vendorid"] or not identity["deviceid"]:
        raise ValueError("Kein verbundenes IO-Link-Gerät")
    return identity


async def collect_parameters(coordinator, port):
    assignment = deepcopy(coordinator.entry.options.get("ports", {}).get(str(port), {}))
    profile = deepcopy(coordinator.library.all.get(assignment.get("profile")))
    if not profile or not profile.get("parameters"):
        raise ValueError("Dem Port ist kein Profil mit Herstellerparametern zugewiesen")
    identity = await read_identity(coordinator, port)
    if profile.get("match") and not any(
        identity["vendorid"] == m["vendorid"] and identity["deviceid"] == m["deviceid"] for m in profile["match"]
    ):
        raise ValueError("Gerätekennung passt nicht zum Profil")
    values, errors = {}, {}
    deadline = asyncio.get_running_loop().time() + 35
    for parameter in profile["parameters"]:
        key = str(parameter["index"])
        if asyncio.get_running_loop().time() >= deadline:
            errors[key] = "Zeitlimit erreicht; erneut lesen"
            continue
        try:
            values[key] = {
                **await read_parameter_value(coordinator, port, parameter),
                "name": parameter["name"],
                "access": parameter.get("access", "ro"),
                "subindex": 0,
            }
        except (ValueError, IfmError) as err:
            errors[key] = str(err)
    if identity != await read_identity(coordinator, port):
        raise ValueError("Sensor wurde während des Lesens gewechselt; bitte erneut lesen")
    if assignment != coordinator.entry.options.get("ports", {}).get(str(port), {}):
        raise ValueError("Portzuweisung wurde während des Lesens geändert")
    if profile != coordinator.library.all.get(profile["id"]):
        raise ValueError("Geräteprofil wurde während des Lesens geändert")
    return {
        "schema_version": 1,
        "kind": "ifm_iolink_parameter_reference",
        "restore_supported": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "master": deepcopy(coordinator.identity),
        "port": port,
        "device": identity,
        "profile_id": profile["id"],
        "assignment": assignment,
        "values": values,
        "errors": errors,
        "complete": not errors,
    }


class ParameterBackups:
    def __init__(self, hass):
        from homeassistant.helpers.storage import Store

        self.store = Store(hass, 1, f"{DOMAIN}.parameter_backups")
        self.audit_store = Store(hass, 1, f"{DOMAIN}.restore_reports")
        self.reports = {}
        self.plans = {}
        self.data = {}
        self.lock = asyncio.Lock()
        self.busy = set()

    async def load(self):
        self.data = await self.store.async_load() or {}
        if hasattr(self, "audit_store"):
            self.reports = await self.audit_store.async_load() or {}

    def get(self, entry_id, port):
        return self.data.get(entry_id, {}).get(str(port))

    async def save(self, entry_id, port, backup):
        if not backup["complete"]:
            raise ValueError("Unvollständige Abfrage: vorhandene Sicherung bleibt erhalten")
        async with self.lock:
            updated = deepcopy(self.data)
            updated.setdefault(entry_id, {})[str(port)] = deepcopy(backup)
            await self.store.async_save(updated)
            self.data = updated

    async def remove(self, entry_id):
        async with self.lock:
            updated = {key: value for key, value in self.data.items() if key != entry_id}
            await self.store.async_save(updated)
            self.data = updated

        if hasattr(self, "audit_store"):
            async with self.lock:
                updated_reports = {key: value for key, value in self.reports.items() if key != entry_id}
                await self.audit_store.async_save(updated_reports)
                self.reports = updated_reports
                self.plans = {token: plan for token, plan in self.plans.items() if plan["key"][0] != entry_id}

    async def record_restore(self, entry_id, port, report):
        async with self.lock:
            updated = deepcopy(self.reports)
            updated.setdefault(entry_id, {})[str(port)] = deepcopy(report)
            await self.audit_store.async_save(updated)
            self.reports = updated
