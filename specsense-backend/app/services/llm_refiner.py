from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama

from app.core.config import settings


class RefinementOutput(BaseModel):
    clarifying_question: str = Field(..., min_length=1)
    ears_rewrite: str = Field(..., min_length=1)


class LLMRefiner:
    def __init__(self) -> None:
        self.llm = ChatOllama(
            model="mistral",
            temperature=0,
            base_url=settings.OLLAMA_BASE_URL,
        )

    def generate_refinement(
        self,
        original_text: str,
        weak_words: list[str],
        has_passive: bool,
    ) -> dict[str, str]:
        prompt = PromptTemplate.from_template(
            """
You are a Senior Requirements Engineer.

Analyze the original requirement below and improve it for clarity, measurability, and testability.

Original requirement:
{original_text}

Detected weak words:
{weak_words}

Passive voice detected:
{has_passive}

Instructions:
1. Acknowledge the weak words and passive voice findings internally while refining.
2. Ask exactly one clarifying question focused on missing measurable criteria (metrics, thresholds, limits, timing, quantity, or accuracy).
3. Rewrite the requirement using EARS syntax.
4. Return only the structured fields requested.
""".strip()
        )

        structured_llm = self.llm.with_structured_output(RefinementOutput)
        chain = prompt | structured_llm

        result = chain.invoke(
            {
                "original_text": original_text,
                "weak_words": ", ".join(weak_words) if weak_words else "None",
                "has_passive": str(has_passive),
            }
        )

        return {
            "clarifying_question": result.clarifying_question,
            "ears_rewrite": result.ears_rewrite,
        }