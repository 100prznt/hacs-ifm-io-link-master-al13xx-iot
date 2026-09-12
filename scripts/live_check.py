"""Read-only hardware verification, explicitly invoked with IoT URLs."""

import asyncio
import json
import sys
import types
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
package = types.ModuleType("custom_components.ifm_iolink")
package.__path__ = [str(ROOT / "custom_components/ifm_iolink")]
sys.modules[package.__name__] = package
from custom_components.ifm_iolink.api import IfmClient, data_value
from custom_components.ifm_iolink.const import port_path
from custom_components.ifm_iolink.decoder import decode


async def main(urls):
    profiles = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in (ROOT / "custom_components/ifm_iolink/profiles").glob("*.json")
    ]
    async with aiohttp.ClientSession() as session:
        for url in urls:
            client = IfmClient(session, url)
            identity = await client.identify()
            print(identity["model"], "ports:", identity["ports"], "firmware:", identity["firmware"])
            for port in range(1, identity["ports"] + 1):
                paths = {key: port_path(port, key) for key in ("vendorid", "deviceid", "pdin")}
                values = await client.multi(list(paths.values()))
                raw = data_value(values, paths["pdin"])
                if raw is None:
                    print("Port", port, "not connected")
                    continue
                profile = next(
                    (
                        p
                        for p in profiles
                        if {
                            "vendorid": data_value(values, paths["vendorid"]),
                            "deviceid": data_value(values, paths["deviceid"]),
                        }
                        in p.get("match", [])
                    ),
                    None,
                )
                print("Port", port, profile["id"] if profile else "unknown", decode(profile, raw) if profile else raw)
                if profile and profile["id"].startswith("pn"):
                    data = await client.request(port_path(port, "iolreadacyclic"), {"index": 510, "subindex": 0})
                    print("Read-only parameter 510:", data)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
