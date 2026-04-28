"""Unit tests for engine.studio_service.

Tests the three service functions that contain the business logic
of the "Édition assistée" studio block.
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from engine.studio_service import (
    _init_gen_state,
    mark_application_as_sent,
    save_final_candidate_version,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job():
    return {"id": "job-1", "title": "Ingénieur", "company": "ACME"}


def _profile():
    return {"name": "Test User"}


def _make_db():
    return MagicMock()


def _make_generate_documents_fn(cv_path="/vault/cv.pdf", cv_data=None):
    cv_data = cv_data or {"headline": "Dev", "summary": "Expert"}
    return MagicMock(return_value={
        "cv_path": cv_path,
        "cv_result": {"cv_data": cv_data},
        "letter_text": "",
        "letter_path": "",
    })


def _safe_filename(value: str, max_len: int = 60) -> str:
    cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in value).strip()
    return cleaned.replace(" ", "_")[:max_len] or "file"


# ---------------------------------------------------------------------------
# _init_gen_state
# ---------------------------------------------------------------------------

class TestInitGenState:
    def test_sets_section_overrides_when_absent(self):
        state = {}
        _init_gen_state(state, _profile(), _job())
        assert isinstance(state["section_overrides"], dict)

    def test_does_not_overwrite_existing_overrides(self):
        state = {"section_overrides": {"headline": "override"}}
        _init_gen_state(state, _profile(), _job())
        assert state["section_overrides"] == {"headline": "override"}

    def test_sets_letter_text_via_heuristic(self):
        state = {}
        pipeline_mock = MagicMock(
            generate_cover_letter_heuristic=MagicMock(return_value="Bonjour,")
        )
        with patch.dict("sys.modules", {"Pipeline": pipeline_mock}):
            _init_gen_state(state, _profile(), _job())
        assert state["letter_text"] == "Bonjour,"

    def test_does_not_overwrite_existing_letter_text(self):
        state = {"letter_text": "Lettre existante"}
        _init_gen_state(state, _profile(), _job())
        assert state["letter_text"] == "Lettre existante"

    def test_returns_same_dict(self):
        state = {}
        result = _init_gen_state(state, _profile(), _job())
        assert result is state

    def test_sets_empty_string_when_heuristic_raises(self):
        state = {}
        pipeline_mock = MagicMock(
            generate_cover_letter_heuristic=MagicMock(side_effect=RuntimeError("fail"))
        )
        with patch.dict("sys.modules", {"Pipeline": pipeline_mock}):
            _init_gen_state(state, _profile(), _job())
        assert state.get("letter_text") == ""

    def test_sets_empty_string_when_pipeline_import_fails(self):
        state = {}
        with patch.dict("sys.modules", {"Pipeline": None}):
            _init_gen_state(state, _profile(), _job())
        assert state.get("letter_text") == ""


# ---------------------------------------------------------------------------
# mark_application_as_sent
# ---------------------------------------------------------------------------

class TestMarkApplicationAsSent:
    def test_calls_mark_as_sent_with_cv_data(self):
        db = _make_db()
        gen_state = {
            "cv_data": {"headline": "Senior Dev", "summary": "Expert Python"},
            "cv_path": "/vault/cv.pdf",
        }
        mark_application_as_sent("job-42", gen_state, db=db)
        db.mark_as_sent.assert_called_once_with(
            job_id="job-42",
            via="manual",
            edited_headline="Senior Dev",
            edited_summary="Expert Python",
            vault_path="/vault/cv.pdf",
        )

    def test_falls_back_to_letter_path_when_no_cv_path(self):
        db = _make_db()
        gen_state = {
            "cv_data": {"headline": "Dev", "summary": ""},
            "letter_path": "/vault/lettre.txt",
        }
        mark_application_as_sent("job-42", gen_state, db=db)
        kwargs = db.mark_as_sent.call_args.kwargs
        assert kwargs["vault_path"] == "/vault/lettre.txt"

    def test_handles_empty_gen_state_gracefully(self):
        db = _make_db()
        mark_application_as_sent("job-42", {}, db=db)
        kwargs = db.mark_as_sent.call_args.kwargs
        assert kwargs["edited_headline"] == ""
        assert kwargs["edited_summary"] == ""
        assert kwargs["vault_path"] is None

    def test_propagates_db_exception(self):
        db = _make_db()
        db.mark_as_sent.side_effect = RuntimeError("DB error")
        with pytest.raises(RuntimeError, match="DB error"):
            mark_application_as_sent("job-42", {}, db=db)


# ---------------------------------------------------------------------------
# save_final_candidate_version
# ---------------------------------------------------------------------------

class TestSaveFinalCandidateVersion:
    def _call(self, gen_state, tmp_path, gen_fn=None, db=None, cv_data=None):
        db = db or _make_db()
        gen_fn = gen_fn or _make_generate_documents_fn(cv_data=cv_data)
        save_final_candidate_version(
            "job-1", _job(), gen_state, photo_path=None,
            db=db, root=tmp_path, generate_documents_fn=gen_fn,
            safe_filename_fn=_safe_filename,
        )
        return db, gen_fn

    def test_updates_cv_path_in_gen_state(self, tmp_path):
        gen_state = {"section_overrides": {}, "cv_data": {}}
        self._call(gen_state, tmp_path)
        assert gen_state["cv_path"] == "/vault/cv.pdf"

    def test_updates_cv_data_from_result(self, tmp_path):
        gen_state = {"section_overrides": {}}
        cv_data = {"headline": "NewH", "summary": "NewS"}
        self._call(gen_state, tmp_path, cv_data=cv_data)
        assert gen_state["cv_data"]["headline"] == "NewH"

    def test_saves_resume_version_as_final(self, tmp_path):
        gen_state = {"section_overrides": {}, "cv_data": {"headline": "H", "summary": "S"}}
        db, _ = self._call(gen_state, tmp_path)
        db.save_resume_version.assert_called_once()
        kwargs = db.save_resume_version.call_args.kwargs
        assert kwargs["is_final"] is True
        assert kwargs["job_id"] == "job-1"

    def test_saves_cover_letter_version_when_letter_present(self, tmp_path):
        gen_state = {
            "section_overrides": {},
            "cv_data": {},
            "letter_text": "Bonjour,",
        }
        db, _ = self._call(gen_state, tmp_path)
        db.save_cover_letter_version.assert_called_once()
        kwargs = db.save_cover_letter_version.call_args.kwargs
        assert kwargs["is_final"] is True

    def test_skips_cover_letter_when_no_letter_text(self, tmp_path):
        gen_state = {"section_overrides": {}, "cv_data": {}, "letter_text": ""}
        db, _ = self._call(gen_state, tmp_path)
        db.save_cover_letter_version.assert_not_called()

    def test_persists_letter_to_disk(self, tmp_path):
        gen_state = {
            "section_overrides": {},
            "cv_data": {},
            "letter_text": "Monsieur,",
        }
        self._call(gen_state, tmp_path)
        assert "letter_path" in gen_state
        assert Path(gen_state["letter_path"]).read_text(encoding="utf-8") == "Monsieur,"

    def test_propagates_exception_from_generate_documents(self, tmp_path):
        gen_state = {"section_overrides": {}}
        gen_fn = MagicMock(side_effect=RuntimeError("Typst error"))
        with pytest.raises(RuntimeError, match="Typst error"):
            save_final_candidate_version(
                "job-1", _job(), gen_state, photo_path=None,
                db=_make_db(), root=tmp_path,
                generate_documents_fn=gen_fn,
                safe_filename_fn=_safe_filename,
            )

    def test_returns_same_gen_state_dict(self, tmp_path):
        gen_state = {"section_overrides": {}, "cv_data": {}}
        result = save_final_candidate_version(
            "job-1", _job(), gen_state, photo_path=None,
            db=_make_db(), root=tmp_path,
            generate_documents_fn=_make_generate_documents_fn(),
            safe_filename_fn=_safe_filename,
        )
        assert result is gen_state

    def test_keeps_existing_cv_path_when_result_is_empty(self, tmp_path):
        gen_fn = MagicMock(return_value={"cv_path": "", "cv_result": {}, "letter_text": "", "letter_path": ""})
        gen_state = {"section_overrides": {}, "cv_path": "/existing/cv.pdf", "cv_data": {}}
        self._call(gen_state, tmp_path, gen_fn=gen_fn)
        assert gen_state["cv_path"] == "/existing/cv.pdf"
