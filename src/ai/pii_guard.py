"""PII detection and anonymization via Presidio pattern recognizers with a regex fallback when unavailable."""
import re
from typing import Tuple, List
from src.common.logger import get_logger

logger = get_logger(__name__)

_analyzer = None
_anonymizer = None
_presidio_ready = False


# ─── Lightweight NLP engine shim ─────────────────────────────────────────────

class _NoOpNlpEngine:
    """Presidio NLP engine that does nothing — no spaCy model, no memory cost.

    Presidio's pattern-based recognizers (EmailRecognizer, PhoneRecognizer,
    etc.) run their own regex and do not call process_text at all, so this
    stub is sufficient to satisfy the AnalyzerEngine interface.
    """

    supported_languages = ["en"]

    def load(self) -> None:
        pass

    def is_loaded(self, language: str) -> bool:
        return True

    def process_text(self, text: str, language: str):
        from presidio_analyzer.nlp_engine import NlpArtifacts
        return NlpArtifacts(
            entities=[],
            tokens=[],
            tokens_indices=[],
            lemmas=[],
            nlp_engine=self,
            score_cutoff=0,
        )

    def process_batch(self, texts, language, **kwargs):
        for text in texts:
            yield text, self.process_text(text, language)


# ─── Init ─────────────────────────────────────────────────────────────────────

def init_pii_guard() -> bool:
    global _analyzer, _anonymizer, _presidio_ready
    try:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_anonymizer import AnonymizerEngine

        nlp_engine = _NoOpNlpEngine()

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)

        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
        _anonymizer = AnonymizerEngine()
        _presidio_ready = True
        logger.info("pii_guard_ready", engine="presidio_pattern_only")
    except Exception as e:
        _presidio_ready = False
        logger.info("pii_guard_ready", engine="regex_fallback", reason=str(e)[:80])
    return _presidio_ready


# ─── Regex fallback ───────────────────────────────────────────────────────────

_REGEX_PII: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '<EMAIL_ADDRESS>'),
    (re.compile(r'\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b'), '<PHONE_NUMBER>'),
    (re.compile(r'\b(?:\d[ -]?){13,16}\b'), '<CREDIT_CARD>'),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '<US_SSN>'),
    (re.compile(r'\b[A-Z]{2}\d{6}[A-Z]?\b'), '<PASSPORT>'),
]


def _regex_scan(text: str) -> Tuple[str, List[str]]:
    detected: List[str] = []
    result = text
    for pattern, placeholder in _REGEX_PII:
        if pattern.search(result):
            detected.append(placeholder.strip('<>'))
            result = pattern.sub(placeholder, result)
    return result, detected


# ─── Public API ───────────────────────────────────────────────────────────────

# Pattern-only entities — no PERSON/LOCATION since those require spaCy NER
_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
]


def scan_and_anonymize(text: str) -> Tuple[str, List[str]]:
    """Return (anonymized_text, list_of_detected_entity_types).

    Uses Presidio pattern recognizers when available, regex otherwise.
    """
    if not text:
        return text, []

    if _presidio_ready and _analyzer and _anonymizer:
        try:
            results = _analyzer.analyze(text=text, entities=_ENTITIES, language="en")
            if not results:
                return text, []
            detected = list({r.entity_type for r in results})
            anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
            logger.info("pii_detected", types=detected, engine="presidio")
            return anonymized.text, detected
        except Exception as e:
            logger.warning("presidio_scan_failed", error=str(e))

    return _regex_scan(text)
