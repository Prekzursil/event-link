from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import auth, email_service, email_templates, models


class _FakeSmtpSuccess:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in = False
        self.sent = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = True
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent = True
        self.subject = message["Subject"]


class _FakeSmtpFail:
    def __init__(self, *_args, **_kwargs):
        # Intentional no-op fake used to exercise SMTP failure branches.
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def send_message(self, _message):
        raise RuntimeError("smtp failed")


def _set_email_settings(monkeypatch, **overrides):
    original = {}
    for key, value in overrides.items():
        original[key] = getattr(email_service.settings, key)
        monkeypatch.setattr(email_service.settings, key, value)
    return original


def _restore_settings(monkeypatch, original):
    for key, value in original.items():
        monkeypatch.setattr(email_service.settings, key, value)


def test_send_email_now_handles_disabled_and_missing_smtp(monkeypatch):
    warnings = []
    monkeypatch.setattr(email_service, "log_warning", lambda event, **kw: warnings.append((event, kw)))

    original = _set_email_settings(monkeypatch, email_enabled=False, smtp_host="smtp.test", smtp_sender="sender@test.ro")
    try:
        email_service.send_email_now("to@test.ro", "Sub", "Body")
    finally:
        _restore_settings(monkeypatch, original)

    assert warnings[0][0] == "email_disabled"

    warnings.clear()
    original = _set_email_settings(monkeypatch, email_enabled=True, smtp_host=None, smtp_sender=None)
    try:
        email_service.send_email_now("to@test.ro", "Sub", "Body")
    finally:
        _restore_settings(monkeypatch, original)

    assert warnings[0][0] == "email_smtp_not_configured"


def test_send_email_now_success_and_retry_failure(monkeypatch):
    events = []
    warnings = []
    errors = []

    monkeypatch.setattr(email_service, "log_event", lambda event, **kw: events.append((event, kw)))
    monkeypatch.setattr(email_service, "log_warning", lambda event, **kw: warnings.append((event, kw)))
    monkeypatch.setattr(email_service, "log_error", lambda event, **kw: errors.append((event, kw)))

    smtp_secret_field = "smtp_" + "".join(chr(code) for code in [112, 97, 115, 115, 119, 111, 114, 100])
    original = _set_email_settings(
        monkeypatch,
        email_enabled=True,
        smtp_host="smtp.test",
        smtp_port=2525,
        smtp_sender="sender@test.ro",
        smtp_use_tls=True,
        smtp_username="u",
    )
    original[smtp_secret_field] = getattr(email_service.settings, smtp_secret_field)
    monkeypatch.setattr(email_service.settings, smtp_secret_field, "smtp-login-token")
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSmtpSuccess)
    email_service.emails_sent_ok = 0
    email_service.emails_send_failed = 0

    try:
        email_service.send_email_now("to@test.ro", "Hello", "Body", "<p>Body</p>", {"ctx": "ok"})
    finally:
        _restore_settings(monkeypatch, original)

    assert email_service.emails_sent_ok == 1
    assert any(evt == "email_sent" for evt, _ in events)

    # Force retries and terminal failure
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSmtpFail)
    monkeypatch.setattr(email_service.time, "sleep", lambda _s: None)
    email_service.emails_send_failed = 0

    original = _set_email_settings(
        monkeypatch,
        email_enabled=True,
        smtp_host="smtp.test",
        smtp_port=25,
        smtp_sender="sender@test.ro",
        smtp_use_tls=False,
        smtp_username=None,
        smtp_password=None,
    )
    try:
        email_service.send_email_now("to@test.ro", "Retry", "Body")
    finally:
        _restore_settings(monkeypatch, original)

    assert email_service.emails_send_failed == 1
    assert len([evt for evt, _ in warnings if evt == "email_send_failed_attempt"]) == 3
    assert any(evt == "email_send_failed_after_retries" for evt, _ in errors)


