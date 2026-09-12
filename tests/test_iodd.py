import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from custom_components.ifm_iolink.decoder import decode
from custom_components.ifm_iolink.iodd import import_iodd

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "model,mode,device,scale,length,raw,value",
    [
        ("pn7094", "status_b", 601, 0.001, 4, "1BE40200", 7.14),
        ("pn7096", "status_b", 602, 0.0001, 4, "4E5C0100", 2.006),
        ("pn7094", "default", 403, 0.01, 2, "0193", 1.0),
        ("pn7096", "default", 404, 0.01, 2, "0193", 1.0),
    ],
)
def test_manufacturer_layouts(model, mode, device, scale, length, raw, value):
    raw_xml = (FIXTURES / f"{model}_{mode}.xml").read_bytes()
    candidates = import_iodd(raw_xml, "device.xml")
    result = next(c for c in candidates if c["profile"]["model"].lower() == model)
    profile = result["profile"]
    assert result["warnings"] == []
    assert profile["match"] == [{"vendorid": 310, "deviceid": device}]
    assert profile["length"] == length
    assert profile["fields"][0]["scale"] == scale
    assert decode(profile, raw)["pd_1"] == value
    # Compatible IDs listed in an IODD must not match an incompatible layout.
    assert all(m["deviceid"] == device for m in profile["match"])


def archive(files):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, value in files.items():
            z.writestr(name, value)
    return buffer.getvalue()


def test_variant_image_and_localized_text_imported():
    xml = (FIXTURES / "pn7096_status_b.xml").read_bytes()
    german = b'<ExternalTextCollection xmlns="http://www.io-link.com/IODD/2010/10"><Language><Text id="TI_PD_VR_IN_1_Name" value="Druck lokalisiert"/></Language></ExternalTextCollection>'
    png = b"\x89PNG\r\n\x1a\nexample"
    raw = archive({"IODD/device.xml": xml, "IODD/device-de.xml": german, "IODD/ifm-PNx0-pic.png": png})
    candidate = import_iodd(raw)[0]["profile"]
    assert candidate["fields"][0]["name"] == "Druck lokalisiert"
    assert candidate["image"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("filename", ["../device.xml", "/device.xml", "folder\\device.xml"])
def test_zip_path_traversal_rejected(filename):
    with pytest.raises(ValueError):
        import_iodd(archive({filename: b"<test/>"}))


def test_dtd_and_entity_rejected():
    with pytest.raises(ValueError, match="DTD"):
        import_iodd(b'<!DOCTYPE a [<!ENTITY example SYSTEM "file:///etc/passwd">]><a>&example;</a>', "device.xml")


def test_oversized_upload_and_unknown_xml():
    with pytest.raises(ValueError):
        import_iodd(b"x" * 8_000_001)
    with pytest.raises(ValueError):
        import_iodd(b"<anything/>", "device.xml")


def test_unsupported_fields_reported():
    raw = (FIXTURES / "pn7096_status_b.xml").read_bytes().replace(b"IntegerT", b"StringT", 1)
    candidate = import_iodd(raw, "device.xml")[0]
    assert candidate["warnings"]
    assert len(candidate["profile"]["fields"]) == 3


def test_jumo_float_and_integer_layouts_do_not_mix_scaling():
    candidates = import_iodd((FIXTURES / "jumo_186031.zip").read_bytes())
    assert len(candidates) == 2
    floating, integer = [c["profile"] for c in candidates]
    assert floating["conditions"] == [{"index": 64, "value": 0}]
    assert integer["conditions"] == [{"index": 64, "value": 1}]
    assert floating["fields"][1]["unit"] == "°C"
    assert integer["fields"][0]["scale"] == 0.001
    assert integer["fields"][1]["scale"] == 0.1
    # A runtime-selectable unit must never be guessed from the first menu.
    assert "unit" not in floating["fields"][0]
    assert any("Einheit hängt" in w for w in candidates[0]["warnings"])
    # This supplied family file does not describe the actual BADU Device-ID.
    assert all(c["profile"]["match"][0]["deviceid"] != 0x186831 for c in candidates)


def test_jumo_status_offsets_from_manufacturer():
    p = import_iodd((FIXTURES / "jumo_186031.zip").read_bytes())[0]["profile"]
    values = decode(p, "00" * 20 + "0FC0")
    assert values["pd_12"] and values["pd_13"]  # empty pipe / bubbles: bits 6/7
    assert values["pd_14"] and values["pd_17"]  # batch / calibration: bits 8/11


def test_complete_ifm_file_keeps_equivalent_pressure_units():
    p = import_iodd((FIXTURES / "ifm_pn7096_complete.zip").read_bytes())[0]
    assert p["warnings"] == []
    assert decode(p["profile"], "4E5C0100")["pd_1"] == 2.006
    assert p["profile"]["fields"][0]["unit"] == "bar"
