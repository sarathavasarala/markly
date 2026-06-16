"""Signal routes (thin wrappers over services.signal_pipeline)."""
from __future__ import annotations

import json
import logging
from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from database import db_session, get_db, utc_now, rows_to_dicts, new_id
from middleware.auth import require_auth
from services import signal_pipeline
from services.signal_pipeline import DEFAULT_TASTE_PROFILE, _resolve_taste_profile

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

FILTER_PROMPT_TEMPLATE = """You are a sharp editor deciding what goes into today's intelligence brief. You are given recent articles from followed feeds. Select the ones worth a smart reader's attention, judged against their priorities.

Reader's priorities:
\"\"\"
{taste_profile}
\"\"\"

Recent articles:
\"\"\"
{articles_list_str}
\"\"\"

Selection rules:
Discard engagement bait, rumor with no substance, marketing fluff, low-information hot takes, and the tenth rewrite of a story already covered elsewhere in the list.

Keep genuinely significant developments even when they are announcements. A major product launch, a strategic move, a notable release, a financing, a policy change, or a real shift from a company that matters belongs in the brief when the implications are analyzable.

Also keep pieces with genuine insight, real strategic relevance, ecosystem shifts, product direction, business mechanics, technical constraints, market structure, incentives, or important second-order implications.

Favor articles that contain enough substance to support a real analyst read: concrete facts, numbers, process detail, disagreement between sources, customer behavior, financing terms, operational constraints, or a mechanism worth unpacking.

It is fine to select few. A short list of strong items beats a padded one. If little qualifies today, return a short list.

Order the selected IDs from most to least important, since only the strongest will be fully processed.

Return a JSON object containing a single key "selected_ids" mapping to an array of string IDs of the chosen articles, ordered best first.
Return ONLY valid JSON.
"""

PLANNING_PROMPT_TEMPLATE = """You are an editorial planning assistant for a daily intelligence briefing. Your job is to create a private scratchpad for the final writer, not to draft the brief.

The user's Taste Profile is:
\"\"\"
{taste_profile}
\"\"\"

Here are the selected high-signal articles with full extracted text:
\"\"\"
{articles_contents_str}
\"\"\"

Themes Already Covered In Recent Briefs:
\"\"\"
{recent_briefs}
\"\"\"

Task:
Create a concise editorial plan that helps the final brief have more depth and less forced grouping.

Instructions:
1. Identify only the themes where the relationship between articles is real and analytically useful. Do not group articles just because they share broad words like AI, cloud, chips, startups, or regulation.
2. Preserve strong standalone stories when they deserve their own treatment.
3. Point out near-duplicate coverage that should be collapsed.
4. Surface source tensions: where authors disagree, emphasize different mechanisms, or notice different parts of the same development.
5. Note what is genuinely new versus the recent brief titles, and what should not be re-explained.
6. For each planned theme or standalone item, explain the mechanism the final writer should investigate: incentives, constraints, technical tradeoffs, business mechanics, ecosystem shifts, or second-order effects.
7. For each planned theme or standalone item, give the final writer a concrete angle in this shape: what happened, why it matters, evidence strength, what to watch next, and what would weaken the read. Keep each part brief.
8. Flag a contrast only where the source material genuinely supports one. Leave framing and phrasing choices to the final writer.
9. Keep it concise. This is a planning memo, not the final brief.

Output format:
- Plain Markdown.
- Use short headings.
- Include sections named "Real themes", "Standalone stories", "Duplicate coverage", "Source tensions", "Novelty notes", and "Watch points".
- Mention article IDs when useful.
"""

