import json
import traceback
from itertools import combinations
from time import perf_counter
from typing import Any

import httpx

from app.request_context import current_request_id, current_request_metrics, current_request_path
from app.schemas.qa import CONFIDENCE_FORMULA_VERSION
from app.services.error_intelligence_store import ErrorIntelligenceStore, Severity
from app.services.llm_service import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.retrieval_engine import RetrievalEngine

_CONF_WEIGHT_SUPPORT = 0.25
_CONF_WEIGHT_RELEVANCE = 0.45
_CONF_WEIGHT_AGREEMENT = 0.30


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def evidence_span_for_paragraph_chunk(paragraph: str, chunk_text: str) -> tuple[int, int] | None:
    """Longest contiguous substring of paragraph found verbatim in chunk_text (deterministic)."""
    para = paragraph.strip()
    ct = chunk_text
    if not para or not ct:
        return None
    if para in ct:
        pos = ct.find(para)
        return (pos, pos + len(para))
    lp, lc = len(para), len(ct)
    max_len = min(lp, lc)
    min_len = min(5, max_len)
    for length in range(max_len, min_len - 1, -1):
        for i in range(lp - length + 1):
            sub = para[i : i + length]
            pos = ct.find(sub)
            if pos != -1:
                return (pos, pos + length)
    return None


def _token_set(text: str) -> set[str]:
    normalized = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return {w for w in normalized.split() if w}


def pairwise_token_jaccard(texts: list[str]) -> float:
    sets = [_token_set(t) for t in texts if str(t).strip()]
    if len(sets) <= 1:
        return 1.0 if sets else 0.0
    scores: list[float] = []
    for a, b in combinations(sets, 2):
        union = len(a | b)
        if union == 0:
            scores.append(1.0)
        else:
            scores.append(len(a & b) / union)
    return sum(scores) / len(scores)


