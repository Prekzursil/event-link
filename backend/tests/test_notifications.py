from datetime import datetime, timezone

from app import models
from app.task_queue import (
    JOB_TYPE_SEND_WEEKLY_DIGEST,
    JOB_TYPE_SEND_EMAIL,
    enqueue_job,
    process_job,
)


def test_notification_preferences_get_and_update(client, helpers):
    token = helpers["register_student"]("student-notif@test.ro")
    headers = helpers["auth_header"](token)

    resp = client.get("/api/me/notifications", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email_digest_enabled"] is False
    assert resp.json()["email_filling_fast_enabled"] is False

    resp = client.put(
        "/api/me/notifications",
        headers=headers,
        json={"email_digest_enabled": True, "email_filling_fast_enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["email_digest_enabled"] is True
    assert resp.json()["email_filling_fast_enabled"] is True


def test_weekly_digest_job_enqueues_send_email_and_is_idempotent(client, helpers):
    helpers["make_organizer"]("org@test.ro")
    org_token = helpers["login"]("org@test.ro", "organizer123")
    resp = client.post(
        "/api/events",
        headers=helpers["auth_header"](org_token),
        json={
            "title": "Event",
            "description": "x",
            "category": "Education",
            "start_time": helpers["future_time"](days=10),
            "city": "Cluj",
            "location": "Hall A",
            "max_seats": 10,
            "tags": ["Tech"],
        },
    )
    assert resp.status_code == 201
    event_id = resp.json()["id"]

    student_token = helpers["register_student"]("student-digest@test.ro")
    db = helpers["db"]
    user = db.query(models.User).filter(models.User.email == "student-digest@test.ro").first()
    assert user is not None
    user.email_digest_enabled = True
    user.language_preference = "en"
    db.add(user)
    db.commit()

    db.add(
        models.UserRecommendation(
            user_id=int(user.id),
            event_id=int(event_id),
            score=1.0,
            rank=1,
            model_version="test",
            generated_at=datetime.now(timezone.utc),
            reason="Your interests: Tech",
        )
    )
    db.commit()

    job = enqueue_job(db, JOB_TYPE_SEND_WEEKLY_DIGEST, {"top_n": 5})
    process_job(db, job)

    queued_emails = db.query(models.BackgroundJob).filter(models.BackgroundJob.job_type == JOB_TYPE_SEND_EMAIL).all()
    assert len(queued_emails) == 1

    deliveries = db.query(models.NotificationDelivery).filter(models.NotificationDelivery.user_id == int(user.id)).all()
    assert len(deliveries) == 1

    # Run again: should not enqueue another email due to dedupe key
    job2 = enqueue_job(db, JOB_TYPE_SEND_WEEKLY_DIGEST, {"top_n": 5})
    process_job(db, job2)

    queued_emails2 = db.query(models.BackgroundJob).filter(models.BackgroundJob.job_type == JOB_TYPE_SEND_EMAIL).all()
    assert len(queued_emails2) == 1

