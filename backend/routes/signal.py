"""Signal routes (thin wrappers over services.signal_pipeline)."""
from __future__ import annotations

import json
import logging
from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from database import db_session, get_db, utc_now, rows_to_dicts, new_id
from middleware.auth import require_auth
from services import signal_pipeline
from services import brief_tracing
from services.signal_pipeline import _resolve_taste_profile
from config import Prompts

logger = logging.getLogger(__name__)

signal_bp = Blueprint("signal", __name__)


def log_telemetry_error(user_id: str, stage: str, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    error_msg = str(exc)
    log_id = new_id()
    created_at = utc_now()
    try:
        with db_session() as conn:
            conn.execute(
                "INSERT INTO telemetry_logs (id, user_id, stage, error_message, traceback, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (log_id, user_id, stage, error_msg, tb, created_at)
            )
    except Exception as db_exc:
        logger.error(f"Failed to save telemetry log to database: {db_exc}")


# ---------------------------------------------------------------------------
# Prompt templates (shared by the blocking and streaming pipelines)
# ---------------------------------------------------------------------------

FILTER_PROMPT_TEMPLATE = Prompts.FILTER_PROMPT_TEMPLATE
PLANNING_PROMPT_TEMPLATE = Prompts.PLANNING_PROMPT_TEMPLATE
SYNTHESIS_PROMPT_TEMPLATE = Prompts.SYNTHESIS_PROMPT_TEMPLATE
HUMANIZER_PROMPT_TEMPLATE = Prompts.HUMANIZER_PROMPT_TEMPLATE
DEFAULT_TASTE_PROFILE = Prompts.DEFAULT_TASTE_PROFILE


@signal_bp.route("/taste-profile", methods=["GET"])
@require_auth
def get_taste_profile():
    from config import Config
    conn = get_db()
    row = conn.execute(
        "SELECT taste_profile, signal_candidate_limit, signal_synthesis_limit, signal_filter_prompt, signal_planning_prompt, signal_synthesis_prompt, signal_web_search_enabled "
        "FROM users WHERE id = ?",
        (g.user.id,)
    ).fetchone()

    return jsonify({
        "taste_profile": _resolve_taste_profile(row),
        "signal_candidate_limit": row["signal_candidate_limit"] if row else None,
        "signal_synthesis_limit": row["signal_synthesis_limit"] if row else None,
        "signal_filter_prompt": row["signal_filter_prompt"] if row else None,
        "signal_planning_prompt": row["signal_planning_prompt"] if row else None,
        "signal_synthesis_prompt": row["signal_synthesis_prompt"] if row else None,
        "signal_planning_enabled": Config.SIGNAL_BRIEF_PLANNING_ENABLED,
        "signal_humanizer_enabled": Config.SIGNAL_HUMANIZER_ENABLED,
        "signal_web_search_enabled": bool(row["signal_web_search_enabled"]) if row and row["signal_web_search_enabled"] is not None else True,
        "default_filter_prompt": FILTER_PROMPT_TEMPLATE,
        "default_planning_prompt": PLANNING_PROMPT_TEMPLATE,
        "default_synthesis_prompt": SYNTHESIS_PROMPT_TEMPLATE,
        "default_synthesis_limit": Config.SIGNAL_MAX_SYNTHESIS_ARTICLES,
    })


@signal_bp.route("/taste-profile", methods=["PUT"])
@require_auth
def update_taste_profile():
    data = request.get_json() or {}
    profile = str(data.get("taste_profile") or "").strip()

    limit = data.get("signal_candidate_limit")
    if limit is not None:
        try:
            limit = int(limit)
            if limit <= 0:
                limit = None
        except (ValueError, TypeError):
            limit = None

    synthesis_limit = data.get("signal_synthesis_limit")
    if synthesis_limit is not None:
        try:
            synthesis_limit = int(synthesis_limit)
            if synthesis_limit <= 0:
                synthesis_limit = None
        except (ValueError, TypeError):
            synthesis_limit = None

    def _optional_prompt(name: str) -> str | None:
        value = data.get(name)
        if value is None:
            return None
        return str(value).strip() or None

    filter_prompt = _optional_prompt("signal_filter_prompt")
    planning_prompt = _optional_prompt("signal_planning_prompt")
    synthesis_prompt = _optional_prompt("signal_synthesis_prompt")
    web_search_enabled = data.get("signal_web_search_enabled")
    if web_search_enabled is None:
        web_search_enabled = True
    else:
        web_search_enabled = bool(web_search_enabled)

    # Save as NULL if they match default templates exactly or are empty
    if filter_prompt and filter_prompt.strip() == FILTER_PROMPT_TEMPLATE.strip():
        filter_prompt = None
    if planning_prompt and planning_prompt.strip() == PLANNING_PROMPT_TEMPLATE.strip():
        planning_prompt = None
    if synthesis_prompt and synthesis_prompt.strip() == SYNTHESIS_PROMPT_TEMPLATE.strip():
        synthesis_prompt = None

    conn = get_db()
    conn.execute(
        "UPDATE users SET taste_profile = ?, signal_candidate_limit = ?, signal_synthesis_limit = ?, "
        "signal_filter_prompt = ?, signal_planning_prompt = ?, signal_synthesis_prompt = ?, signal_web_search_enabled = ?, updated_at = ? WHERE id = ?",
        (profile, limit, synthesis_limit, filter_prompt, planning_prompt, synthesis_prompt, 1 if web_search_enabled else 0, utc_now(), g.user.id)
    )
    conn.commit()

    return jsonify({
        "success": True,
        "taste_profile": profile or DEFAULT_TASTE_PROFILE,
        "signal_candidate_limit": limit,
        "signal_synthesis_limit": synthesis_limit,
        "signal_filter_prompt": filter_prompt,
        "signal_planning_prompt": planning_prompt,
        "signal_synthesis_prompt": synthesis_prompt,
        "signal_web_search_enabled": web_search_enabled,
    })


@signal_bp.route("/briefs", methods=["GET"])
@require_auth
def list_briefs():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM signal_briefs WHERE user_id = ? ORDER BY created_at DESC",
        (g.user.id,)
    ).fetchall()
    return jsonify({"briefs": rows_to_dicts(rows)})


