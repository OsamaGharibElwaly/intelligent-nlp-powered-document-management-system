import json
from typing import Any


class PromptBuilder:
    SYSTEM_GROUNDED = "You are a grounded QA system. Follow instructions exactly."

    def build_answer(
        self,
        question: str,
        chunks: list[dict[str, Any]],
        *,
        answer_mode: str,
        answer_length: str,
    ) -> tuple[str, str]:
        mode = answer_mode.strip().lower()
        length = answer_length.strip().lower()

        length_rules = {
            "short": "Produce 1–2 short paragraphs (about 2–6 sentences total). Stay concise.",
            "medium": "Produce 2–4 paragraphs of moderate depth.",
            "detailed": "Produce 4–8 paragraphs with fuller coverage where the context allows.",
        }.get(length, "Produce 2–4 paragraphs of moderate depth.")

        context_blocks: list[str] = []
        for row in chunks:
            cid = str(row.get("chunk_id", ""))
            did = str(row.get("document_id", ""))
            text = str(row.get("chunk_text", row.get("text", "")))
            context_blocks.append(f"[chunk_id={cid} document_id={did}]\n{text}")

        context_blob = "\n\n".join(context_blocks)

        schema_hint = {
            "paragraphs": [
                {
                    "text": "paragraph body",
                    "citations": [{"chunk_id": "must match a chunk_id from CONTEXT", "document_id": "matching document_id"}],
                }
            ]
        }

        if mode == "strict":
            mode_rules = (
                "ANSWER MODE: STRICT.\n"
                "- Each paragraph must contain ONLY verbatim excerpts copied exactly from the CONTEXT chunks "
                "(you may join excerpts with single spaces or newlines; do not paraphrase).\n"
                "- Do not state facts that do not appear verbatim in CONTEXT.\n"
                "- Every paragraph MUST include at least one citation entry pointing to the chunk(s) "
                "that contain the verbatim text used in that paragraph.\n"
            )
        else:
            mode_rules = (
                "ANSWER MODE: FLEXIBLE.\n"
                "- You may synthesize and explain ideas across chunks while staying grounded in CONTEXT.\n"
                "- Do not invent facts absent from CONTEXT.\n"
                "- Every paragraph MUST cite at least one chunk that supports that paragraph.\n"
            )

        user_prompt = (
            f"{mode_rules}\n"
            f"LENGTH: {length_rules}\n\n"
            "CONTEXT:\n"
            f"{context_blob}\n\n"
            "QUESTION:\n"
            f"{question.strip()}\n\n"
            "Respond with a single JSON object only (no markdown fences). Shape:\n"
            f"{json.dumps(schema_hint, indent=2)}\n\n"
            'If CONTEXT is insufficient to answer, set paragraphs to one entry with text exactly '
            '"Not enough information in document" and citations to the first CONTEXT chunk if any, else '
            '{"chunk_id":"unknown","document_id":"unknown"}.'
        )

        system_prompt = (
            f"{self.SYSTEM_GROUNDED}\n"
            "Output valid JSON only. Each paragraph must include citations that reference chunk_id and "
            "document_id labels from CONTEXT."
        )
        return system_prompt, user_prompt
