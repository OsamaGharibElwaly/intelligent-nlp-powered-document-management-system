import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.feedback_store import FeedbackStore
from app.services.learning_signals_store import LearningSignalsStore


def test_feedback_store_append_returns_stable_id(tmp_path: Path) -> None:
    store = FeedbackStore(str(tmp_path))
    fid = store.append({"sentiment": "positive", "query": "hello"})
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["feedback_id"] == fid
    assert rows[0]["sentiment"] == "positive"


def test_learning_chunk_delta_and_cap(tmp_path: Path) -> None:
    ls = LearningSignalsStore(str(tmp_path))
    for _ in range(20):
        ls.apply_feedback_to_chunks(["chunk-a"], positive=True)
    assert ls.get_chunk_delta("chunk-a") <= 0.15 + 1e-6
    ls.apply_feedback_to_chunks(["chunk-a"], positive=False)
    assert ls.get_chunk_delta("chunk-a") < 0.15


def test_negative_feedback_nudges_keyword_weight_up(tmp_path: Path) -> None:
    ls = LearningSignalsStore(str(tmp_path))
    kw0, vw0 = ls.get_hybrid_weights()
    ls.nudge_hybrid_weights(positive=False)
    kw1, vw1 = ls.get_hybrid_weights()
    assert kw1 >= kw0
    assert vw1 <= vw0


def test_flag_reindex_queues_document(tmp_path: Path) -> None:
    ls = LearningSignalsStore(str(tmp_path))
    ls.flag_reindex("logical-doc-1", "unit_test")
    snap = ls.snapshot()
    assert snap["reindex_queue"]
    assert snap["reindex_queue"][-1]["logical_document_id"] == "logical-doc-1"
