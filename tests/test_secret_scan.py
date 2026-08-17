from pathlib import Path

from scripts.check_no_secrets import scan_file


def test_safe_example_file_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / ".env.example"
    path.write_text("API_KEY=\n", encoding="utf-8")
    assert scan_file(path) == []


def test_private_key_material_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n", encoding="utf-8")
    assert "possible private key" in scan_file(path)


def test_credential_filename_is_rejected_even_when_empty(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text("{}\n", encoding="utf-8")
    assert "forbidden secret-bearing filename" in scan_file(path)
