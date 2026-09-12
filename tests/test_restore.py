"""Restore checks and failure semantics without writing to real IO-Link hardware."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from custom_components.ifm_iolink.api import IfmError
from custom_components.ifm_iolink.restore import execute_restore, prepare_restore


def setup():
    profile = {
        "id": "test",
        "match": [{"vendorid": 310, "deviceid": 602}],
        "parameters": [
            {"index": 500, "name": "A", "access": "rw", "datatype": "UIntegerT"},
            {"index": 510, "name": "B", "access": "rw", "datatype": "UIntegerT"},
            {"index": 560, "name": "Diagnostic", "access": "ro", "datatype": "UIntegerT"},
            {"index": 2, "name": "System command", "access": "rw", "datatype": "UIntegerT"},
        ],
    }
    values = {500: "01", 510: "02", 560: "AA", 2: "00"}
    identity = {"vendorid": 310, "deviceid": 602, "serial": "replacement", "status": 2}
    writes = []

    async def multi(paths):
        return {p: {"code": 200, "data": identity[p.rsplit("/", 1)[-1]]} for p in paths}

    async def read(path, data):
        assert path.endswith("/iolreadacyclic")
        return {"value": values[data["index"]]}

    async def write(port, index, raw):
        writes.append((port, index, raw))
        values[index] = raw

    c = SimpleNamespace(
        entry=SimpleNamespace(options={"ports": {"1": {"profile": "test"}}}),
        library=SimpleNamespace(all={"test": profile}),
        client=SimpleNamespace(multi=multi, request=read, write_parameter=write),
        condition_values={"cached": 1},
        metadata_at=1,
    )
    backup = {
        "kind": "ifm_iolink_parameter_reference",
        "schema_version": 1,
        "complete": True,
        "errors": {},
        "profile_id": "test",
        "created_at": "2026-09-12T00:00:00Z",
        "restore_supported": False,
        "device": {**identity, "serial": "old_sensor"},
        "values": {
            str(k): {"raw": v, "subindex": 0, "access": "rw"}
            for k, v in {500: "03", 510: "04", 560: "FF", 2: "80"}.items()
        },
    }
    return c, backup, values, identity, writes


def test_legacy_backup_preview_checks_profile_not_uploaded_access():
    c, backup, _, _, writes = setup()
    plan = asyncio.run(prepare_restore(c, 1, backup))
    assert [r["index"] for r in plan["rows"]] == [500, 510]
    assert {r["index"] for r in plan["skipped"]} == {560, 2}
    assert not writes


@pytest.mark.parametrize(
    "issue", ["wrong_device", "wrong_profile", "incomplete", "hex", "length", "missing", "unknown", "subindex"]
)
def test_invalid_backup_cannot_prepare_write(issue):
    c, b, _, _, writes = setup()
    if issue == "wrong_device":
        b["device"]["deviceid"] = 601
    if issue == "wrong_profile":
        b["profile_id"] = "wrong"
    if issue == "incomplete":
        b["complete"] = False
    if issue == "hex":
        b["values"]["500"]["raw"] = "GG"
    if issue == "length":
        b["values"]["500"]["raw"] = "0003"
    if issue == "missing":
        b["values"].pop("510")
    if issue == "unknown":
        b["values"]["65000"] = {"raw": "00"}
    if issue == "subindex":
        b["values"]["500"]["subindex"] = 1
    with pytest.raises(ValueError):
        asyncio.run(prepare_restore(c, 1, b))
    assert not writes


def test_write_readback_and_original_values_are_recorded():
    c, backup, values, _, writes = setup()
    reports = []

    async def record(report):
        if not reports:
            assert writes == []
        reports.append(deepcopy(report))

    async def run():
        return await execute_restore(c, 1, await prepare_restore(c, 1, backup), record)

    result = asyncio.run(run())
    assert writes == [(1, 500, "03"), (1, 510, "04")]
    assert result["status"] == "completed"
    assert result["verified"] == [500, 510]
    assert result["pending"] == []
    assert reports[0]["rows"][0]["before"] == "01"
    assert values[560] == "AA" and values[2] == "00"


@pytest.mark.parametrize("change", ["serial", "value", "profile", "master"])
def test_stale_preview_aborts_before_any_write(change):
    c, backup, values, identity, writes = setup()

    async def run():
        plan = await prepare_restore(c, 1, backup)
        if change == "serial":
            identity["serial"] = "different"
        if change == "value":
            values[510] = "09"
        if change == "profile":
            c.library.all["test"]["parameters"][0]["access"] = "ro"

        async def record(_):
            pass

        return await execute_restore(c, 1, plan, record, still_current=lambda: change != "master")

    result = asyncio.run(run())
    assert result["status"] == "stopped"
    assert not writes


@pytest.mark.parametrize("mode", ["timeout", "mismatch", "storage"])
def test_stop_without_retry_or_rollback_on_failure(mode):
    c, backup, _, _, writes = setup()

    async def write(port, index, raw):
        writes.append((port, index, raw))
        if mode == "timeout":
            raise IfmError("request timed out; outcome unknown")

    c.client.write_parameter = write
    record_calls = 0

    async def record(_):
        nonlocal record_calls
        record_calls += 1
        if mode == "storage" and record_calls == 1:
            raise OSError("disk full")

    async def run():
        return await execute_restore(c, 1, await prepare_restore(c, 1, backup), record)

    result = asyncio.run(run())
    assert result["status"] == "stopped"
    assert len(writes) == (0 if mode == "storage" else 1)
    if mode != "storage":
        assert result["in_flight"] == 500
    assert result["pending"] == [500, 510]


def test_unchanged_backup_performs_no_hardware_writes():
    c, backup, values, _, writes = setup()
    for key in backup["values"]:
        backup["values"][key]["raw"] = values[int(key)]

    async def run():
        async def record(_):
            pass

        return await execute_restore(c, 1, await prepare_restore(c, 1, backup), record)

    result = asyncio.run(run())
    assert result["status"] == "completed"
    assert result["verified"] == []
    assert not writes


@pytest.mark.parametrize("pair", [(583, 584), (593, 594), (556, 555)])
@pytest.mark.parametrize("direction", ["up", "down"])
def test_pn_threshold_restore_orders_pairs_without_crossing_current_bounds(pair, direction):
    c, backup, values, _, writes = setup()
    high, low = pair
    profile = c.library.all["test"]
    profile["parameters"] = [
        {"index": i, "name": str(i), "access": "rw", "datatype": "IntegerT"} for i in (low, high, 550)
    ]
    values.update({low: "000A", high: "0014", 550: "00"})
    desired = {low: "001E", high: "0028", 550: "01"} if direction == "up" else {low: "0001", high: "0005", 550: "01"}
    backup["values"] = {str(i): {"raw": v} for i, v in desired.items()}
    plan = asyncio.run(prepare_restore(c, 1, backup))
    assert [r["index"] for r in plan["rows"]] == ([high, low, 550] if direction == "up" else [low, high, 550])
    assert not writes


@pytest.mark.parametrize("current,desired", [("", "476172616765"), ("476172616765", ""), ("01", "010203")])
def test_variable_length_string_labels_on_replacement_sensor(current, desired):
    c, backup, values, _, writes = setup()
    c.library.all["test"]["parameters"][0]["datatype"] = "StringT"
    values[500] = current
    backup["values"]["500"]["raw"] = desired

    async def run():
        plan = await prepare_restore(c, 1, backup)

        async def record(report):
            pass

        return await execute_restore(c, 1, plan, record)

    result = asyncio.run(run())
    assert result["status"] == "completed"
    assert (1, 500, desired) in writes