def compute_answer_confidence(
    citation_blocks: list[dict[str, Any]],
    retrieved: list[dict[str, Any]],
    chunk_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    unique: set[str] = set()
    for block in citation_blocks:
        for cite in block.get("citations", []):
            unique.add(str(cite["chunk_id"]))

    max_raw = max((float(r["relevance_score"]) for r in retrieved), default=0.0)
    cap = max_raw if max_raw > 1e-12 else 1e-12

    rel_values: list[float] = []
    for cid in unique:
        row = chunk_by_id.get(cid)
        if row is not None:
            rel_values.append(float(row.get("relevance_score", 0.0)))
    rel_mean = sum(rel_values) / len(rel_values) if rel_values else 0.0
    relevance_component = min(1.0, max(0.0, rel_mean / cap))

    support_component = min(1.0, len(unique) / 3.0) if unique else 0.0

    texts = [str(chunk_by_id[cid].get("chunk_text", "")) for cid in sorted(unique) if cid in chunk_by_id]
    agreement_component = pairwise_token_jaccard(texts) if unique else 0.0

    score = (
        _CONF_WEIGHT_SUPPORT * support_component
        + _CONF_WEIGHT_RELEVANCE * relevance_component
        + _CONF_WEIGHT_AGREEMENT * agreement_component
    )
    score = min(1.0, max(0.0, score))

    return {
        "score": score,
        "formula_version": CONFIDENCE_FORMULA_VERSION,
        "supporting_unique_chunks": len(unique),
        "support_component": support_component,
        "relevance_component": relevance_component,
        "agreement_component": agreement_component,
        "relevance_mean_raw": rel_mean,
        "max_retrieval_score_raw": max_raw,
    }


def collect_evidence_spans(
    answer_parts: list[str],
    citation_blocks: list[dict[str, Any]],
    chunk_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    seen: set[tuple[int, str, int, int]] = set()
    for block in citation_blocks:
        pidx = int(block.get("paragraph_index", -1))
        if pidx < 0 or pidx >= len(answer_parts):
            continue
        para = answer_parts[pidx]
        for cite in block.get("citations", []):
            cid = str(cite.get("chunk_id", ""))
            did = str(cite.get("document_id", ""))
            chunk = chunk_by_id.get(cid)
            if chunk is None:
                continue
            ct = str(chunk.get("chunk_text", ""))
            span = evidence_span_for_paragraph_chunk(para, ct)
            if span is None:
                continue
            start, end = span
            excerpt = ct[start:end]
            key = (pidx, cid, start, end)
            if key in seen:
                continue
            seen.add(key)
            spans.append(
                {
                    "paragraph_index": pidx,
                    "chunk_id": cid,
                    "document_id": did,
                    "span_start": start,
                    "span_end": end,
                    "span_text": excerpt,
                }
            )
    return spans


def zero_confidence_payload() -> dict[str, Any]:
    return {
        "score": 0.0,
        "formula_version": CONFIDENCE_FORMULA_VERSION,
        "supporting_unique_chunks": 0,
        "support_component": 0.0,
        "relevance_component": 0.0,
        "agreement_component": 0.0,
        "relevance_mean_raw": 0.0,
        "max_retrieval_score_raw": 0.0,
    }


def _stamp_fault_tolerance(
    payload: dict[str, Any],
    *,
    degraded: bool,
    degraded_reason: str | None = None,
    llm_attempts: int | None = None,
    retrieval_degraded: bool = False,
) -> dict[str, Any]:
    stamped = dict(payload)
    stamped["degraded"] = degraded
    stamped["degraded_reason"] = degraded_reason
    stamped["llm_attempts"] = llm_attempts
    stamped["retrieval_degraded"] = retrieval_degraded
    return stamped


def fallback_answer_body(retrieved: list[dict[str, Any]], *, answer_mode: str) -> str:
    default_chunk = retrieved[0]
    text = str(default_chunk.get("chunk_text", "")).strip()
    if answer_mode.strip().lower() == "strict":
        return text[:2000] if text else "Not enough information in document"
    if len(text) > 1200:
        return f"Based on the retrieved context: {text[:1200]}..."
    return f"Based on the retrieved context: {text}" if text else "Not enough information in document"


class RAGPipelineService:
    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        error_intel_store: ErrorIntelligenceStore | None = None,
    ) -> None:
        self.retrieval_engine = retrieval_engine
        self.prompt_builder = prompt_builder
        self.llm_service = llm_service
        self._error_intel = error_intel_store

    def _intel_endpoint(self) -> str:
        return current_request_path.get() or "/query"

    def _record_retrieval_flags(self, retrieval_flags: dict[str, Any]) -> None:
        if self._error_intel is None:
            return
        rid = current_request_id.get()
        if retrieval_flags.get("vector_unavailable"):
            self._error_intel.record(
                error_type="retrieval",
                severity="error",
                endpoint=self._intel_endpoint(),
                message="Vector retrieval unavailable (embedding/search failure in vector-only mode).",
                request_id=rid,
                extra={"flags": dict(retrieval_flags)},
            )
        elif retrieval_flags.get("embedding_skipped"):
            self._error_intel.record(
                error_type="retrieval",
                severity="warning",
                endpoint=self._intel_endpoint(),
                message="Embedding or vector search failed — degraded to keyword retrieval where applicable.",
                request_id=rid,
                extra={"flags": dict(retrieval_flags)},
            )

    def _record_llm_issue(self, *, reason: str, exc: BaseException | None = None) -> None:
        if self._error_intel is None:
            return
        rid = current_request_id.get()
        sev: Severity = "error" if reason == "llm_unavailable" else "warning"
        stack = (
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            if exc is not None
            else None
        )
        self._error_intel.record(
            error_type="llm",
            severity=sev,
            endpoint=self._intel_endpoint(),
            message=f"LLM degradation: {reason}",
            request_id=rid,
            stack_trace=stack,
            extra={"degraded_reason": reason},
        )

    def _with_explainability(
        self,
        payload: dict[str, Any],
        *,
        answer_parts: list[str],
        retrieved: list[dict[str, Any]],
        chunk_by_id: dict[str, dict[str, Any]],
        usage_document_ids: list[str],
    ) -> dict[str, Any]:
        cites = payload.get("citations")
        if not isinstance(cites, list):
            cites = []
        confidence = compute_answer_confidence(cites, retrieved, chunk_by_id) if cites else zero_confidence_payload()
        evidence = collect_evidence_spans(answer_parts, cites, chunk_by_id) if cites else []
        return {
            **payload,
            "confidence": confidence,
            "evidence_spans": evidence,
            "usage_document_ids": usage_document_ids,
        }

    async def run_query_flow(
        self,
        question: str,
        document_id: str | None,
        top_k: int,
        *,
        metadata_by_index_document_id: dict[str, dict[str, object]] | None = None,
        retrieval_mode: str = "hybrid",
        answer_mode: str = "flexible",
        answer_length: str = "medium",
    ) -> dict[str, Any]:
        sink = current_request_metrics.get()

        tr = perf_counter()
        retrieved, retrieval_flags = await self.retrieval_engine.retrieve(
            query=question,
            document_id=document_id,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            metadata_by_index_document_id=metadata_by_index_document_id,
        )
        if sink is not None:
            sink["retrieval_ms"] = (perf_counter() - tr) * 1000
            sink["chunks_returned"] = len(retrieved)
            if retrieved:
                top_rows = retrieved[:top_k]
                scores = [float(row.get("relevance_score", 0.0)) for row in top_rows]
                sink["retrieval_accuracy_proxy"] = sum(scores) / len(scores) if scores else None
            else:
                sink["retrieval_accuracy_proxy"] = None

        self._record_retrieval_flags(retrieval_flags)
        retrieval_degraded = bool(retrieval_flags.get("embedding_skipped"))
        if not retrieved:
            if sink is not None:
                sink["llm_ms"] = 0.0
            return _stamp_fault_tolerance(
                {
                    "answer": "Not enough information in document",
                    "citations": [],
                    "confidence": zero_confidence_payload(),
                    "evidence_spans": [],
                    "usage_document_ids": [],
                },
                degraded=False,
                degraded_reason=None,
                llm_attempts=None,
                retrieval_degraded=retrieval_degraded,
            )

        usage_document_ids = sorted({str(row["document_id"]) for row in retrieved})
        chunk_by_id = {str(row["chunk_id"]): row for row in retrieved}
        default_chunk = retrieved[0]
        default_citation = {
            "chunk_id": str(default_chunk["chunk_id"]),
            "document_id": str(default_chunk["document_id"]),
        }

        system_prompt, user_prompt = self.prompt_builder.build_answer(
            question,
            retrieved,
            answer_mode=answer_mode,
            answer_length=answer_length,
        )

        llm_meta: dict[str, Any] = {}

        def _merge_llm_tokens_into_sink() -> None:
            if sink is None:
                return
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if llm_meta.get(key) is not None:
                    sink[key] = llm_meta[key]

        def _degraded_llm_result(reason: str) -> dict[str, Any]:
            fb_body = fallback_answer_body(retrieved, answer_mode=answer_mode)
            attempts_raw = llm_meta.get("llm_attempts")
            attempts = attempts_raw if isinstance(attempts_raw, int) else None
            return _stamp_fault_tolerance(
                self._with_explainability(
                    self._fallback_answer(retrieved, answer_mode=answer_mode),
                    answer_parts=[fb_body],
                    retrieved=retrieved,
                    chunk_by_id=chunk_by_id,
                    usage_document_ids=usage_document_ids,
                ),
                degraded=True,
                degraded_reason=reason,
                llm_attempts=attempts,
                retrieval_degraded=retrieval_degraded,
            )

        t_llm = perf_counter()
        try:
            parsed = await self.llm_service.answer_json(system_prompt, user_prompt, meta=llm_meta)
        except httpx.HTTPError as http_exc:
            if sink is not None:
                sink["llm_ms"] = (perf_counter() - t_llm) * 1000
            self._record_llm_issue(reason="llm_unavailable", exc=http_exc)
            return _degraded_llm_result("llm_unavailable")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as parse_exc:
            if sink is not None:
                sink["llm_ms"] = (perf_counter() - t_llm) * 1000
            self._record_llm_issue(reason="llm_response_invalid", exc=parse_exc)
            return _degraded_llm_result("llm_response_invalid")
        else:
            if sink is not None:
                sink["llm_ms"] = (perf_counter() - t_llm) * 1000
                _merge_llm_tokens_into_sink()

        paragraphs_raw = parsed.get("paragraphs")
        if not isinstance(paragraphs_raw, list) or not paragraphs_raw:
            self._record_llm_issue(reason="llm_response_invalid")
            fb_body = fallback_answer_body(retrieved, answer_mode=answer_mode)
            return _stamp_fault_tolerance(
                self._with_explainability(
                    self._fallback_answer(retrieved, answer_mode=answer_mode),
                    answer_parts=[fb_body],
                    retrieved=retrieved,
                    chunk_by_id=chunk_by_id,
                    usage_document_ids=usage_document_ids,
                ),
                degraded=True,
                degraded_reason="llm_response_invalid",
                llm_attempts=llm_meta.get("llm_attempts") if isinstance(llm_meta.get("llm_attempts"), int) else None,
                retrieval_degraded=retrieval_degraded,
            )

        citation_blocks: list[dict[str, Any]] = []
        answer_parts: list[str] = []

        mode_lower = answer_mode.strip().lower()

        for block in paragraphs_raw:
            if not isinstance(block, dict):
                continue
            text = str(block.get("text", "")).strip()
            cites_raw = block.get("citations")
            cites = cites_raw if isinstance(cites_raw, list) else []

            fixed_citations = self._sanitize_citations(cites, chunk_by_id, default_citation)
            if mode_lower == "strict":
                text = self._enforce_strict_paragraph(text, fixed_citations, chunk_by_id)

            if not fixed_citations:
                fixed_citations = [dict(default_citation)]

            if not str(text).strip():
                continue

            paragraph_index = len(answer_parts)
            answer_parts.append(text)
            citation_blocks.append({"paragraph_index": paragraph_index, "citations": fixed_citations})

        if not answer_parts:
            self._record_llm_issue(reason="llm_response_invalid")
            fb_body = fallback_answer_body(retrieved, answer_mode=answer_mode)
            fb = self._fallback_answer(retrieved, answer_mode=answer_mode)
            return _stamp_fault_tolerance(
                self._with_explainability(
                    fb,
                    answer_parts=[fb_body],
                    retrieved=retrieved,
                    chunk_by_id=chunk_by_id,
                    usage_document_ids=usage_document_ids,
                ),
                degraded=True,
                degraded_reason="llm_response_invalid",
                llm_attempts=llm_meta.get("llm_attempts") if isinstance(llm_meta.get("llm_attempts"), int) else None,
                retrieval_degraded=retrieval_degraded,
            )

        base = {"answer": "\n\n".join(answer_parts), "citations": citation_blocks}
        return _stamp_fault_tolerance(
            self._with_explainability(
                base,
                answer_parts=answer_parts,
                retrieved=retrieved,
                chunk_by_id=chunk_by_id,
                usage_document_ids=usage_document_ids,
            ),
            degraded=False,
            degraded_reason=None,
            llm_attempts=llm_meta.get("llm_attempts") if isinstance(llm_meta.get("llm_attempts"), int) else None,
            retrieval_degraded=retrieval_degraded,
        )

    def _sanitize_citations(
        self,
        cites: list[Any],
        chunk_by_id: dict[str, dict[str, Any]],
        default: dict[str, str],
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for item in cites:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("chunk_id", "")).strip()
            did = str(item.get("document_id", "")).strip()
            if cid in chunk_by_id:
                row = chunk_by_id[cid]
                out.append({"chunk_id": cid, "document_id": str(row.get("document_id", did))})
        if not out:
            return [dict(default)]
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, str]] = []
        for c in out:
            key = (c["chunk_id"], c["document_id"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        return deduped

    def _enforce_strict_paragraph(
        self,
        text: str,
        citations: list[dict[str, str]],
        chunk_by_id: dict[str, dict[str, Any]],
    ) -> str:
        normalized_para = _normalize_ws(text)
        if not normalized_para:
            first_id = citations[0]["chunk_id"]
            return str(chunk_by_id.get(first_id, {}).get("chunk_text", "")).strip()

        pool: list[str] = []
        for cite in citations:
            chunk = chunk_by_id.get(cite["chunk_id"])
            if chunk:
                pool.append(_normalize_ws(str(chunk.get("chunk_text", ""))))

        for chunk_norm in pool:
            if normalized_para in chunk_norm:
                return text

        longest = ""
        for chunk_norm in pool:
            if chunk_norm in normalized_para and len(chunk_norm) > len(longest):
                longest = chunk_norm
        if longest:
            return longest

        first_chunk = chunk_by_id.get(citations[0]["chunk_id"])
        if first_chunk:
            excerpt = str(first_chunk.get("chunk_text", "")).strip()
            return excerpt[:500] if excerpt else text
        return text

    def _fallback_answer(
        self,
        retrieved: list[dict[str, Any]],
        *,
        answer_mode: str,
    ) -> dict[str, Any]:
        default_chunk = retrieved[0]
        cite = {"chunk_id": str(default_chunk["chunk_id"]), "document_id": str(default_chunk["document_id"])}
        body = fallback_answer_body(retrieved, answer_mode=answer_mode)
        return {
            "answer": body,
            "citations": [{"paragraph_index": 0, "citations": [cite]}],
        }
