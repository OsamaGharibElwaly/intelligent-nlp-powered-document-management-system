"""Append-only observability events + aggregation for admin dashboards."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Literal

_MAX_FILE_LINES = 8000
_KEEP_AFTER_COMPACT = 5000

MetricsRange = Literal["24h", "7d", "30d"]


def finalize_query_metrics_row(
    req_metrics: dict[str, Any],
    cleaned: dict[str, Any] | None,
    *,
    success: bool,
    failure_detail: str | None = None,
    short_circuit: bool = False,
    endpoint: str = "/query",
) -> dict[str, Any]:
    perf_start = req_metrics.get("perf_start")
    total_ms: float | None = None
    if perf_start is not None:
        total_ms = (perf_counter() - float(perf_start)) * 1000

    conf = (cleaned or {}).get("confidence")
    score_raw = conf.get("score") if isinstance(conf, dict) else None
    try:
        conf_f = float(score_raw) if score_raw is not None else None
    except (TypeError, ValueError):
        conf_f = None

    return {
        "kind": "query",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": req_metrics.get("request_id"),
        "endpoint": endpoint,
        "success": success,
        "failure_detail": failure_detail,
        "short_circuit": short_circuit,
        "query_latency_ms": total_ms,
        "retrieval_latency_ms": req_metrics.get("retrieval_ms"),
        "llm_latency_ms": req_metrics.get("llm_ms"),
        "chunks_returned": req_metrics.get("chunks_returned"),
        "retrieval_accuracy_proxy": req_metrics.get("retrieval_accuracy_proxy"),
        "confidence_score": conf_f,
        "degraded": bool((cleaned or {}).get("degraded")),
        "prompt_tokens": _int_or_none(req_metrics.get("prompt_tokens")),
        "completion_tokens": _int_or_none(req_metrics.get("completion_tokens")),
        "total_tokens": _int_or_none(req_metrics.get("total_tokens")),
    }


def finalize_retrieve_metrics_row(
    req_metrics: dict[str, Any],
    *,
    retrieval_ms: float,
    chunks_returned: int,
    top_relevance: float | None,
    success: bool,
    failure_detail: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": "retrieve",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": req_metrics.get("request_id"),
        "endpoint": "/retrieve",
        "success": success,
        "failure_detail": failure_detail,
        "query_latency_ms": None,
        "retrieval_latency_ms": retrieval_ms,
        "llm_latency_ms": None,
        "chunks_returned": chunks_returned,
        "retrieval_accuracy_proxy": top_relevance,
        "confidence_score": None,
        "degraded": False,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(0.95 * (len(s) - 1)))))
    return float(s[idx])


class ObservabilityMetricsStore:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._log_file = self._root / "observability_metrics.log"
        self._lock = Lock()
        if not self._log_file.exists():
            self._log_file.touch()

    def append_event(self, row: dict[str, Any]) -> None:
        line = json.dumps(row, ensure_ascii=True)
        with self._lock:
            with self._log_file.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")
            self._compact_if_needed()

    def _compact_if_needed(self) -> None:
        try:
            lines = self._log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) <= _MAX_FILE_LINES:
            return
        keep = lines[-_KEEP_AFTER_COMPACT:]
        tmp = self._log_file.with_suffix(".log.tmp")
        tmp.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
        tmp.replace(self._log_file)

    def read_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self._log_file.exists():
            return out
        with self._lock:
            try:
                raw = self._log_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                return out
        for line in raw:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return out

    def events_in_range(self, since: datetime | None, until: datetime | None) -> list[dict[str, Any]]:
        rows = self.read_all()
        filtered: list[dict[str, Any]] = []
        for r in rows:
            ts = _parse_ts(str(r.get("timestamp", "")))
            if since is not None and ts is not None and ts < since:
                continue
            if until is not None and ts is not None and ts > until:
                continue
            filtered.append(r)
        return filtered

    def export_csv(self, since: datetime | None, until: datetime | None) -> str:
        rows = self.events_in_range(since, until)
        fields = [
            "timestamp",
            "kind",
            "request_id",
            "endpoint",
            "success",
            "query_latency_ms",
            "retrieval_latency_ms",
            "llm_latency_ms",
            "chunks_returned",
            "retrieval_accuracy_proxy",
            "confidence_score",
            "degraded",
            "total_tokens",
            "failure_detail",
        ]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: str(x.get("timestamp", ""))):
            w.writerow({k: r.get(k) for k in fields})
        return buf.getvalue()

    def summarize(self, range_key: MetricsRange) -> dict[str, Any]:
        now = datetime.now(UTC)
        if range_key == "24h":
            delta = timedelta(hours=24)
            bucket_minutes = 60
        elif range_key == "7d":
            delta = timedelta(days=7)
            bucket_minutes = 60 * 24
        else:
            delta = timedelta(days=30)
            bucket_minutes = 60 * 24

        window_start = now - delta
        prev_window_start = window_start - delta
        prev_window_end = window_start

        cur_events = self.events_in_range(window_start, now)
        prev_events = self.events_in_range(prev_window_start, prev_window_end)

        cur_buckets = self._aggregate_buckets(cur_events, window_start, bucket_minutes)
        prev_buckets = self._aggregate_buckets(prev_events, prev_window_start, bucket_minutes)

        return {
            "range": range_key,
            "bucket_minutes": bucket_minutes,
            "bucket_start": window_start.isoformat(),
            "bucket_end": now.isoformat(),
            "buckets": cur_buckets,
            "previous_buckets": prev_buckets,
            "totals": self._totals(cur_events),
            "previous_totals": self._totals(prev_events),
            "alert_thresholds": {
                "warn_query_latency_ms": 8000.0,
                "warn_llm_latency_ms": 6000.0,
                "warn_retrieval_latency_ms": 4000.0,
                "min_success_rate": 0.92,
            },
        }

    def _bucket_key(self, ts: datetime, origin: datetime, bucket_minutes: int) -> str:
        slot = int((ts - origin).total_seconds() // (bucket_minutes * 60))
        boundary = origin + timedelta(minutes=bucket_minutes * slot)
        return boundary.isoformat()

    def _aggregate_buckets(
        self,
        events: list[dict[str, Any]],
        origin: datetime,
        bucket_minutes: int,
    ) -> list[dict[str, Any]]:
        by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in events:
            ts = _parse_ts(str(e.get("timestamp", "")))
            if ts is None:
                continue
            key = self._bucket_key(ts, origin, bucket_minutes)
            by_bucket[key].append(e)

        keys_sorted = sorted(by_bucket.keys())
        out: list[dict[str, Any]] = []
        for bk in keys_sorted:
            evs = by_bucket[bk]
            q_evs = [x for x in evs if x.get("kind") == "query"]
            r_evs = [x for x in evs if x.get("kind") == "retrieve"]

            qlats = [float(x["query_latency_ms"]) for x in q_evs if x.get("query_latency_ms") is not None]
            rlats = [
                float(x["retrieval_latency_ms"])
                for x in q_evs + r_evs
                if x.get("retrieval_latency_ms") is not None
            ]
            llats = [float(x["llm_latency_ms"]) for x in q_evs if x.get("llm_latency_ms") is not None]
            toks = [_int_or_none(x.get("total_tokens")) for x in q_evs]
            toks_f = [float(t) for t in toks if t is not None]

            proxies = [
                float(x["retrieval_accuracy_proxy"])
                for x in q_evs + r_evs
                if x.get("retrieval_accuracy_proxy") is not None
            ]

            q_succ = sum(1 for x in q_evs if x.get("success") is True)
            q_fail = sum(1 for x in q_evs if x.get("success") is False)
            r_succ = sum(1 for x in r_evs if x.get("success") is True)
            r_fail = sum(1 for x in r_evs if x.get("success") is False)

            degraded_n = sum(1 for x in q_evs if x.get("degraded") is True)

            out.append(
                {
                    "bucket_start": bk,
                    "query_count": len(q_evs),
                    "retrieve_count": len(r_evs),
                    "avg_query_latency_ms": sum(qlats) / len(qlats) if qlats else 0.0,
                    "p95_query_latency_ms": _p95(qlats),
                    "avg_retrieval_latency_ms": sum(rlats) / len(rlats) if rlats else 0.0,
                    "p95_retrieval_latency_ms": _p95(rlats),
                    "avg_llm_latency_ms": sum(llats) / len(llats) if llats else 0.0,
                    "p95_llm_latency_ms": _p95(llats),
                    "avg_total_tokens": sum(toks_f) / len(toks_f) if toks_f else 0.0,
                    "avg_retrieval_accuracy_proxy": sum(proxies) / len(proxies) if proxies else 0.0,
                    "query_success_count": q_succ,
                    "query_failure_count": q_fail,
                    "retrieve_success_count": r_succ,
                    "retrieve_failure_count": r_fail,
                    "degraded_query_count": degraded_n,
                }
            )
        return out

    def _totals(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        q_evs = [x for x in events if x.get("kind") == "query"]
        r_evs = [x for x in events if x.get("kind") == "retrieve"]
        qlats = [float(x["query_latency_ms"]) for x in q_evs if x.get("query_latency_ms") is not None]
        succ_q = sum(1 for x in q_evs if x.get("success") is True)
        fail_q = sum(1 for x in q_evs if x.get("success") is False)
        denom = succ_q + fail_q
        return {
            "query_events": len(q_evs),
            "retrieve_events": len(r_evs),
            "avg_query_latency_ms": sum(qlats) / len(qlats) if qlats else 0.0,
            "p95_query_latency_ms": _p95(qlats),
            "success_rate": (succ_q / denom) if denom else 1.0,
            "failure_rate": (fail_q / denom) if denom else 0.0,
        }
