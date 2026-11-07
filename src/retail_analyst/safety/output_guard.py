"""The last safety layer: removes personal data from an answer before display.

Presidio does not promise to find every piece of personal data, so it backs up
the SQL guard rather than replacing it. Strings that came from query results
are allowed, since those results never contain personal columns.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from retail_analyst.core.config import Safety

SPACY_MODEL = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}


@dataclass(frozen=True)
class GuardResult:
    text: str
    removed: list[str]  # entity types, never the values


@lru_cache(maxsize=1)
def _analyzer() -> AnalyzerEngine:
    # Presidio logs a warning for every recognizer of a language we do not load.
    logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
    nlp_engine = NlpEngineProvider(nlp_configuration=SPACY_MODEL).create_engine()
    return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])


def redact(text: str, safety: Safety, allowed: set[str]) -> GuardResult:
    findings = _analyzer().analyze(
        text=text,
        language="en",
        entities=safety.output_entities,
        score_threshold=safety.output_score_threshold,
        allow_list=sorted(allowed),
    )
    # Replace from the end so earlier offsets stay valid; skip overlaps.
    removed: list[str] = []
    end_of_previous = len(text) + 1
    for finding in sorted(findings, key=lambda f: f.start, reverse=True):
        if finding.end > end_of_previous:
            continue
        words = len(text[finding.start : finding.end].split())
        if finding.entity_type == "PERSON" and words < safety.person_min_words:
            continue
        text = text[: finding.start] + safety.output_replacement + text[finding.end :]
        removed.append(finding.entity_type)
        end_of_previous = finding.start
    return GuardResult(text=text, removed=removed)


def redact_strings(value: object, safety: Safety, allowed: set[str]) -> object:
    """Applies redact to every string inside nested lists and dicts, such as a report."""
    if isinstance(value, str):
        return redact(value, safety, allowed).text
    if isinstance(value, list):
        return [redact_strings(item, safety, allowed) for item in value]
    if isinstance(value, dict):
        return {key: redact_strings(item, safety, allowed) for key, item in value.items()}
    return value


def result_strings(tool_outputs: list[str]) -> set[str]:
    """Collects the text values found in run_sql results."""
    found: set[str] = set()
    for output in tool_outputs:
        try:
            entries = json.loads(output)
        except json.JSONDecodeError:
            continue
        for entry in entries if isinstance(entries, list) else []:
            for row in entry.get("rows", []) if isinstance(entry, dict) else []:
                found.update(value for value in row.values() if isinstance(value, str))
    return found
