class PromptBuilder:
    SYSTEM_PROMPT = "You are a grounded QA system. Answer ONLY using provided context."

    def build(self, question: str, context: list[str]) -> tuple[str, str]:
        context_blocks = "\n\n".join(f"[Chunk {idx + 1}]\n{text}" for idx, text in enumerate(context))
        user_prompt = (
            "CONTEXT:\n"
            f"{context_blocks}\n\n"
            "QUESTION:\n"
            f"{question}\n\n"
            'If context is insufficient, return exactly: "Not enough information in document".'
        )
        return self.SYSTEM_PROMPT, user_prompt
