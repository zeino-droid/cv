from engine.database import JobDatabase


def test_upsert_jobs_insert_and_update(tmp_path):
    db = JobDatabase(db_path=str(tmp_path / "jobs.db"))
    jobs = [
        {
            "id": "job-1",
            "title": "Ingénieur R&D",
            "company": "ACME",
            "location": "Paris",
            "description": "Desc",
            "url": "https://example.com",
            "fit_score": 70,
            "matched_skills": ["Python"],
            "required_skills": ["Python"],
        }
    ]
    assert db.upsert_jobs(jobs) == 1

    updated = [{**jobs[0], "fit_score": 90, "description": "", "url": ""}]
    assert db.upsert_jobs(updated) == 0
    saved = db.get_job_by_id("job-1")
    assert saved["fit_score"] == 90
    assert saved["description"] == "Desc"
    assert saved["url"] == "https://example.com"
    assert saved["matched_skills"] == ["Python"]


def test_update_status_and_invalid_status(tmp_path):
    db = JobDatabase(db_path=str(tmp_path / "jobs.db"))
    db.upsert_jobs([{"id": "job-2", "title": "Data Engineer", "company": "ACME"}])
    assert db.update_status("job-2", "selected", notes="ok") is True
    assert db.update_status("job-2", "invalid-status") is False
    job = db.get_job_by_id("job-2")
    assert job["status"] == "selected"
    assert job["notes"] == "ok"


def test_mark_as_sent_and_save_generation(tmp_path):
    db = JobDatabase(db_path=str(tmp_path / "jobs.db"))
    db.upsert_jobs([{"id": "job-3", "title": "ML Engineer", "company": "ACME"}])
    assert db.mark_as_sent("job-3", via="linkedin", edited_headline="H", edited_summary="S", vault_path="vault/x") is True
    sent = db.get_job_by_id("job-3")
    assert sent["status"] == "sent"
    assert sent["sent_via"] == "linkedin"
    assert sent["vault_path"] == "vault/x"

    db.upsert_jobs([{"id": "job-4", "title": "Thermal Engineer", "company": "ACME"}])
    db.save_generation("job-4", "vault/cv.pdf", "vault/letter.pdf")
    generated = db.get_job_by_id("job-4")
    assert generated["status"] == "generated"
    assert generated["cv_path"] == "vault/cv.pdf"


def test_get_jobs_filters_stats_top_and_locations(tmp_path):
    db = JobDatabase(db_path=str(tmp_path / "jobs.db"))
    db.upsert_jobs(
        [
            {"id": "job-a", "title": "Simulation Engineer", "company": "A", "location": "Paris", "fit_score": 85},
            {"id": "job-b", "title": "Data Engineer", "company": "B", "location": "Lyon", "fit_score": 60},
            {"id": "job-c", "title": "QA Engineer", "company": "C", "location": "Paris", "fit_score": 30},
        ]
    )
    db.update_status("job-a", "selected")
    db.update_status("job-b", "sent")

    filtered = db.get_jobs(min_score=50, status="selected")
    assert [job["id"] for job in filtered] == ["job-a"]

    searched = db.get_jobs(search="data")
    assert [job["id"] for job in searched] == ["job-b"]

    top = db.get_top_to_apply(2)
    assert [job["id"] for job in top] == ["job-a", "job-c"]

    stats = db.get_stats()
    assert stats["total"] == 3
    assert stats["sent"] == 1

    by_location = db.count_by_location()
    assert by_location[0]["location"] == "Paris"
