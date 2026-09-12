"""Reference backups never silently mix devices or replace a complete backup with errors."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.ifm_iolink.api import IfmError
from custom_components.ifm_iolink.parameters import ParameterBackups, collect_parameters


def coordinator(failing=False, swapped=False):
    profile = {
        "id": "test",
        "match": [{"vendorid": 310, "deviceid": 602}],
        "parameters": [
            {"index": 1, "name": "First", "access": "rw", "datatype": "StringT"},
            {"index": 2, "name": "Second", "access": "ro", "datatype": "StringT"},
        ],
    }
    identity_reads = 0

    async def multi(paths):
        nonlocal identity_reads
        identity_reads += 1
        identity = {
            "vendorid": 310,
            "deviceid": 602,
            "serial": "changed" if swapped and identity_reads > 1 else "first",
            "status": 2,
        }
        return {p: {"code": 200, "data": identity[p.rsplit("/", 1)[-1]]} for p in paths}

    async def request(path, data):
        assert path.endswith("/iolreadacyclic")
        assert data["subindex"] == 0
        if failing and data["index"] == 1:
            raise IfmError("read failed")
        return {"value": "4142"}

    return SimpleNamespace(
        entry=SimpleNamespace(options={"ports": {"1": {"profile": "test"}}}),
        library=SimpleNamespace(all={"test": profile}),
        identity={"serial": "master", "model": "AL1350"},
        client=SimpleNamespace(multi=multi, request=request),
    )


def test_all_parameters_keep_raw_values_and_identity():
    result = asyncio.run(collect_parameters(coordinator(), 1))
    assert result["complete"]
    assert result["values"]["1"]["raw"] == "4142"
    assert result["values"]["2"]["value"] == "AB"
    assert result["device"]["deviceid"] == 602
    assert result["restore_supported"] is True


def test_parameter_error_does_not_skip_remaining_reads():
    result = asyncio.run(collect_parameters(coordinator(failing=True), 1))
    assert not result["complete"]
    assert result["errors"] == {"1": "read failed"}
    assert result["values"]["2"]["raw"] == "4142"


def test_device_swap_rejects_mixed_backup():
    with pytest.raises(ValueError, match="gewechselt"):
        asyncio.run(collect_parameters(coordinator(swapped=True), 1))


def test_wrong_profile_rejects_read():
    c = coordinator()
    c.library.all["test"]["match"][0]["deviceid"] = 403
    with pytest.raises(ValueError, match="Gerätekennung"):
        asyncio.run(collect_parameters(c, 1))


def test_incomplete_backup_preserves_saved_reference():
    backups = ParameterBackups.__new__(ParameterBackups)
    backups.data = {"entry": {"1": {"complete": True, "values": {"1": "saved"}}}}
    backups.lock = asyncio.Lock()
    backups.store = SimpleNamespace(async_save=AsyncMock())
    with pytest.raises(ValueError, match="Unvollständige"):
        asyncio.run(backups.save("entry", 1, {"complete": False}))
    assert backups.get("entry", 1)["values"]["1"] == "saved"
    backups.store.async_save.assert_not_awaited()


def test_backups_are_isolated_persisted_and_reloadable():
    backups = ParameterBackups.__new__(ParameterBackups)
    backups.data = {}
    backups.lock = asyncio.Lock()
    saved = []

    async def save(value):
        saved.append(value)

    backups.store = SimpleNamespace(async_save=save, async_load=AsyncMock(side_effect=lambda: saved[-1]))

    async def run():
        await backups.save("a", 1, {"complete": True, "values": {"1": "first"}})
        await backups.save("b", 1, {"complete": True, "values": {"1": "second"}})
        backups.data = {}
        await backups.load()
        assert backups.get("a", 1)["values"]["1"] == "first"
        assert backups.get("b", 1)["values"]["1"] == "second"
        await backups.remove("a")
        assert backups.get("a", 1) is None
        assert backups.get("b", 1) is not None

    asyncio.run(run())
