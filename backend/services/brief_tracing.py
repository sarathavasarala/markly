"""Portable Daily Brief tracing adapters.

The Signal pipeline records Markly-owned trace events through this module. Langfuse
is the first sink, but the route layer does not depend on Langfuse directly.
"""
from __future__ import annotations

import hashlib
import logging
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any

from config import Config
from database import new_id, utc_now

logger = logging.getLogger(__name__)

TRACE_SCHEMA_VERSION = 1
PROMPT_VERSION = "signal-v1"


def _count_words(value: str | None) -> int:
    return len((value or "").split())


def _hash_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_item(item: dict[str, Any], *, include_content: bool = False) -> dict[str, Any]:
    out = {
        "id": item.get("id"),
        "url": item.get("url"),
        "title": item.get("title"),
        "summary": item.get("summary"),
        "feed_title": item.get("feed_title"),
        "sort_ts": item.get("sort_ts"),
        "published_at": item.get("published_at"),
        "first_seen_at": item.get("first_seen_at"),
        "status": item.get("status"),
        "has_embedding": bool(item.get("embedding")),
    }
    if include_content:
        content = _truncate_signal_content(item.get("content"))
        out.update({
            "content": content,
            "content_format": item.get("content_format"),
            "content_word_count": _count_words(content),
            "content_sha256": _hash_text(content),
        })
    return {key: value for key, value in out.items() if value is not None}


def _truncate_signal_content(content: str | None) -> str:
    if not content:
        return "No content extracted"
    if len(content) <= Config.SIGNAL_CONTENT_MAX_CHARS:
        return content
    first_part = content[: Config.SIGNAL_CONTENT_HEAD_CHARS]
    last_part = content[-Config.SIGNAL_CONTENT_TAIL_CHARS:]
    return f"{first_part}\n\n[... middle content truncated ...]\n\n{last_part}"


def summarize_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_safe_item(item) for item in items]


def summarize_selected_items(items: list[dict[str, Any]], *, include_content: bool = False) -> list[dict[str, Any]]:
    return [_safe_item(item, include_content=include_content) for item in items]


def summarize_selected_item_refs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for item in items:
        content = _truncate_signal_content(item.get("content"))
        refs.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "feed_title": item.get("feed_title"),
            "content_word_count": _count_words(content),
            "content_sha256": _hash_text(content),
        })
    return refs


def summarize_text(value: str | None) -> dict[str, Any]:
    return {
        "content": value or "",
        "word_count": _count_words(value),
        "sha256": _hash_text(value),
    }


def summarize_content_updates(updates: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "updated_count": len(updates),
        "items": [
            {
                "id": item_id,
                "content_format": content_format,
                "content_word_count": _count_words(content),
                "content_sha256": _hash_text(content),
            }
            for item_id, content, content_format in updates
        ],
    }


def summarize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_limit": settings.get("candidate_limit"),
        "synthesis_limit": settings.get("synthesis_limit"),
        "planning_enabled": settings.get("planning_enabled"),
        "web_search_enabled": settings.get("web_search_enabled"),
        "prompt_version": PROMPT_VERSION,
        "filter_prompt_sha256": _hash_text(settings.get("filter_template")),
        "planning_prompt_sha256": _hash_text(settings.get("planning_template")),
        "synthesis_prompt_sha256": _hash_text(settings.get("synthesis_template")),
        "taste_profile_sha256": _hash_text(settings.get("taste_profile")),
        "recent_briefs": settings.get("recent_briefs"),
    }


def runtime_config() -> dict[str, Any]:
    return {
        "enable_embeddings": Config.ENABLE_EMBEDDINGS,
        "signal_candidate_pool_multiplier": Config.SIGNAL_CANDIDATE_POOL_MULTIPLIER,
        "signal_briefed_exclude_days": Config.SIGNAL_BRIEFED_EXCLUDE_DAYS,
        "signal_embed_min_coverage": Config.SIGNAL_EMBED_MIN_COVERAGE,
        "signal_content_max_chars": Config.SIGNAL_CONTENT_MAX_CHARS,
        "signal_content_head_chars": Config.SIGNAL_CONTENT_HEAD_CHARS,
        "signal_content_tail_chars": Config.SIGNAL_CONTENT_TAIL_CHARS,
        "signal_humanizer_enabled": Config.SIGNAL_HUMANIZER_ENABLED,
        "signal_model": Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME or Config.AZURE_OPENAI_DEPLOYMENT_NAME,
    }


class TraceObservation(AbstractContextManager):
    def update(self, *, input: Any = None, output: Any = None, metadata: dict[str, Any] | None = None):
        return None

    def end(self):
        return None

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc is not None:
            self.update(metadata={"error": str(exc), "error_type": type(exc).__name__})
        self.end()
        return False