@signal_bp.route("/briefs", methods=["POST"])
@require_auth
def generate_brief():
    conn = get_db()
    preview = False
    from middleware.auth import _dev_bypass_auth_enabled
    if g.user.email.lower() == "sarathavasarala@gmail.com" or _dev_bypass_auth_enabled():
        preview = request.args.get("preview", "false").lower() == "true"
        if not preview and request.is_json:
            try:
                preview = bool(request.get_json().get("preview", False))
            except Exception:
                pass

    trace = brief_tracing.start_daily_brief_trace(user_id=g.user.id, mode="blocking")
    try:
        with trace.span("load_settings") as span:
            settings = signal_pipeline.load_user_settings(
                conn,
                g.user.id,
                default_filter_template=FILTER_PROMPT_TEMPLATE,
                default_planning_template=PLANNING_PROMPT_TEMPLATE,
                default_synthesis_template=SYNTHESIS_PROMPT_TEMPLATE,
            )
            span.update(output=brief_tracing.summarize_settings(settings))
        taste_profile = settings["taste_profile"]

        with trace.span("candidate_selection", input={"candidate_limit": settings["candidate_limit"]}) as span:
            items = signal_pipeline.select_candidates(
                conn, g.user.id, settings["candidate_limit"], taste_profile=taste_profile
            )
            span.update(output={
                "candidate_count": len(items),
                "candidates": brief_tracing.summarize_candidates(items),
            })
        if not items:
            trace.finish(output={"success": False, "reason": "no_content"})
            return jsonify({
                "success": False,
                "reason": "no_content",
                "message": "No recent RSS feed content found to analyze. Try adding some sources first."
            }), 200

        with trace.generation(
            "llm_filter",
            model=brief_tracing.runtime_config()["signal_model"],
            input={
                "candidate_count": len(items),
                "synthesis_limit": settings.get("synthesis_limit"),
                "candidates": brief_tracing.summarize_candidates(items),
            },
        ) as generation:
            selected_items = signal_pipeline.llm_filter(
                items, taste_profile, settings["filter_template"], synthesis_limit=settings.get("synthesis_limit")
            )
            generation.update(output={
                "selected_ids": [item["id"] for item in selected_items],
                "selected_items": brief_tracing.summarize_selected_items(selected_items),
            })
        if not selected_items:
            trace.finish(output={"success": False, "reason": "no_high_signal_content"})
            return jsonify({
                "success": False,
                "reason": "no_high_signal_content",
                "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"
            }), 200

        with trace.span("content_extraction", input={"selected_ids": [item["id"] for item in selected_items]}) as span:
            updates = signal_pipeline.run_extract_contents(selected_items)
            signal_pipeline.persist_content_updates(conn, updates)
            span.update(output={
                **brief_tracing.summarize_content_updates(updates),
                "selected_items": brief_tracing.summarize_selected_items(selected_items, include_content=True),
            })

        brief_plan = ""
        if settings.get("planning_enabled", True):
            with trace.generation(
                "brief_planning",
                model=brief_tracing.runtime_config()["signal_model"],
                input={"selected_items": brief_tracing.summarize_selected_item_refs(selected_items)},
            ) as generation:
                brief_plan = signal_pipeline.plan_brief(
                    selected_items,
                    taste_profile,
                    settings["planning_template"],
                    recent_briefs=settings.get("recent_briefs", ""),
                )
                generation.update(output={"brief_plan": brief_plan})

        with trace.generation(
            "background_research",
            model=brief_tracing.runtime_config()["signal_model"],
            input={"web_search_enabled": settings["web_search_enabled"], "brief_plan": brief_plan},
        ) as generation:
            research_brief, queries = signal_pipeline.research(
                selected_items,
                web_search_enabled=settings["web_search_enabled"],
                brief_plan=brief_plan,
                taste_profile=taste_profile,
            )
            generation.update(output={"research_brief": research_brief, "queries": queries})

        with trace.generation(
            "brief_synthesis",
            model=brief_tracing.runtime_config()["signal_model"],
            input={
                "selected_items": brief_tracing.summarize_selected_item_refs(selected_items),
                "research_brief": research_brief,
                "brief_plan": brief_plan,
                "recent_briefs": settings.get("recent_briefs", ""),
            },
        ) as generation:
            content = signal_pipeline.synthesize(
                selected_items,
                taste_profile,
                settings["synthesis_template"],
                research_brief=research_brief,
                recent_briefs=settings.get("recent_briefs", ""),
                brief_plan=brief_plan,
            )
            generation.update(output={"content": content})

        from config import Config
        if Config.SIGNAL_HUMANIZER_ENABLED:
            with trace.generation(
                "style_edit",
                model=brief_tracing.runtime_config()["signal_model"],
                input={"draft_content": brief_tracing.summarize_text(content)},
            ) as generation:
                content = signal_pipeline.style_edit_brief(content, HUMANIZER_PROMPT_TEMPLATE)
                generation.update(output={"content": brief_tracing.summarize_text(content)})

        brief = signal_pipeline.save_brief(conn, g.user.id, content, selected_items, skip_last_briefed_update=preview)
        trace.finish(brief=brief, output={"brief": brief, "selected_ids": [item["id"] for item in selected_items]})
        return jsonify(brief), 201
    except Exception as exc:
        trace.fail(stage="non-streaming-generation", exc=exc)
        logger.exception("Error in non-streaming signal brief generation")
        log_telemetry_error(g.user.id, "non-streaming-generation", exc)
        return jsonify({"error": f"Failed to generate brief: {str(exc)}"}), 500
    finally:
        trace.flush()