SYNTHESIS_PROMPT_TEMPLATE = """You are writing a daily intelligence brief for a sharp, busy reader. They have already chosen the feeds. Your job is to explain what actually mattered today and why.

Reader's priorities:
\"\"\"
{taste_profile}
\"\"\"

Selected articles:
\"\"\"
{articles_contents_str}
\"\"\"

Background research, factual context from web search, may be empty:
\"\"\"
{research_brief}
\"\"\"

Editorial plan, private planning notes from an earlier pass, not final copy, may be empty:
\"\"\"
{brief_plan}
\"\"\"

Themes already covered in recent briefs. Avoid repeating them unless there is a genuinely new development:
\"\"\"
{recent_briefs}
\"\"\"

=========================================================
HOW TO THINK
=========================================================

Your value is judgment, not coverage.

Start with the facts. Explain what happened, who did what, and what changed. Assume the reader has not read the source material.

Before discussing implications, explain how the underlying system works. If the story involves bonds, explain why companies issue bonds and why investors buy them. If it involves AI infrastructure, explain what the infrastructure does. If it involves a developer tool, explain the workflow it changes. The reader should understand the mechanism before being asked to care about the consequences.

Move carefully from facts to interpretation. State what happened before explaining what it may mean. Make clear whether you are describing evidence, offering an interpretation, or discussing a possible future consequence.

When discussing organizations, focus on incentives and constraints. What are they optimizing for? What problem are they trying to solve? What tradeoffs are they accepting? Why might this decision be rational from their perspective?

Actively look for alternative explanations. If a smart skeptic could interpret the evidence differently, acknowledge that and explain why you prefer one interpretation over another, or why the evidence remains inconclusive.

Explain second-order effects only when you can trace a credible mechanism. Show how one thing leads to another. Do not treat speculation as foresight.

Follow the money whenever useful. Ask who pays, who benefits, who bears risk, who captures value, and what must be true economically for the strategy to work.

Treat announcements, essays, interviews, and public statements primarily as evidence of intent. Give more weight to products shipped, money spent, organizational changes, customer behavior, technical results, and observed actions.

Do not mistake a coherent narrative for a real trend. Before describing something as a major shift, consider whether the available evidence actually supports that claim.

If the day is thin, say so. Do not manufacture significance.

=========================================================
FRAMING
=========================================================

Write to explain reality, not to demonstrate insight.

Do not create insight by dismissing one fact in favor of another. This is the most important rule in this section. Never elevate one point by diminishing another. When two things both matter, state both plainly and explain how each matters; do not pit them against each other as a rhetorical move.

This bans every variant of the "not X, but Y" construction, including:

- X matters less than Y / X is less important than Y
- the real story is / the real signal is / the useful signal is / the signal is that
- the important thing is / the interesting part is / the notable fact is / the key asset is
- the specific details matter less than / the product itself is less important than
- this is not about X, it is about Y / whether X is true matters less than Y

If you are about to write a sentence whose job is to say "the important part is not A, it is B", stop. State A as a fact, state B as a fact, and explain the mechanism connecting them. State the news directly, then discuss the implications.

Before you finish, reread the draft and rewrite any sentence that contains "not ... but", "matters less than", "is less important than", "the real / useful / important / interesting X is", or any construction that makes a point by setting two facts against each other.

Do not force unrelated stories into a single narrative.

Do not make every development sound like a turning point, paradigm shift, or new era.

Curiosity is often more valuable than certainty. A useful question can be more informative than a confident conclusion.

=========================================================
GROUNDING
=========================================================

State only what the articles and research support.

If you are inferring or speculating, make that clear in the sentence.

Do not invent facts, numbers, quotes, sources, dates, or URLs.

Use numbers when they make a story more concrete.

When evidence is weak, conflicting, anecdotal, or incomplete, say so plainly.

Give more weight to observed behavior than stated intentions.

=========================================================
PLAIN LANGUAGE
=========================================================

The reader is intelligent but not a specialist in every field.

The first time you mention a product, company, model, protocol, financial instrument, or technical concept that may not be widely understood, explain in one plain sentence what it is and what it does.

Describe things directly rather than through vendor language.

Avoid abstraction as a substitute for explanation.

If a smart reader outside the field would stop and ask "what does that actually mean?", rewrite the sentence.

=========================================================
HOW TO WRITE
=========================================================

Write like a thoughtful operator explaining reality to another intelligent person.

Use clean, direct prose.

Assume the reader is arriving cold to the topic.

Build each section gradually:

1. What happened.
2. How it works.
3. Why the participants are behaving this way.
4. What may follow.

Do not jump directly from facts to conclusions.

Develop ideas in substantial paragraphs. Avoid chains of one- or two-sentence paragraphs. Most sections should read like a short essay, not a collection of observations.

Prefer explanation over interpretation when forced to choose.

Avoid analyst cliches, management cliches, startup cliches, and social-media-style declarations.

If you use terms such as moat, leverage, positioning, ecosystem, value chain, platform advantage, strategic asset, or market structure, explain concretely what they mean in that specific situation.

Do not use em dashes. Use commas, hyphens, colons, or parentheses instead.

Embed sources inline as Markdown links where they support the claim. Every thematic section should contain at least one source link, woven naturally into the prose rather than grouped at the end.

No greeting, no signature, and no closing recap.

=========================================================
OUTPUT
=========================================================

Output in Markdown.

The very first line MUST be a title summarizing the brief's focal point, formatted as a markdown H1 starting with "# Theme: " (for example, "# Theme: Apple Intelligence and Nvidia Blackwell Costs"). If the brief covers several unrelated stories, name the dominant thread or use a compact multi-theme title. Do not pretend unrelated items form one grand thesis.

Use ## headers for clusters. Start the body directly with the first cluster header.

Each section should stand on its own. A reader should be able to understand what happened, why it happened, and why it matters without opening the source article.

Aim for depth through explanation rather than density of conclusions.
"""


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
    try:
        settings = signal_pipeline.load_user_settings(
            conn,
            g.user.id,
            default_filter_template=FILTER_PROMPT_TEMPLATE,
            default_planning_template=PLANNING_PROMPT_TEMPLATE,
            default_synthesis_template=SYNTHESIS_PROMPT_TEMPLATE,
        )
        taste_profile = settings["taste_profile"]

        items = signal_pipeline.select_candidates(
            conn, g.user.id, settings["candidate_limit"], taste_profile=taste_profile
        )
        if not items:
            return jsonify({
                "success": False,
                "reason": "no_content",
                "message": "No recent RSS feed content found to analyze. Try adding some sources first."
            }), 200

        selected_items = signal_pipeline.llm_filter(
            items, taste_profile, settings["filter_template"], synthesis_limit=settings.get("synthesis_limit")
        )
        if not selected_items:
            return jsonify({
                "success": False,
                "reason": "no_high_signal_content",
                "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"
            }), 200

        updates = signal_pipeline.run_extract_contents(selected_items)
        signal_pipeline.persist_content_updates(conn, updates)

        brief_plan = ""
        if settings.get("planning_enabled", True):
            brief_plan = signal_pipeline.plan_brief(
                selected_items,
                taste_profile,
                settings["planning_template"],
                recent_briefs=settings.get("recent_briefs", ""),
            )

        research_brief, _ = signal_pipeline.research(
            selected_items,
            web_search_enabled=settings["web_search_enabled"],
            brief_plan=brief_plan,
            taste_profile=taste_profile,
        )

        content = signal_pipeline.synthesize(
            selected_items,
            taste_profile,
            settings["synthesis_template"],
            research_brief=research_brief,
            recent_briefs=settings.get("recent_briefs", ""),
            brief_plan=brief_plan,
        )
        brief = signal_pipeline.save_brief(conn, g.user.id, content, selected_items)
        return jsonify(brief), 201
    except Exception as exc:
        logger.exception("Error in non-streaming signal brief generation")
        log_telemetry_error(g.user.id, "non-streaming-generation", exc)
        return jsonify({"error": f"Failed to generate brief: {str(exc)}"}), 500


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


