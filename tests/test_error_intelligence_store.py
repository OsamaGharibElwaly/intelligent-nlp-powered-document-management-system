import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.services.error_intelligence_store as eis_mod  # noqa: E402
from app.services.error_intelligence_store import ErrorIntelligenceStore  # noqa: E402


def test_error_intel_filters_and_order(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = ErrorIntelligenceStore(str(root))
    store.record(
        error_type="validation",
        severity="warning",
        endpoint="/query",
        message="bad",
        request_id="r1",
    )
    store.record(
        error_type="system",
        severity="critical",
        endpoint="/upload",
        message="boom",
        request_id="r2",
        stack_trace="trace",
    )
    out = store.list_events(endpoint_prefix="/query", limit=10)
    assert len(out) == 1
    assert out[0]["request_id"] == "r1"
    out_all = store.list_events(limit=10)
    assert len(out_all) == 2
    assert out_all[0]["timestamp"] >= out_all[1]["timestamp"]  # descending


def test_compact_tmp(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "c"
    store = ErrorIntelligenceStore(str(root))
    monkeypatch.setattr(eis_mod, "_MAX_FILE_LINES", 5)
    monkeypatch.setattr(eis_mod, "_KEEP_AFTER_COMPACT", 3)
    for i in range(6):
        store.record(
            error_type="system",
            severity="info",
            endpoint="/x",
            message=str(i),
            request_id=f"id{i}",
        )
    lines = (root / "error_intelligence.log").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) <= 3
