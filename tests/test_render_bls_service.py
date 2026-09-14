import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("render_bls", Path(__file__).resolve().parents[1] / "scripts/render_bls_service.py")
RENDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDER)


def test_render_resolves_paths_and_omits_optional_environment(tmp_path):
    result = RENDER.render(repository=RENDER.ROOT, python=Path(RENDER.sys.executable), store=tmp_path)
    assert len(result) == 2
    assert "{{" not in str(result)
    assert "EnvironmentFile=" not in result["forex-bls-schedule.service"]
    assert "--store " + str(tmp_path) in result["forex-bls-schedule.service"]


@pytest.mark.parametrize("path", ["relative", "/tmp/a%h", "/tmp/$HOME", "/tmp/a b", "/tmp/a\nb", "/tmp/a/../b"])
def test_unsafe_unit_paths_refuse(path):
    with pytest.raises(ValueError):
        RENDER.local_path(path)


def test_output_is_never_overwritten(tmp_path):
    output = tmp_path / "rendered"
    output.mkdir()
    args = ["--store", str(tmp_path), "--output", str(output)]
    assert RENDER.main(args) == 0
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    assert RENDER.main(args) == 2
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}


def test_selected_venv_interpreter_path_is_preserved(tmp_path):
    interpreter = tmp_path / "venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(Path(RENDER.sys.executable).resolve())
    service = RENDER.render(repository=RENDER.ROOT, python=interpreter, store=tmp_path)["forex-bls-schedule.service"]
    assert "ExecStart=" + str(interpreter) + " " in service