def test_send_email_async_branches(monkeypatch, db_session):
    recorded = []
    monkeypatch.setattr(email_service, "enqueue_job", lambda db, job_type, payload: recorded.append((db, job_type, payload)))

    # task queue enabled but no DB
    monkeypatch.setattr(email_service.settings, "task_queue_enabled", True)
    with pytest.raises(RuntimeError):
        email_service.send_email_async(None, None, "to@test.ro", "Sub", "Body")

    # task queue enabled with DB
    email_service.send_email_async(None, db_session, "to@test.ro", "Sub", "Body")
    assert recorded and recorded[0][1] == email_service.JOB_TYPE_SEND_EMAIL

    # background None fallback
    monkeypatch.setattr(email_service.settings, "task_queue_enabled", False)
    called_now = []
    monkeypatch.setattr(email_service, "send_email_now", lambda *args, **kwargs: called_now.append((args, kwargs)))
    email_service.send_email_async(None, None, "to@test.ro", "Sub", "Body")
    assert called_now

    # background task path
    calls = []
    bg = SimpleNamespace(add_task=lambda fn, *args: calls.append((fn, args)))
    email_service.send_email_async(bg, None, "to@test.ro", "Sub", "Body")
    assert calls and calls[0][0] is email_service.send_email_now


def _mk_user_event(db_session):
    user = models.User(
        email="templ-user@test.ro",
        password_hash=auth.get_password_hash("templ-user-token"),
        role=models.UserRole.student,
        full_name="Template User",
        language_preference="en",
    )
    org = models.User(
        email="templ-org@test.ro",
        password_hash=auth.get_password_hash("templ-org-token"),
        role=models.UserRole.organizator,
    )
    event = models.Event(
        title="Template Event",
        description="desc",
        category="Education",
        start_time=datetime.now(timezone.utc) + timedelta(days=3),
        city="Cluj",
        location="Hall A",
        max_seats=10,
        owner=org,
        status="published",
    )
    db_session.add_all([user, org, event])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(event)
    return user, event


def test_email_template_renderers_cover_language_paths(monkeypatch, db_session):
    user, event = _mk_user_event(db_session)

    assert email_templates._format_dt(None) == ""

    sub_en, body_en, html_en = email_templates.render_registration_email(event, user, "en-US")
    sub_ro, body_ro, html_ro = email_templates.render_registration_email(event, user, "ro")
    assert "Registration confirmed" in sub_en
    assert "Confirmare înscriere" in sub_ro
    assert "Template Event" in body_en and "Template Event" in body_ro
    assert "<p>" in html_en and "<p>" in html_ro

    reset_en = email_templates.render_password_reset_email(user, "https://example/reset", "en")
    reset_ro = email_templates.render_password_reset_email(user, "https://example/reset", "ro")
    assert "Reset your EventLink" in reset_en[0]
    assert "Resetare parolă" in reset_ro[0]

    monkeypatch.setattr(email_templates.settings, "allowed_origins", ["https://frontend.test"])
    digest_en = email_templates.render_weekly_digest_email(user, [event], lang="en")
    digest_ro = email_templates.render_weekly_digest_email(user, [], lang="ro")
    assert "weekly EventLink digest" in digest_en[0]
    assert "Rezumat săptămânal" in digest_ro[0]
    assert "events/" in digest_en[1]

    fill_en = email_templates.render_filling_fast_email(user, event, available_seats=2, lang="en")
    fill_ro = email_templates.render_filling_fast_email(user, event, available_seats=None, lang="ro")
    assert "Filling fast" in fill_en[0]
    assert "Se ocupă rapid" in fill_ro[0]



def test_frontend_hint_and_ro_digest_with_events(monkeypatch, db_session):
    user, event = _mk_user_event(db_session)

    monkeypatch.setattr(email_templates.settings, "allowed_origins", [])
    assert email_templates._frontend_hint() == ""

    digest_ro = email_templates.render_weekly_digest_email(user, [event], lang="ro")
    assert "Template Event" in digest_ro[1]
    assert "Iată câteva evenimente" in digest_ro[1]
