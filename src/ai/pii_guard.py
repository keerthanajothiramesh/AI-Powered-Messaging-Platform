"""PII detection and anonymization.

Uses Presidio when available (requires presidio-analyzer + spaCy en_core_web_sm).
Falls back to regex patterns when Presidio is not installed or the spaCy model
has not been downloaded yet.

Render build command to enable full Presidio:
    pip install -r requirements.txt && python -m spacy download en_core_web_sm
"""
import re
from typing import Tuple, List
from src.common.logger import get_logger

logger = get_logger(__name__)

# ─── Presidio (optional) ──────────────────────────────────────────────────────

_analyzer = None
_anonymizer = None
_presidio_ready = False


def init_pii_guard() -> bool:
    global _analyzer, _anonymizer, _presidio_ready
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
        _presidio_ready = True
        logger.info("pii_guard_ready", engine="presidio")
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

_ENTITIES = [
    "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "US_SSN", "PERSON", "LOCATION", "IP_ADDRESS",
]


def scan_and_anonymize(text: str) -> Tuple[str, List[str]]:
    """Return (anonymized_text, list_of_detected_entity_types).

    If no PII is found the original text is returned unchanged.
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
            # fall through to regex

    return _regex_scan(text)
