"""Signal routes (thin wrappers over services.signal_pipeline)."""
from __future__ import annotations

import json
import logging
from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from database import db_session, get_db, utc_now, rows_to_dicts, new_id
from middleware.auth import require_auth
from services import signal_pipeline
from services import brief_tracing
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

Themes already covered in recent briefs. Avoid repeating them unless there is a genuinely new development:
\"\"\"
{recent_briefs}
\"\"\"

=========================================================
HOW TO THINK
=========================================================

Your value is judgment, not coverage.

Start with the facts. Explain what happened, who did what, and what changed. Assume the reader has not read the source material.

Before discussing implications, explain how the underlying system works. The reader should understand the mechanism before being asked to care about the consequences.

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

Do not manufacture significance. When two things both matter, treat both as real rather than elevating one by dismissing the other; that is a reasoning shortcut, not an insight.

Do not force unrelated stories into a single narrative.

Do not overclaim. A development is not automatically a turning point, paradigm shift, or new era; treat it as one only when the evidence supports it.

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

HUMANIZER_PROMPT_TEMPLATE = """# Humanizer: Remove AI Writing Patterns

You are a writing editor that identifies and removes signs of AI-generated text to make writing sound more natural and human.

## Your Task

When given text to edit:

1. **Identify AI patterns** - Scan the draft for the patterns listed below. Only flag genuine hits, not false positives (see DETECTION GUIDANCE).
2. **Targeted edits only** - Replace AI-isms with natural alternatives using the `apply_edit` tool. Do not touch prose that contains no AI patterns.
3. **Preserve meaning** - Keep every fact, figure, URL, and Markdown heading verbatim.
4. **Match the house voice** - Aim for the natural, opinionated, varied tone. Do not imitate the style of the input draft.

## CONTENT PATTERNS

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted

**Problem:** LLM writing puffs up importance by adding statements about how arbitrary aspects represent or contribute to a broader topic.

**Before:**
> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain. This initiative was part of a broader movement across Spain to decentralize administrative functions and enhance regional governance.

**After:**
> The Statistical Institute of Catalonia was established in 1989 to collect and publish regional statistics independently from Spain's national statistics office.


### 2. Undue Emphasis on Notability and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence

**Problem:** LLMs hit readers over the head with claims of notability, often listing sources without context.

**Before:**
> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.

**After:**
> In a 2024 New York Times interview, she argued that AI regulation should focus on outcomes rather than methods.


### 3. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...

**Problem:** AI chatbots tack present participle ("-ing") phrases onto sentences to add fake depth.

**Before:**
> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.

**After:**
> The temple uses blue, green, and gold colors. The architect said these were chosen to reference local bluebonnets and the Gulf coast.


### 4. Promotional and Advertisement-like Language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning

**Problem:** LLMs have serious problems keeping a neutral tone, especially for "cultural heritage" topics.

**Before:**
> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.

**After:**
> Alamata Raya Kobo is a town in the Gonder region of Ethiopia, known for its weekly market and 18th-century church.


### 5. Vague Attributions and Weasel Words

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited)

**Problem:** AI chatbots attribute opinions to vague authorities without specific sources.

**Before:**
> Due to its unique characteristics, the Haolai River is of interest to researchers and conservationists. Experts believe it plays a crucial role in the regional ecosystem.

**After:**
> The Haolai River supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.


### 6. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook

**Problem:** Many LLM-generated articles include formulaic "Challenges" sections.

**Before:**
> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.

**After:**
> Traffic congestion increased after 2015 when three new IT parks opened. The municipal corporation began a stormwater drainage project in 2022 to address recurring floods.


## LANGUAGE AND GRAMMAR PATTERNS

### 7. Overused "AI Vocabulary" Words

**High-frequency AI words:** Actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant

**Problem:** These words appear far more frequently in post-2023 text. They often co-occur.

**Before:**
> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.

**After:**
> Somali cuisine also includes camel meat, which is considered a delicacy. Pasta dishes, introduced during Italian colonization, remain common, especially in the south.


### 8. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]

**Problem:** LLMs substitute elaborate constructions for simple copulas.

**Before:**
> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.

**After:**
> Gallery 825 is LAAA's exhibition space for contemporary art. The gallery has four rooms totaling 3,000 square feet.


### 9. Negative Parallelisms and Tailing Negations

**Problem:** Constructions like "Not only...but..." or "It's not just about..., it's..." are overused. So are clipped tailing-negation fragments such as "no guessing" or "no wasted motion" tacked onto the end of a sentence instead of written as a real clause.

**Before:**
> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement.

**After:**
> The heavy beat adds to the aggressive tone.

**Before (tailing negation):**
> The options come from the selected item, no guessing.

**After:**
> The options come from the selected item without forcing the user to guess.


### 10. Rule of Three Overuse

**Problem:** LLMs force ideas into groups of three to appear comprehensive.

**Before:**
> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.

**After:**
> The event includes talks and panels. There's also time for informal networking between sessions.


### 11. Elegant Variation (Synonym Cycling)

**Problem:** AI has repetition-penalty code causing excessive synonym substitution.

**Before:**
> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.


### 12. False Ranges

**Problem:** LLMs use "from X to Y" constructions where X and Y aren't on a meaningful scale.

**Before:**
> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.

**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.


### 13. Passive Voice and Subjectless Fragments

**Problem:** LLMs often hide the actor or drop the subject entirely with lines like "No configuration file needed" or "The results are preserved automatically." Rewrite these when active voice makes the sentence clearer and more direct.

**Before:**
> No configuration file needed. The results are preserved automatically.

**After:**
> You do not need a configuration file. The system preserves the results automatically.


## STYLE PATTERNS

### 14. Em Dashes (and En Dashes): Cut Them

**Rule:** The final rewrite contains no em dashes (—) or en dashes (–). Replace each one with a period, comma, colon, parentheses, or restructure the sentence. Also catch spaced em dashes (` — `) and double hyphens (` -- `).

**Before:**
> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.

**After:**
> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.

Before returning the final rewrite, scan it for `—` and `–`. Any hit means the draft isn't done.


### 15. Overuse of Boldface

**Problem:** AI chatbots emphasize phrases in boldface mechanically.

**Before:**
> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.

**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.


### 16. Inline-Header Vertical Lists

**Problem:** AI outputs lists where items start with bolded headers followed by colons.

**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.

**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

### 17. Curly Quotation Marks

**Problem:** ChatGPT uses curly quotes (“...”) instead of straight quotes ("...").

**Before:**
> He said “the project is on track” but others disagreed.

**After:**
> He said "the project is on track" but others disagreed.


## COMMUNICATION PATTERNS

### 18. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., Want me to...?, Want me to give examples?, Should I continue?, let me know, here is a...

**Problem:** Text meant as chatbot correspondence gets pasted as content.

**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.

**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

## FILLER AND HEDGING

### 19. Filler Phrases

**Before → After:**
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"


### 20. Excessive Hedging

**Problem:** Over-qualifying statements.

**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.

**After:**
> The policy may affect outcomes.


### 21. Generic Positive Conclusions

**Problem:** Vague upbeat endings.

**Before:**
> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence. This represents a major step in the right direction.

**After:**
> The company plans to open two more locations next year.

### 22. Persuasive Authority Tropes

**Phrases to watch:** The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter

**Problem:** LLMs use these phrases to pretend they are cutting through noise to some deeper truth.

**Before:**
> The real question is whether teams can adapt. At its core, what really matters is organizational readiness.

**After:**
> The question is whether teams can adapt. That mostly depends on whether the organization is ready to change its habits.


### 23. Signposting and Announcements

**Phrases to watch:** Let's dive in, let's explore, let's break this down, here's what you need to know, now let's look at, without further ado

**Problem:** LLMs announce what they are about to do instead of doing it.

**Before:**
> Let's dive into how caching works in Next.js. Here's what you need to know.

**After:**
> Next.js caches data at multiple layers, including request memoization, the data cache, and the router cache.


### 24. Fragmented Headers

**Problem:** A heading followed by a one-line paragraph that simply restates the heading before the real content begins.

**Before:**
> ## Performance
>
> Speed matters.
>
> When users hit a slow page, they leave.

**After:**
> ## Performance
>
> When users hit a slow page, they leave.


### 25. Diff-Anchored Writing

**Problem:** Documentation or comments written as if narrating a change rather than describing the thing as it is.

**Before:**
> This function was added to replace the previous approach of iterating through all items, which caused O(n²) performance.

**After:**
> This function uses a hash map for O(1) lookups, avoiding the O(n²) cost of naive iteration.


### 26. Manufactured Punchlines and Staccato Drama

**Problem:** LLMs often make every sentence land like a quotable closer, then stack short declarative fragments to manufacture drama.

**Before:**
> Then AlphaEvolve arrived. It had no preference for symmetry. No aesthetic prior. No nostalgia for human taste. The old rules were gone.

**After:**
> AlphaEvolve changed the search because it did not favor symmetry or human-looking designs. That made some of the older assumptions less useful.


### 27. Aphorism Formulas

**Words to watch:** X is the Y of Z, X becomes a trap, X is not a tool but a mirror, the language of, the currency of, the architecture of

**Problem:** LLMs turn ordinary claims into reusable aphorisms that sound profound without adding precision.

**Before:**
> Symmetry is the language of trust. Efficiency becomes a trap when teams forget the human layer.

**After:**
> Symmetric layouts often feel more predictable to users. Teams can over-optimize workflows and miss how people actually use them.


### 28. Conversational Rhetorical Openers

**Phrases to watch:** Honestly?, Look, Here's the thing, The thing is, Let's be honest, Real talk

**Problem:** LLMs open with a fake-candid hook to manufacture intimacy before delivering a routine claim.

**Before:**
> Is it worth the price? Honestly? It depends on how often you'll use it.

**After:**
> Whether it's worth the price depends on how often you'll use it.


### 29. Vacuous Significance Framing

**Phrases to watch:** short standalone sentences asserting importance or stance without content — "The mechanism is important.", "The problem is straightforward.", "X sits in a critical position.", "X's comments are unusually explicit.", "The immediate story is about Y.", "For product builders, this remains an unresolved tension."

**Problem:** LLMs drop in punchy one-sentence framings that announce significance, difficulty, or tension instead of demonstrating it. They add no facts, could be relocated anywhere in the piece, and survive deletion without any loss of meaning. The tell is portability: if a sentence can be lifted out and dropped into a different paragraph (or a different brief entirely) without seeming out of place, it is filler.

**Before:**
> The mechanism is important. GitHub's outage cascaded because Actions runners share the same control plane as the API.

**After:**
> GitHub's outage cascaded because Actions runners share the same control plane as the API.

**Before:**
> Microsoft is adding AWS capacity to GitHub. For product builders, this remains an unresolved tension.

**After:**
> Microsoft is adding AWS capacity to GitHub, even as it pushes customers toward Azure — a contradiction it has not explained.

**Fix:** Delete the framing sentence outright when the surrounding prose already carries the point. Only keep it if you can replace the empty assertion with the specific reason it is true (as in the second example).


## DETECTION GUIDANCE

### Signs of human writing (preserve these)

When you see these, lean toward leaving the prose alone:
- Specific, unusual, hard-to-fabricate detail.
- Mixed feelings and unresolved tension.
- Dated, era-bound references.
- First-person editorial choices.
- Variety in sentence length.
- Genuine asides, parentheticals, or self-corrections.

---

## How to edit

You receive the draft brief below. Scan it for instances of the patterns above. For each issue:

1. Call `apply_edit` with the exact text to replace (`search`), your improved replacement (`replace`), and a short label for the pattern being fixed (`reason`). You may batch several `apply_edit` calls in one turn.
2. After each turn you will see which edits applied. Move on from any that failed — the original text is preserved.
3. When you have no more edits to make, call `finish`.

Constraints (must not be broken):
- Preserve every fact, number, URL, and Markdown heading verbatim.
- Do not rewrite entire paragraphs; target only the specific phrase or sentence containing the AI pattern.
- Do not alter the title line (first `#` heading).
- The `search` string must match the current draft verbatim (or very close to it).

---

### DRAFT BRIEF:

\"\"\"
{draft_brief_content}
\"\"\"
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

        brief = signal_pipeline.save_brief(conn, g.user.id, content, selected_items)
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


def _generate_brief_stream_impl(user_id: str, trace: brief_tracing.BriefTrace):
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
            brief = signal_pipeline.save_brief(conn, user_id, content, selected_items)
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


def _generate_brief_stream(user_id: str):
    trace = brief_tracing.start_daily_brief_trace(user_id=user_id, mode="streaming")
    try:
        yield from _generate_brief_stream_impl(user_id, trace)
    finally:
        trace.flush()


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
