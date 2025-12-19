def test_registration_endpoints_disabled_in_maintenance_mode(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "ownerpass")
    organizer_token = helpers["login"]("owner@test.ro", "ownerpass")

    event = client.post(
        "/api/events",
        json={
            "title": "Maintenance Event",
            "description": "Desc",
            "category": "Tech",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
            "status": "published",
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("student@test.ro")

    from app.config import settings

    old = getattr(settings, "maintenance_mode_registrations_disabled", False)
    settings.maintenance_mode_registrations_disabled = True
    try:
        register = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
        assert register.status_code == 503

        resend = client.post(
            f"/api/events/{event['id']}/register/resend",
            headers=helpers["auth_header"](student_token),
        )
        assert resend.status_code == 503

        unregister = client.delete(
            f"/api/events/{event['id']}/register",
            headers=helpers["auth_header"](student_token),
        )
        assert unregister.status_code == 503
    finally:
        settings.maintenance_mode_registrations_disabled = old
