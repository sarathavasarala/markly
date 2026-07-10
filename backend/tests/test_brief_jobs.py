from database import db_session, upsert_user
from services import brief_jobs


def test_enqueue_daily_brief_jobs_is_idempotent(app):
    user = upsert_user("brief-job@example.com", full_name="Brief Job")

    first = brief_jobs.enqueue_daily_brief_jobs()
    second = brief_jobs.enqueue_daily_brief_jobs()

    assert first == {"queued": 1, "existing": 0}
    assert second == {"queued": 0, "existing": 1}

    with db_session() as conn:
        job = conn.execute(
            "SELECT user_id, status, attempts FROM brief_jobs WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
    assert dict(job) == {"user_id": user["id"], "status": "queued", "attempts": 0}


def test_run_job_records_success(app, mocker):
    user = upsert_user("brief-success@example.com", full_name="Brief Success")
    brief_jobs.enqueue_daily_brief_jobs()
    job = brief_jobs._claim_next_job()
    assert job is not None
    mocker.patch(
        "services.brief_jobs._generate_brief",
        return_value={"status": "succeeded"},
    )

    brief_jobs._run_job(job)

    with db_session() as conn:
        saved_job = conn.execute(
            "SELECT status, attempts, brief_id, completed_at FROM brief_jobs WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
    assert saved_job["status"] == "succeeded"
    assert saved_job["attempts"] == 1
    assert saved_job["brief_id"] is None
    assert saved_job["completed_at"] is not None


def test_run_job_retries_after_failure(app, mocker):
    user = upsert_user("brief-retry@example.com", full_name="Brief Retry")
    brief_jobs.enqueue_daily_brief_jobs()
    job = brief_jobs._claim_next_job()
    assert job is not None
    mocker.patch("services.brief_jobs._generate_brief", side_effect=RuntimeError("Azure OpenAI unavailable"))

    brief_jobs._run_job(job)

    with db_session() as conn:
        saved_job = conn.execute(
            "SELECT status, attempts, available_at, created_at, error_message FROM brief_jobs WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        telemetry = conn.execute(
            "SELECT stage, error_message FROM telemetry_logs WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
    assert saved_job["status"] == "queued"
    assert saved_job["attempts"] == 1
    assert saved_job["available_at"] > saved_job["created_at"]
    assert saved_job["error_message"] == "Azure OpenAI unavailable"
    assert dict(telemetry) == {
        "stage": "scheduled-brief-generation",
        "error_message": "Azure OpenAI unavailable",
    }


def test_generate_brief_runs_the_existing_pipeline(app, mocker):
    user = upsert_user("brief-pipeline@example.com", full_name="Brief Pipeline")
    item = {"id": "item-1", "title": "A useful article"}
    settings = {
        "taste_profile": "product writing",
        "candidate_limit": 10,
        "filter_template": "filter",
        "planning_enabled": False,
        "planning_template": "plan",
        "web_search_enabled": False,
        "synthesis_template": "synthesize",
        "synthesis_limit": 5,
        "recent_briefs": "",
    }
    mocker.patch("services.brief_jobs.signal_pipeline.load_user_settings", return_value=settings)
    mocker.patch("services.brief_jobs.signal_pipeline.select_candidates", return_value=[item])
    mocker.patch("services.brief_jobs.signal_pipeline.llm_filter", return_value=[item])
    mocker.patch("services.brief_jobs.signal_pipeline.run_extract_contents", return_value=[])
    mocker.patch("services.brief_jobs.signal_pipeline.persist_content_updates")
    mocker.patch("services.brief_jobs.signal_pipeline.research", return_value=("", []))
    mocker.patch("services.brief_jobs.signal_pipeline.synthesize", return_value="Brief content")
    mocker.patch(
        "services.brief_jobs.signal_pipeline.save_brief",
        return_value={"id": "saved-brief"},
    )
    mocker.patch("services.brief_jobs.Config.SIGNAL_HUMANIZER_ENABLED", False)

    result = brief_jobs._generate_brief(user["id"])

    assert result == {"status": "succeeded", "brief_id": "saved-brief"}
