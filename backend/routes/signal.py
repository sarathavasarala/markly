"""Signal routes (thin wrappers over services.signal_pipeline)."""
from __future__ import annotations

import json
import logging
from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from database import db_session, get_db, utc_now, rows_to_dicts
from middleware.auth import require_auth
from services import signal_pipeline
from services.signal_pipeline import DEFAULT_TASTE_PROFILE, _resolve_taste_profile

logger = logging.getLogger(__name__)

signal_bp = Blueprint("signal", __name__)


# ---------------------------------------------------------------------------
# Prompt templates (shared by the blocking and streaming pipelines)
# ---------------------------------------------------------------------------

FILTER_PROMPT_TEMPLATE = """You are an expert analyst assistant. You are given a list of recent articles from followed RSS feeds. Your task is to filter this list aggressively to identify only the articles that align with the user's Taste Profile.

User's Taste Profile:
\"\"\"
{taste_profile}
\"\"\"

Recent RSS Articles:
\"\"\"
{articles_list_str}
\"\"\"

Task:
Select the articles that contain genuine insight, strategic relevance, ecosystem shifts, product directions, or important second-order implications. Skip incremental news, announcements, engagement bait, benchmark hype, or repetitive coverage.
Discard any articles that do not align with the priorities.
Order the selected IDs from most to least aligned with the Taste Profile, since only the strongest will be processed.

Return a JSON object containing a single key "selected_ids" mapping to an array of string IDs of the chosen articles, ordered best first.
Return ONLY valid JSON.
"""

SYNTHESIS_PROMPT_TEMPLATE = """You are a top-tier analyst and chief of staff. Your goal is to prepare a daily intelligence briefing memo for a smart founder or CEO. This memo is synthesized from followed RSS feeds.

The user's Taste Profile is:
\"\"\"
{taste_profile}
\"\"\"

Here are the selected high-signal articles:
\"\"\"
{articles_contents_str}
\"\"\"

Instructions:
1. Group articles into themes only where the connection is real. It is fine to treat a strong standalone story on its own. Prefer a few genuine clusters plus standalone items over forcing everything into one unified narrative. Do not manufacture rhymes or throughlines between unrelated pieces.
2. Explain what actually mattered, what changed underneath the surface, what smart practitioners would notice, where the important tensions or disagreements are, what second-order implications emerge, and which narratives seem overstated versus genuinely meaningful.
3. Writing Style:
   - Use clean, direct prose and simple language while carrying substantial depth.
   - Do NOT use bullet points (no asterisks or hyphens for lists; write in paragraphs).
   - Do NOT use em dashes. Use commas, hyphens, colons, or parentheses instead.
   - When you use a specialist term, product category, or acronym that a smart generalist may not know, define it in one short clause on first use, then continue with the analysis. Do not assume insider vocabulary. One sentence of grounding is context, not a summary.
   - Avoid excessive formatting, corporate jargon, motivational language, exaggerated claims, and AI-sounding phrasing.
   - Sound like a thoughtful industry insider explaining reality to another intelligent person.
   - Explain mechanisms and incentives, connect isolated events into broader patterns only when warranted, identify hidden assumptions, and discuss second-order implications.
   - Acknowledge uncertainty when evidence is weak instead of manufacturing false confidence or artificial depth.
   - Do not try to sound impressive. Prefer the plain statement over the quotable one. If a sentence reaches for an aphorism, cut it back to what it actually means. Be precise, skeptical, grounded, and useful.
   - Do not end with a recap section that restates the clusters above. Close only if you have genuinely new synthesis, a watch-list, or a specific bet, in a few sentences.
4. Source Attribution:
   - When referencing information or insights drawn from a specific article, include an inline hyperlink to the source using Markdown link syntax: [descriptive anchor text](URL).
   - Weave links naturally into the prose. For example: "As [this analysis from Stratechery](https://example.com/article) argues, the real shift is...".
   - Do not group all sources at the end. Embed them where they are most contextually relevant.
   - Every thematic section should contain at least one source link.
5. Web Search Grounding and Active Research:
   - Identify gaps in the provided RSS articles where more context is needed. This includes unexplained specialist terms, new product announcements, references to ongoing industry events, or technical claims that would benefit from latest public details or grounding.
   - Actively use the `web_search` tool to execute search queries to retrieve the latest public context, background, and updates for these points.
   - Integrate these web search findings naturally into your briefing prose to ground the analysis and explain background realities.
   - For all information or insights retrieved via web search, include inline citation hyperlinks to the source: [descriptive anchor text](URL) using the actual search result URL.
6. Output Format:
   - Provide the response in Markdown format.
   - Use simple headers (e.g. `##` for conversation clusters) to organize the memo.
   - Do not include any greeting, introduction, signature, or filler. Start directly with the first thematic header.
"""


@signal_bp.route("/taste-profile", methods=["GET"])
@require_auth
def get_taste_profile():
    conn = get_db()
    row = conn.execute(
        "SELECT taste_profile, signal_candidate_limit, signal_filter_prompt, signal_synthesis_prompt, signal_web_search_enabled "
        "FROM users WHERE id = ?",
        (g.user.id,)
    ).fetchone()
    
    return jsonify({
        "taste_profile": _resolve_taste_profile(row),
        "signal_candidate_limit": row["signal_candidate_limit"] if row else None,
        "signal_filter_prompt": row["signal_filter_prompt"] if row else None,
        "signal_synthesis_prompt": row["signal_synthesis_prompt"] if row else None,
        "signal_web_search_enabled": bool(row["signal_web_search_enabled"]) if row and row["signal_web_search_enabled"] is not None else True,
        "default_filter_prompt": FILTER_PROMPT_TEMPLATE,
        "default_synthesis_prompt": SYNTHESIS_PROMPT_TEMPLATE,
    })