def _generate_brief_stream(user_id: str):
    """Generator that yields SSE events as the shared pipeline runs."""
    try:
        with db_session() as conn:
            settings = signal_pipeline.load_user_settings(
                conn,
                user_id,
                default_filter_template=FILTER_PROMPT_TEMPLATE,
                default_planning_template=PLANNING_PROMPT_TEMPLATE,
                default_synthesis_template=SYNTHESIS_PROMPT_TEMPLATE,
            )
            taste_profile = settings["taste_profile"]

            items = signal_pipeline.select_candidates(
                conn, user_id, settings["candidate_limit"], taste_profile=taste_profile
            )
            if not items:
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
        logger.exception("Error during scanning/setting loading")
        log_telemetry_error(user_id, "scanning", exc)
        yield _sse_event({"stage": "error", "message": f"Failed during initial scan: {str(exc)}"})
        return

    yield _sse_event({"stage": "filtering", "message": "Applying briefing preferences..."})

    try:
        selected_items = signal_pipeline.llm_filter(
            items, taste_profile, settings["filter_template"], synthesis_limit=settings.get("synthesis_limit")
        )
    except Exception as exc:
        logger.exception("Error in signal filtering LLM call")
        log_telemetry_error(user_id, "filtering", exc)
        yield _sse_event({"stage": "error", "message": f"Failed during filtering: {str(exc)}"})
        return

    if not selected_items:
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
        gen = signal_pipeline.extract_contents(selected_items)
        updates = []
        try:
            while True:
                done, total = next(gen)
                yield _sse_event({"stage": "extracting", "message": f"Extracting full text... {done} of {total}", "current": done, "total": total})
        except StopIteration as stop:
            updates = stop.value or []
    except Exception as exc:
        logger.exception("Error during content extraction")
        log_telemetry_error(user_id, "extracting", exc)
        yield _sse_event({"stage": "error", "message": f"Failed during content extraction: {str(exc)}"})
        return

    try:
        with db_session() as conn:
            signal_pipeline.persist_content_updates(conn, updates)
    except Exception as exc:
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
            brief_plan = signal_pipeline.plan_brief(
                selected_items,
                taste_profile,
                settings["planning_template"],
                recent_briefs=settings.get("recent_briefs", ""),
            )
            plan_words = len((brief_plan or "").split())
            yield _sse_event({
                "stage": "planned",
                "message": "Theme planning complete",
                "plan_word_count": plan_words,
                "extracted_word_count": extracted_words,
            })
        except Exception as exc:
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
            research_brief, queries = signal_pipeline.research(selected_items, web_search_enabled=True, brief_plan=brief_plan, taste_profile=taste_profile)
            research_words = len((research_brief or "").split())
            yield _sse_event({
                "stage": "researched",
                "message": f"Background research complete ({len(queries)} queries run)" if queries else "Background research complete",
                "titles": queries,
                "research_word_count": research_words,
                "extracted_word_count": extracted_words,
            })
        except Exception as exc:
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
        content = signal_pipeline.synthesize(
            selected_items,
            taste_profile,
            settings["synthesis_template"],
            research_brief=research_brief,
            recent_briefs=settings.get("recent_briefs", ""),
            brief_plan=brief_plan,
        )
    except Exception as exc:
        logger.exception("Error in signal brief synthesis LLM call")
        log_telemetry_error(user_id, "synthesizing", exc)
        yield _sse_event({"stage": "error", "message": f"Failed to generate brief content: {str(exc)}"})
        return

    try:
        with db_session() as conn:
            brief = signal_pipeline.save_brief(conn, user_id, content, selected_items)
    except Exception as exc:
        logger.exception("Error saving brief to database")
        log_telemetry_error(user_id, "saving", exc)
        yield _sse_event({"stage": "error", "message": f"Failed to save generated brief: {str(exc)}"})
        return

    synthesis_output_words = len((content or "").split())
    yield _sse_event({
        "stage": "complete",
        "brief": brief,
        "synthesis_output_word_count": synthesis_output_words
    })


@signal_bp.route("/briefs/generate", methods=["POST"])
@require_auth
def generate_brief_stream():
    user_id = g.user.id
    return Response(
        stream_with_context(_generate_brief_stream(user_id)),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
