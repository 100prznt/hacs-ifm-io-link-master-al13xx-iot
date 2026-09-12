"""Load the HA-independent client/decoder modules without starting Home Assistant."""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
package = types.ModuleType("custom_components.ifm_iolink")
package.__path__ = [str(ROOT / "custom_components/ifm_iolink")]
sys.modules[package.__name__] = package
