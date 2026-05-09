from itertools import combinations
from typing import Any

import httpx

from app.schemas.qa import CONFIDENCE_FORMULA_VERSION
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
    ) -> None:
        self.retrieval_engine = retrieval_engine
        self.prompt_builder = prompt_builder
        self.llm_service = llm_service

    def _with_explainability(
        self,
        payload: dict[str, Any],
        *,
        answer_parts: list[str],
        retrieved: list[dict[str, Any]],
        chunk_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        cites = payload.get("citations")
        if not isinstance(cites, list):
            cites = []
        confidence = compute_answer_confidence(cites, retrieved, chunk_by_id) if cites else zero_confidence_payload()
        evidence = collect_evidence_spans(answer_parts, cites, chunk_by_id) if cites else []
        return {**payload, "confidence": confidence, "evidence_spans": evidence}

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
        retrieved = await self.retrieval_engine.retrieve(
            query=question,
            document_id=document_id,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            metadata_by_index_document_id=metadata_by_index_document_id,
        )
        if not retrieved:
            return {
                "answer": "Not enough information in document",
                "citations": [],
                "confidence": zero_confidence_payload(),
                "evidence_spans": [],
            }

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

        try:
            parsed = await self.llm_service.answer_json(system_prompt, user_prompt)
        except (ValueError, KeyError, TypeError, httpx.HTTPError):
            fb_body = fallback_answer_body(retrieved, answer_mode=answer_mode)
            return self._with_explainability(
                self._fallback_answer(retrieved, answer_mode=answer_mode),
                answer_parts=[fb_body],
                retrieved=retrieved,
                chunk_by_id=chunk_by_id,
            )

        paragraphs_raw = parsed.get("paragraphs")
        if not isinstance(paragraphs_raw, list) or not paragraphs_raw:
            fb_body = fallback_answer_body(retrieved, answer_mode=answer_mode)
            return self._with_explainability(
                self._fallback_answer(retrieved, answer_mode=answer_mode),
                answer_parts=[fb_body],
                retrieved=retrieved,
                chunk_by_id=chunk_by_id,
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
            fb_body = fallback_answer_body(retrieved, answer_mode=answer_mode)
            fb = self._fallback_answer(retrieved, answer_mode=answer_mode)
            return self._with_explainability(
                fb,
                answer_parts=[fb_body],
                retrieved=retrieved,
                chunk_by_id=chunk_by_id,
            )

        base = {"answer": "\n\n".join(answer_parts), "citations": citation_blocks}
        return self._with_explainability(base, answer_parts=answer_parts, retrieved=retrieved, chunk_by_id=chunk_by_id)

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