@signal_bp.route("/taste-profile", methods=["PUT"])
@require_auth
def update_taste_profile():
    data = request.get_json() or {}
    profile = data.get("taste_profile", "").strip()
    
    limit = data.get("signal_candidate_limit")
    if limit is not None:
        try:
            limit = int(limit)
            if limit <= 0:
                limit = None
        except (ValueError, TypeError):
            limit = None

    filter_prompt = data.get("signal_filter_prompt", "").strip() or None
    synthesis_prompt = data.get("signal_synthesis_prompt", "").strip() or None
    web_search_enabled = data.get("signal_web_search_enabled")
    if web_search_enabled is None:
        web_search_enabled = True
    else:
        web_search_enabled = bool(web_search_enabled)

    # Save as NULL if they match default templates exactly or are empty
    if filter_prompt and filter_prompt.strip() == FILTER_PROMPT_TEMPLATE.strip():
        filter_prompt = None
    if synthesis_prompt and synthesis_prompt.strip() == SYNTHESIS_PROMPT_TEMPLATE.strip():
        synthesis_prompt = None

    conn = get_db()
    conn.execute(
        "UPDATE users SET taste_profile = ?, signal_candidate_limit = ?, "
        "signal_filter_prompt = ?, signal_synthesis_prompt = ?, signal_web_search_enabled = ?, updated_at = ? WHERE id = ?",
        (profile, limit, filter_prompt, synthesis_prompt, 1 if web_search_enabled else 0, utc_now(), g.user.id)
    )
    conn.commit()

    return jsonify({
        "success": True,
        "taste_profile": profile or DEFAULT_TASTE_PROFILE,
        "signal_candidate_limit": limit,
        "signal_filter_prompt": filter_prompt,
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

    settings = signal_pipeline.load_user_settings(
        conn,
        g.user.id,
        default_filter_template=FILTER_PROMPT_TEMPLATE,
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
            "message": "No recent RSS feed content found to analyze. Try adding some feeds first in the Radar tab!"
        }), 200

    selected_items = signal_pipeline.llm_filter(items, taste_profile, settings["filter_template"])
    if not selected_items:
        return jsonify({
            "success": False,
            "reason": "no_high_signal_content",
            "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"
        }), 200

    updates = signal_pipeline.run_extract_contents(selected_items)
    signal_pipeline.persist_content_updates(conn, updates)

    try:
        content = signal_pipeline.synthesize(
            selected_items,
            taste_profile,
            settings["synthesis_template"],
            web_search_enabled=settings["web_search_enabled"],
        )
    except Exception as exc:
        logger.error(f"Error in signal brief synthesis LLM call: {exc}")
        return jsonify({"error": f"Failed to generate brief content: {str(exc)}"}), 500

    brief = signal_pipeline.save_brief(conn, g.user.id, content, selected_items)
    return jsonify(brief), 201



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


# ---------------------------------------------------------------------------
# SSE Streaming Endpoint
# ---------------------------------------------------------------------------

def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _generate_brief_stream(user_id: str):
    """Generator that yields SSE events as the shared pipeline runs."""
    with db_session() as conn:
        settings = signal_pipeline.load_user_settings(
            conn,
            user_id,
            default_filter_template=FILTER_PROMPT_TEMPLATE,
            default_synthesis_template=SYNTHESIS_PROMPT_TEMPLATE,
        )
        taste_profile = settings["taste_profile"]

        items = signal_pipeline.select_candidates(
            conn, user_id, settings["candidate_limit"], taste_profile=taste_profile
        )
        if not items:
            yield _sse_event({"stage": "error", "message": "No recent RSS feed content found to analyze. Try adding some feeds first in the Radar tab!"})
            return

        source_names = list({item["feed_title"] or "Unknown" for item in items})
        yield _sse_event({
            "stage": "scanning",
            "message": f"Scanning {len(items)} articles across {len(source_names)} sources",
            "article_count": len(items),
            "source_count": len(source_names),
        })

        yield _sse_event({"stage": "filtering", "message": "Applying taste profile filter..."})

        selected_items = signal_pipeline.llm_filter(items, taste_profile, settings["filter_template"])
        if not selected_items:
            yield _sse_event({"stage": "error", "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"})
            return

        yield _sse_event({
            "stage": "filtered",
            "message": f"Selected {len(selected_items)} high-signal articles",
            "count": len(selected_items),
            "titles": [item["title"] for item in selected_items],
        })

        extract_total = len(selected_items)
        yield _sse_event({"stage": "extracting", "message": "Extracting full text...", "current": 0, "total": extract_total})

        gen = signal_pipeline.extract_contents(selected_items)
        updates = []
        try:
            while True:
                done, total = next(gen)
                yield _sse_event({"stage": "extracting", "message": f"Extracting full text... {done} of {total}", "current": done, "total": total})
        except StopIteration as stop:
            updates = stop.value or []

        signal_pipeline.persist_content_updates(conn, updates)

        if settings.get("web_search_enabled", True):
            yield _sse_event({"stage": "synthesizing", "message": "Researching web and writing your daily brief..."})
        else:
            yield _sse_event({"stage": "synthesizing", "message": "Writing your daily brief..."})

        try:
            content = signal_pipeline.synthesize(
                selected_items,
                taste_profile,
                settings["synthesis_template"],
                web_search_enabled=settings.get("web_search_enabled", True),
            )
        except Exception as exc:
            logger.error(f"Error in signal brief synthesis LLM call: {exc}")
            yield _sse_event({"stage": "error", "message": f"Failed to generate brief content: {str(exc)}"})
            return

        brief = signal_pipeline.save_brief(conn, user_id, content, selected_items)
        yield _sse_event({"stage": "complete", "brief": brief})


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
