"""Deterministic SEARCH/REPLACE patcher for Markdown prose text.

apply_search_replace(text, search, replace)
  -> (new_text, True,  context_info)   on success – text is modified
  -> (text,     False, reason)         on failure  – text is unchanged

Strategy:
  1. Exact substring match (fast path).
  2. Fuzzy match via diff-match-patch (handles minor quote/whitespace/Unicode
     variants that arise when a model slightly mis-transcribes the source text).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# How tolerant the fuzzy matcher is (0 = exact match only, 1 = anything).
# 0.25 is deliberately strict: the model has seen the exact draft text, so
# search strings should be near-verbatim. Only minor quote/whitespace variants
# should pass; completely different strings must be rejected.
_FUZZY_THRESHOLD = 0.25
# Max character distance from the expected location to search.
_FUZZY_DISTANCE = 1000


def apply_search_replace(text: str, search: str, replace: str) -> tuple[str, bool, str]:
    """Find *search* in *text* and replace its first occurrence with *replace*.

    Returns:
        (new_text, True,  context)  – success, text is modified.
        (text,     False, reason)   – failure, text is NOT modified.
    """
    if not search:
        return text, False, "empty_search"

    # ------------------------------------------------------------------
    # 1. Exact match (fast path)
    # ------------------------------------------------------------------
    idx = text.find(search)
    if idx != -1:
        new_text = text[:idx] + replace + text[idx + len(search):]
        return new_text, True, f"exact@{idx}"

    # ------------------------------------------------------------------
    # 2. Fuzzy match via diff-match-patch
    # ------------------------------------------------------------------
    try:
        from diff_match_patch import diff_match_patch  # noqa: PLC0415

        dmp = diff_match_patch()
        dmp.Match_Threshold = _FUZZY_THRESHOLD
        dmp.Match_Distance = _FUZZY_DISTANCE

        match_idx = dmp.match_main(text, search, 0)
        if match_idx == -1:
            return text, False, "not_found"

        # The matched span length is approximately len(search); minor differences
        # (extra/missing whitespace, different quote characters) are within the
        # fuzzy threshold and acceptable for prose style edits.
        matched_end = match_idx + len(search)
        new_text = text[:match_idx] + replace + text[matched_end:]
        return new_text, True, f"fuzzy@{match_idx}"

    except ImportError:
        logger.warning("diff-match-patch not installed; fuzzy matching unavailable")
        return text, False, "not_found"
    except Exception as exc:
        logger.warning("text_patch fuzzy match error: %s", exc)
        return text, False, f"error:{type(exc).__name__}"
