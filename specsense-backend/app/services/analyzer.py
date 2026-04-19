from __future__ import annotations

import spacy
from spacy.language import Language
from spacy.tokens import Doc, Span


class RequirementAnalyzer:
    """Deterministic syntax analyzer for requirement quality checks."""

    WEAK_WORDS: tuple[str, ...] = (
        "fast",
        "robust",
        "seamless",
        "easy",
        "user-friendly",
        "approximately",
        "many",
    )

    def __init__(self) -> None:
        try:
            self.nlp: Language = spacy.load("en_core_web_sm")
        except OSError as exc:
            raise RuntimeError(
                "The spaCy model 'en_core_web_sm' is not installed. "
                "Install it with: python -m spacy download en_core_web_sm"
            ) from exc

    def analyze_syntax(self, text: str) -> dict[str, object]:
        doc = self.nlp(text)

        weak_words = self._extract_weak_words(doc)
        has_passive_voice = self._detect_passive_voice(doc)

        score = 100
        if has_passive_voice:
            score -= 10
        score -= 5 * len(weak_words)

        return {
            "score": score,
            "weak_words": weak_words,
            "has_passive_voice": has_passive_voice,
        }

    def _extract_weak_words(self, doc: Doc) -> list[str]:
        text_lower = doc.text.lower()
        found_words: list[str] = []

        for weak_word in self.WEAK_WORDS:
            if weak_word in text_lower and weak_word not in found_words:
                found_words.append(weak_word)

        return found_words

    def _detect_passive_voice(self, doc: Doc) -> bool:
        for token in doc:
            if token.dep_ == "auxpass" or "pass" in token.dep_:
                return True

        for sentence in doc.sents:
            if self._sentence_has_passive_voice(sentence):
                return True

        return False

    def _sentence_has_passive_voice(self, sentence: Span) -> bool:
        for token in sentence:
            if token.dep_ == "auxpass" or token.dep_ == "nsubjpass":
                return True

        return False