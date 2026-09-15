"""Port-mode switch checks and failure semantics without writing to real hardware."""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.ifm_iolink.port_mode import execute_mode_change, prepare_mode_change


def setup(mode=3, connected=True):
    state = {"mode": mode}
    writes = []

    async def write_port_mode(port, target):
        writes.append((port, target))
        state["mode"] = target

    async def multi(paths):
        return {p: {"code": 200, "data": state["mode"]} for p in paths}

    c = SimpleNamespace(
        client=SimpleNamespace(write_port_mode=write_port_mode, multi=multi),
        condition_values={(1, "prof", 64): 0, (2, "prof", 64): 0},
        metadata_at=1,
    )
    c.data = {
        "1": {
            "mode": state["mode"],
            "connected": connected,
            "assignment": {"name": "Drucksensor"},
            "profile": "prof",
        }
    }
    return c, state, writes


def test_preview_reports_current_state_and_rejects_noop():
    c, _, _ = setup(mode=3, connected=True)
    plan = asyncio.run(prepare_mode_change(c, 1, 2))
    assert plan == {
        "port": 1,
        "current_mode": 3,
        "target_mode": 2,
        "device_connected": True,
        "assignment_name": "Drucksensor",
        "profile_id": "prof",
    }
    with pytest.raises(ValueError):
        asyncio.run(prepare_mode_change(c, 1, 3))  # already IO-Link


@pytest.mark.parametrize("target", [0, 1, 4])
def test_only_do_and_iolink_are_switchable_targets(target):
    c, *_ = setup()
    with pytest.raises(ValueError):
        asyncio.run(prepare_mode_change(c, 1, target))


def test_unknown_port_or_unread_mode_cannot_be_previewed():
    c, *_ = setup()
    with pytest.raises(ValueError):
        asyncio.run(prepare_mode_change(c, 5, 2))
    c.data["1"]["mode"] = None
    with pytest.raises(ValueError):
        asyncio.run(prepare_mode_change(c, 1, 2))


def test_execute_writes_reads_back_and_clears_port_conditions():
    c, state, writes = setup(mode=3)
    plan = asyncio.run(prepare_mode_change(c, 1, 2))
    result = asyncio.run(execute_mode_change(c, 1, plan))
    assert writes == [(1, 2)]
    assert result == {"port": 1, "mode": 2}
    assert c.condition_values == {(2, "prof", 64): 0}
    assert c.metadata_at == 0


def test_stale_current_mode_aborts_before_write():
    c, state, writes = setup(mode=3)
    plan = asyncio.run(prepare_mode_change(c, 1, 2))
    c.data["1"]["mode"] = 1  # changed behind our back since the preview
    with pytest.raises(ValueError):
        asyncio.run(execute_mode_change(c, 1, plan))
    assert not writes


def test_reloaded_coordinator_aborts_before_write():
    c, *_ = setup(mode=3)
    plan = asyncio.run(prepare_mode_change(c, 1, 2))
    with pytest.raises(ValueError):
        asyncio.run(execute_mode_change(c, 1, plan, still_current=lambda: False))


def test_readback_mismatch_after_write_is_reported():
    c, state, writes = setup(mode=3)
    plan = asyncio.run(prepare_mode_change(c, 1, 2))

    async def write_port_mode(port, target):
        writes.append((port, target))
        state["mode"] = 1  # device rejected the requested mode and picked another one

    c.client.write_port_mode = write_port_mode

    with pytest.raises(ValueError):
        asyncio.run(execute_mode_change(c, 1, plan))
    assert writes == [(1, 2)]