class BriefTrace(AbstractContextManager):
    def __init__(self, *, user_id: str, mode: str):
        self.run_id = new_id()
        self.user_id = user_id
        self.mode = mode
        self.started_at = utc_now()

    def span(self, name: str, *, input: Any = None, metadata: dict[str, Any] | None = None) -> TraceObservation:
        return TraceObservation()

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceObservation:
        return TraceObservation()

    def event(self, name: str, *, input: Any = None, output: Any = None, metadata: dict[str, Any] | None = None):
        return None

    def finish(self, *, brief: dict[str, Any] | None = None, output: Any = None):
        return None

    def fail(self, *, stage: str, exc: BaseException):
        return None

    def flush(self):
        return None

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc is not None:
            self.fail(stage="unhandled", exc=exc)
        self.flush()
        return False


class NoopBriefTrace(BriefTrace):
    pass


class LangfuseObservation(TraceObservation):
    def __init__(self, manager: Any, observation: Any):
        self.manager = manager
        self.observation = observation
        self.closed = False

    def update(self, *, input: Any = None, output: Any = None, metadata: dict[str, Any] | None = None):
        payload: dict[str, Any] = {}
        if input is not None:
            payload["input"] = input
        if output is not None:
            payload["output"] = output
        if metadata:
            payload["metadata"] = metadata
        if payload:
            self.observation.update(**payload)

    def end(self):
        if self.closed:
            return
        self.closed = True
        self.manager.__exit__(None, None, None)

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc is not None:
            self.update(metadata={"error": str(exc), "error_type": type(exc).__name__})
        if self.closed:
            return False
        self.closed = True
        self.manager.__exit__(exc_type, exc, tb)
        return False


class LangfuseBriefTrace(BriefTrace):
    def __init__(self, *, user_id: str, mode: str):
        super().__init__(user_id=user_id, mode=mode)
        from langfuse import get_client

        self.client = get_client()
        self.root = self.client.start_as_current_observation(
            as_type="span",
            name="daily_brief_generation",
            input={"mode": mode, "schema_version": TRACE_SCHEMA_VERSION},
        )
        self.root_observation = self.root.__enter__()
        self.closed = False
        self.root_observation.update_trace(
            name="daily_brief_generation",
            user_id=user_id,
            session_id=f"daily-brief:{user_id}",
            metadata={
                "schema_version": TRACE_SCHEMA_VERSION,
                "run_id": self.run_id,
                "mode": mode,
                "started_at": self.started_at,
                "runtime": runtime_config(),
            },
            tags=["markly", "daily-brief", mode],
            version=PROMPT_VERSION,
        )

    def span(self, name: str, *, input: Any = None, metadata: dict[str, Any] | None = None) -> TraceObservation:
        manager = self.client.start_as_current_observation(
            as_type="span",
            name=name,
            input=input,
            metadata=metadata,
        )
        return LangfuseObservation(manager, manager.__enter__())

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceObservation:
        manager = self.client.start_as_current_observation(
            as_type="generation",
            name=name,
            model=model,
            input=input,
            metadata=metadata,
        )
        return LangfuseObservation(manager, manager.__enter__())

    def event(self, name: str, *, input: Any = None, output: Any = None, metadata: dict[str, Any] | None = None):
        with self.client.start_as_current_observation(
            as_type="event",
            name=name,
            input=input,
            metadata=metadata,
        ) as event:
            if output is not None:
                event.update(output=output)

    def finish(self, *, brief: dict[str, Any] | None = None, output: Any = None):
        trace_metadata = {
            "status": "completed",
            "brief_id": brief.get("id") if brief else None,
            "brief_title": brief.get("title") if brief else None,
        }
        self.root_observation.update(
            output=output or brief,
            metadata={key: value for key, value in trace_metadata.items() if value is not None},
        )
        self.root_observation.update_trace(output=output or brief, metadata=trace_metadata)

    def fail(self, *, stage: str, exc: BaseException):
        metadata = {
            "status": "failed",
            "error_stage": stage,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        self.root_observation.update(metadata=metadata)
        self.root_observation.update_trace(metadata=metadata)

    def flush(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.root.__exit__(None, None, None)
            self.client.flush()
        except Exception as exc:
            logger.warning("Failed to flush Langfuse Daily Brief trace: %s", exc)


def _langfuse_configured() -> bool:
    return bool(Config.LANGFUSE_PUBLIC_KEY and Config.LANGFUSE_SECRET_KEY)


def start_daily_brief_trace(*, user_id: str, mode: str) -> BriefTrace:
    if not Config.BRIEF_TRACING_ENABLED:
        return NoopBriefTrace(user_id=user_id, mode=mode)

    if Config.BRIEF_TRACE_SINK != "langfuse":
        return NoopBriefTrace(user_id=user_id, mode=mode)

    if not _langfuse_configured():
        logger.warning("BRIEF_TRACING_ENABLED=true but Langfuse credentials are missing")
        return NoopBriefTrace(user_id=user_id, mode=mode)

    try:
        return LangfuseBriefTrace(user_id=user_id, mode=mode)
    except Exception as exc:
        logger.warning("Failed to start Langfuse Daily Brief trace: %s", exc)
        return NoopBriefTrace(user_id=user_id, mode=mode)