@signal_bp.route("/briefs/<brief_id>", methods=["DELETE"])
@require_auth
def delete_brief(brief_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM signal_briefs WHERE id = ? AND user_id = ?",
        (brief_id, g.user.id)
    ).fetchone()
    if not row:
        return jsonify({"error": "Brief not found"}), 404
    conn.execute("DELETE FROM signal_briefs WHERE id = ?", (brief_id,))
    conn.commit()
    return jsonify({"success": True}), 200


@signal_bp.route("/telemetry", methods=["GET"])
@require_auth
def get_telemetry():
    """Retrieve the recent telemetry error logs for debugging."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, stage, error_message, traceback, created_at FROM telemetry_logs "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (g.user.id,)
    ).fetchall()
    return jsonify({"telemetry": rows_to_dicts(rows)})


# ---------------------------------------------------------------------------
# SSE Streaming Endpoint
# ---------------------------------------------------------------------------

def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _generate_brief_stream_impl(user_id: str, trace: brief_tracing.BriefTrace, skip_last_briefed_update=False):
    """Generator that yields SSE events as the shared pipeline runs."""
    try:
        with db_session() as conn:
            with trace.span("load_settings") as span:
                settings = signal_pipeline.load_user_settings(
                    conn,
                    user_id,
                    default_filter_template=FILTER_PROMPT_TEMPLATE,
                    default_planning_template=PLANNING_PROMPT_TEMPLATE,
                    default_synthesis_template=SYNTHESIS_PROMPT_TEMPLATE,
                )
                span.update(output=brief_tracing.summarize_settings(settings))
            taste_profile = settings["taste_profile"]

            with trace.span("candidate_selection", input={"candidate_limit": settings["candidate_limit"]}) as span:
                items = signal_pipeline.select_candidates(
                    conn, user_id, settings["candidate_limit"], taste_profile=taste_profile
                )
                span.update(output={
                    "candidate_count": len(items),
                    "candidates": brief_tracing.summarize_candidates(items),
                })
            if not items:
                trace.finish(output={"success": False, "reason": "no_content"})
                yield _sse_event({"stage": "error", "message": "No recent RSS feed content found to analyze. Try adding some sources first."})
                return

            source_names = list({item["feed_title"] or "Unknown" for item in items})
            candidate_words = sum(len((item.get("title") or "").split()) + len((item.get("summary") or "").split()) for item in items)
            yield _sse_event({
                "stage": "scanning",
                "message": f"Scanning {len(items)} articles across {len(source_names)} sources",
                "article_count": len(items),
                "source_count": len(source_names),
                "candidate_word_count": candidate_words,
            })
    except Exception as exc:
        trace.fail(stage="scanning", exc=exc)
        logger.exception("Error during scanning/setting loading")
        log_telemetry_error(user_id, "scanning", exc)
        yield _sse_event({"stage": "error", "message": f"Failed during initial scan: {str(exc)}"})
        return

    yield _sse_event({"stage": "filtering", "message": "Applying briefing preferences..."})

    try:
        with trace.generation(
            "llm_filter",
            model=brief_tracing.runtime_config()["signal_model"],
            input={
                "candidate_count": len(items),
                "synthesis_limit": settings.get("synthesis_limit"),
                "candidates": brief_tracing.summarize_candidates(items),
            },
        ) as generation:
            selected_items = signal_pipeline.llm_filter(
                items, taste_profile, settings["filter_template"], synthesis_limit=settings.get("synthesis_limit")
            )
            generation.update(output={
                "selected_ids": [item["id"] for item in selected_items],
                "selected_items": brief_tracing.summarize_selected_items(selected_items),
            })
    except Exception as exc:
        trace.fail(stage="filtering", exc=exc)
        logger.exception("Error in signal filtering LLM call")
        log_telemetry_error(user_id, "filtering", exc)
        yield _sse_event({"stage": "error", "message": f"Failed during filtering: {str(exc)}"})
        return

    if not selected_items:
        trace.finish(output={"success": False, "reason": "no_high_signal_content"})
        yield _sse_event({"stage": "error", "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"})
        return

    yield _sse_event({
        "stage": "filtered",
        "message": f"Selected {len(selected_items)} high-signal articles",
        "count": len(selected_items),
        "titles": [item["title"] for item in selected_items],
        "candidate_word_count": candidate_words,
    })

    extract_total = len(selected_items)
    yield _sse_event({"stage": "extracting", "message": "Extracting full text...", "current": 0, "total": extract_total})

    try:
        with trace.span("content_extraction", input={"selected_ids": [item["id"] for item in selected_items]}) as span:
            gen = signal_pipeline.extract_contents(selected_items)
            updates = []
            try:
                while True:
                    done, total = next(gen)
                    yield _sse_event({"stage": "extracting", "message": f"Extracting full text... {done} of {total}", "current": done, "total": total})
            except StopIteration as stop:
                updates = stop.value or []
            span.update(output={
                **brief_tracing.summarize_content_updates(updates),
                "selected_items": brief_tracing.summarize_selected_items(selected_items, include_content=True),
            })
    except Exception as exc:
        trace.fail(stage="extracting", exc=exc)
        logger.exception("Error during content extraction")
        log_telemetry_error(user_id, "extracting", exc)
        yield _sse_event({"stage": "error", "message": f"Failed during content extraction: {str(exc)}"})
        return

    try:
        with db_session() as conn:
            signal_pipeline.persist_content_updates(conn, updates)
    except Exception as exc:
        trace.fail(stage="extracting_persist", exc=exc)
        logger.exception("Error persisting content updates")
        log_telemetry_error(user_id, "extracting_persist", exc)
        yield _sse_event({"stage": "error", "message": f"Failed to save extracted content: {str(exc)}"})
        return

    extracted_words = sum(len((item.get("content") or "").split()) for item in selected_items)

    brief_plan = ""
    plan_words = 0
    if settings.get("planning_enabled", True):
        yield _sse_event({
            "stage": "planning",
            "message": "Planning themes and source tensions...",
            "extracted_word_count": extracted_words,
        })

        try:
            with trace.generation(
                "brief_planning",
                model=brief_tracing.runtime_config()["signal_model"],
                input={"selected_items": brief_tracing.summarize_selected_item_refs(selected_items)},
            ) as generation:
                brief_plan = signal_pipeline.plan_brief(
                    selected_items,
                    taste_profile,
                    settings["planning_template"],
                    recent_briefs=settings.get("recent_briefs", ""),
                )
                generation.update(output={"brief_plan": brief_plan})
            plan_words = len((brief_plan or "").split())
            yield _sse_event({
                "stage": "planned",
                "message": "Theme planning complete",
                "plan_word_count": plan_words,
                "extracted_word_count": extracted_words,
            })
        except Exception as exc:
            trace.fail(stage="planning", exc=exc)
            logger.exception("Error during brief planning")
            log_telemetry_error(user_id, "planning", exc)
            yield _sse_event({"stage": "error", "message": f"Failed during theme planning: {str(exc)}"})
            return

    research_brief = ""
    research_words = 0
    if settings.get("web_search_enabled", True):
        yield _sse_event({
            "stage": "researching",
            "message": "Researching background context...",
            "extracted_word_count": extracted_words,
        })
        try:
            with trace.generation(
                "background_research",
                model=brief_tracing.runtime_config()["signal_model"],
                input={"web_search_enabled": True, "brief_plan": brief_plan},
            ) as generation:
                research_brief, queries = signal_pipeline.research(selected_items, web_search_enabled=True, brief_plan=brief_plan, taste_profile=taste_profile)
                generation.update(output={"research_brief": research_brief, "queries": queries})
            research_words = len((research_brief or "").split())
            yield _sse_event({
                "stage": "researched",
                "message": f"Background research complete ({len(queries)} queries run)" if queries else "Background research complete",
                "titles": queries,
                "research_word_count": research_words,
                "extracted_word_count": extracted_words,
            })
        except Exception as exc:
            trace.fail(stage="researching", exc=exc)
            logger.exception("Error during background research")
            log_telemetry_error(user_id, "researching", exc)
            yield _sse_event({"stage": "error", "message": f"Failed during background research: {str(exc)}"})
            return

    articles_contents_str = signal_pipeline._build_articles_contents_str(selected_items)
    synthesis_words = len((articles_contents_str or "").split()) + research_words + plan_words

    yield _sse_event({
        "stage": "synthesizing",
        "message": "Writing your daily brief...",
        "extracted_word_count": extracted_words,
        "research_word_count": research_words,
        "plan_word_count": plan_words,
        "synthesis_word_count": synthesis_words,
    })

    try:
        with trace.generation(
            "brief_synthesis",
            model=brief_tracing.runtime_config()["signal_model"],
            input={
                "selected_items": brief_tracing.summarize_selected_item_refs(selected_items),
                "research_brief": research_brief,
                "brief_plan": brief_plan,
                "recent_briefs": settings.get("recent_briefs", ""),
            },
        ) as generation:
            content = signal_pipeline.synthesize(
                selected_items,
                taste_profile,
                settings["synthesis_template"],
                research_brief=research_brief,
                recent_briefs=settings.get("recent_briefs", ""),
                brief_plan=brief_plan,
            )
            generation.update(output={"content": content})
    except Exception as exc:
        trace.fail(stage="synthesizing", exc=exc)
        logger.exception("Error in signal brief synthesis LLM call")
        log_telemetry_error(user_id, "synthesizing", exc)
        yield _sse_event({"stage": "error", "message": f"Failed to generate brief content: {str(exc)}"})
        return

    from config import Config
    if Config.SIGNAL_HUMANIZER_ENABLED:
        yield _sse_event({
            "stage": "humanizing",
            "message": "Refining style and tone...",
            "extracted_word_count": extracted_words,
            "research_word_count": research_words,
            "plan_word_count": plan_words,
        })
        try:
            with trace.generation(
                "style_edit",
                model=brief_tracing.runtime_config()["signal_model"],
                input={"draft_content": brief_tracing.summarize_text(content)},
            ) as generation:
                content = signal_pipeline.style_edit_brief(content, HUMANIZER_PROMPT_TEMPLATE)
                generation.update(output={"content": brief_tracing.summarize_text(content)})
        except Exception as exc:
            logger.exception("Error in signal brief style edit agent")
            log_telemetry_error(user_id, "humanizing", exc)
            # Proceed with draft content on failure

    try:
        with db_session() as conn:
            brief = signal_pipeline.save_brief(conn, user_id, content, selected_items, skip_last_briefed_update=skip_last_briefed_update)
    except Exception as exc:
        trace.fail(stage="saving", exc=exc)
        logger.exception("Error saving brief to database")
        log_telemetry_error(user_id, "saving", exc)
        yield _sse_event({"stage": "error", "message": f"Failed to save generated brief: {str(exc)}"})
        return

    synthesis_output_words = len((content or "").split())
    trace.finish(brief=brief, output={"brief": brief, "selected_ids": [item["id"] for item in selected_items]})
    yield _sse_event({
        "stage": "complete",
        "brief": brief,
        "synthesis_output_word_count": synthesis_output_words
    })


def _generate_brief_stream(user_id: str, skip_last_briefed_update=False):
    trace = brief_tracing.start_daily_brief_trace(user_id=user_id, mode="streaming")
    try:
        yield from _generate_brief_stream_impl(user_id, trace, skip_last_briefed_update=skip_last_briefed_update)
    finally:
        trace.flush()


@signal_bp.route("/briefs/generate", methods=["POST"])
@require_auth
def generate_brief_stream():
    user_id = g.user.id
    preview = False
    from middleware.auth import _dev_bypass_auth_enabled
    if g.user.email.lower() == "sarathavasarala@gmail.com" or _dev_bypass_auth_enabled():
        preview = request.args.get("preview", "false").lower() == "true"

    return Response(
        stream_with_context(_generate_brief_stream(user_id, skip_last_briefed_update=preview)),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
