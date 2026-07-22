import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "simulator"))

from scripts import container_smoke


class StubEngineAdapter:
    _engine = None


def test_container_smoke_allows_stub_without_require_native(monkeypatch, capsys):
    import engine_adapter

    monkeypatch.setattr(engine_adapter, "EngineAdapter", StubEngineAdapter)
    monkeypatch.setattr(sys, "argv", ["container_smoke.py"])

    assert container_smoke.main() == 0
    assert "'native_engine': False" in capsys.readouterr().out


def test_container_smoke_fails_when_native_engine_required(monkeypatch):
    import engine_adapter

    monkeypatch.setattr(engine_adapter, "EngineAdapter", StubEngineAdapter)
    monkeypatch.setattr(sys, "argv", ["container_smoke.py", "--require-native"])

    with pytest.raises(RuntimeError, match="native engine module is unavailable"):
        container_smoke.main()
