import os
import unittest
from datetime import datetime, timedelta, timezone

# Ensure test configuration before importing the app
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient
from app import models, auth
from app.api import app
from app.database import Base, engine, SessionLocal, get_db


class APITestCase(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        def _override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(app)

    def register_student(self, email: str) -> str:
        response = self.client.post(
            "/register",
            json={"email": email, "password": "password123", "confirm_password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def login(self, email: str, password: str) -> str:
        response = self.client.post("/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def make_organizer(self, email="org@test.ro", password="organizer123") -> None:
        db = SessionLocal()
        organizer = models.User(
            email=email,
            password_hash=auth.get_password_hash(password),
            role=models.UserRole.organizator,
        )
        db.add(organizer)
        db.commit()
        db.close()

    def future_time(self, days=1) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_student_registration_and_duplicate_email(self):
        first = self.client.post(
            "/register",
            json={"email": "student@test.ro", "password": "password123", "confirm_password": "password123"},
        )
        self.assertEqual(first.status_code, 200)
        duplicate = self.client.post(
            "/register",
            json={"email": "student@test.ro", "password": "password123", "confirm_password": "password123"},
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("deja folosit", duplicate.json().get("detail", ""))

    def test_login_failure(self):
        self.register_student("login@test.ro")
        bad = self.client.post("/login", json={"email": "login@test.ro", "password": "wrong"})
        self.assertEqual(bad.status_code, 401)
        self.assertIn("incorectă", bad.json().get("detail", ""))

    def test_event_creation_and_capacity_enforced(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")

        start_time = self.future_time()
        payload = {
            "title": "Test Event",
            "description": "Descriere",
            "category": "Test",
            "start_time": start_time,
            "end_time": None,
            "location": "Online",
            "max_seats": 1,
            "tags": ["test"],
        }
        create_resp = self.client.post(
            "/api/events",
            json=payload,
            headers={"Authorization": f"Bearer {organizer_token}"},
        )
        self.assertEqual(create_resp.status_code, 201)
        event_id = create_resp.json()["id"]

        # student one registers successfully
        student1_token = self.register_student("s1@test.ro")
        reg1 = self.client.post(
            f"/api/events/{event_id}/register",
            headers={"Authorization": f"Bearer {student1_token}"},
        )
        self.assertEqual(reg1.status_code, 201)

        # student two blocked by capacity
        student2_token = self.register_student("s2@test.ro")
        reg2 = self.client.post(
            f"/api/events/{event_id}/register",
            headers={"Authorization": f"Bearer {student2_token}"},
        )
        self.assertEqual(reg2.status_code, 409)
        self.assertIn("plin", reg2.json().get("detail", ""))

    def test_student_cannot_create_event(self):
        student_token = self.register_student("stud@test.ro")
        payload = {
            "title": "Invalid",
            "description": "Desc",
            "category": "Test",
            "start_time": self.future_time(),
            "end_time": None,
            "location": "Online",
            "max_seats": 10,
            "tags": [],
        }
        resp = self.client.post("/api/events", json=payload, headers=self.auth_header(student_token))
        self.assertEqual(resp.status_code, 403)

    def test_edit_forbidden_for_non_owner(self):
        self.make_organizer("o1@test.ro", "pass1")
        self.make_organizer("o2@test.ro", "pass2")
        owner_token = self.login("o1@test.ro", "pass1")
        other_token = self.login("o2@test.ro", "pass2")

        create_resp = self.client.post(
            "/api/events",
            json={
                "title": "Owner Event",
                "description": "Desc",
                "category": "Cat",
                "start_time": self.future_time(),
                "location": "Loc",
                "max_seats": 5,
                "tags": [],
            },
            headers=self.auth_header(owner_token),
        )
        event_id = create_resp.json()["id"]

        update = self.client.put(
            f"/api/events/{event_id}",
            json={"title": "Hack"},
            headers=self.auth_header(other_token),
        )
        self.assertEqual(update.status_code, 403)

    def test_delete_cascades_registrations(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")
        create_resp = self.client.post(
            "/api/events",
            json={
                "title": "Delete Me",
                "description": "Desc",
                "category": "Cat",
                "start_time": self.future_time(),
                "location": "Loc",
                "max_seats": 2,
                "tags": [],
            },
            headers=self.auth_header(organizer_token),
        )
        event_id = create_resp.json()["id"]

        student_token = self.register_student("stud@test.ro")
        self.client.post(f"/api/events/{event_id}/register", headers=self.auth_header(student_token))

        delete_resp = self.client.delete(f"/api/events/{event_id}", headers=self.auth_header(organizer_token))
        self.assertEqual(delete_resp.status_code, 204)

        db = SessionLocal()
        remaining_regs = db.query(models.Registration).count()
        db.close()
        self.assertEqual(remaining_regs, 0)

    def test_events_list_filters_and_order(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")
        base_payload = {
            "description": "Desc",
            "category": "Tech",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        }
        e1 = self.client.post(
            "/api/events",
            json={**base_payload, "title": "Python Workshop", "start_time": self.future_time(days=2)},
            headers=self.auth_header(organizer_token),
        ).json()
        e2 = self.client.post(
            "/api/events",
            json={**base_payload, "title": "Party Night", "category": "Social", "start_time": self.future_time(days=3)},
            headers=self.auth_header(organizer_token),
        ).json()
        self.client.post(
            "/api/events",
            json={**base_payload, "title": "Old Event", "start_time": self.future_time(days=-1)},
            headers=self.auth_header(organizer_token),
        )

        events = self.client.get("/api/events").json()
        self.assertEqual([e1["id"], e2["id"]], [e["id"] for e in events["items"]])
        self.assertEqual(events["total"], 2)

        search = self.client.get("/api/events", params={"search": "python"}).json()
        self.assertEqual(search["total"], 1)
        self.assertEqual(search["items"][0]["title"], "Python Workshop")

        category = self.client.get("/api/events", params={"category": "social"}).json()
        self.assertEqual(category["total"], 1)
        self.assertEqual(category["items"][0]["title"], "Party Night")

        start_filter = self.client.get(
            "/api/events", params={"start_date": datetime.now(timezone.utc).date().isoformat()}
        ).json()
        self.assertGreaterEqual(len(start_filter["items"]), 2)

        end_filter = self.client.get(
            "/api/events", params={"end_date": datetime.now(timezone.utc).date().isoformat()}
        ).json()
        self.assertEqual(end_filter["total"], 0)

    def test_my_events_and_registration_state(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")
        e1 = self.client.post(
            "/api/events",
            json={
                "title": "Early",
                "description": "Desc",
                "category": "Cat",
                "start_time": self.future_time(days=2),
                "location": "Loc",
                "max_seats": 5,
                "tags": [],
            },
            headers=self.auth_header(organizer_token),
        ).json()
        e2 = self.client.post(
            "/api/events",
            json={
                "title": "Late",
                "description": "Desc",
                "category": "Cat",
                "start_time": self.future_time(days=5),
                "location": "Loc",
                "max_seats": 5,
                "tags": [],
            },
            headers=self.auth_header(organizer_token),
        ).json()

        student_token = self.register_student("stud@test.ro")
        self.client.post(f"/api/events/{e2['id']}/register", headers=self.auth_header(student_token))
        self.client.post(f"/api/events/{e1['id']}/register", headers=self.auth_header(student_token))

        my_events = self.client.get("/api/me/events", headers=self.auth_header(student_token)).json()
        self.assertEqual([e1["id"], e2["id"]], [e["id"] for e in my_events])

        detail = self.client.get(f"/api/events/{e1['id']}", headers=self.auth_header(student_token)).json()
        self.assertTrue(detail["is_registered"])
        self.assertEqual(detail["seats_taken"], 1)

    def test_recommended_uses_tags_and_excludes_registered(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")
        tag_payload = {
            "description": "Desc",
            "category": "Tech",
            "location": "Loc",
            "max_seats": 10,
        }
        python_event = self.client.post(
            "/api/events",
            json={**tag_payload, "title": "Python 1", "start_time": self.future_time(days=2), "tags": ["python"]},
            headers=self.auth_header(organizer_token),
        ).json()
        another_python = self.client.post(
            "/api/events",
            json={**tag_payload, "title": "Python 2", "start_time": self.future_time(days=3), "tags": ["python"]},
            headers=self.auth_header(organizer_token),
        ).json()

        student_token = self.register_student("stud@test.ro")
        self.client.post(f"/api/events/{python_event['id']}/register", headers=self.auth_header(student_token))

        rec_resp = self.client.get("/api/recommendations", headers=self.auth_header(student_token))
        self.assertEqual(rec_resp.status_code, 200, msg=rec_resp.text)
        rec = rec_resp.json()
        rec_ids = [e["id"] for e in rec]
        self.assertIn(another_python["id"], rec_ids)
        self.assertNotIn(python_event["id"], rec_ids)

    def test_duplicate_registration_blocked(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")
        event = self.client.post(
            "/api/events",
            json={
                "title": "Dup",
                "description": "Desc",
                "category": "Cat",
                "start_time": self.future_time(days=1),
                "location": "Loc",
                "max_seats": 3,
                "tags": [],
            },
            headers=self.auth_header(organizer_token),
        ).json()
        student_token = self.register_student("stud@test.ro")
        first = self.client.post(f"/api/events/{event['id']}/register", headers=self.auth_header(student_token))
        self.assertEqual(first.status_code, 201)
        second = self.client.post(f"/api/events/{event['id']}/register", headers=self.auth_header(student_token))
        self.assertEqual(second.status_code, 400)
        self.assertIn("deja înscris", second.json().get("detail", ""))

    def test_unregister_restores_spot(self):
        self.make_organizer()
        organizer_token = self.login("org@test.ro", "organizer123")
        event = self.client.post(
            "/api/events",
            json={
                "title": "Unregister Test",
                "description": "Desc",
                "category": "Cat",
                "start_time": self.future_time(days=1),
                "location": "Loc",
                "max_seats": 1,
                "tags": [],
            },
            headers=self.auth_header(organizer_token),
        ).json()
        student_token = self.register_student("stud@test.ro")
        reg = self.client.post(f"/api/events/{event['id']}/register", headers=self.auth_header(student_token))
        self.assertEqual(reg.status_code, 201)

        unregister = self.client.delete(f"/api/events/{event['id']}/register", headers=self.auth_header(student_token))
        self.assertEqual(unregister.status_code, 204)

        # another student can now register
        other_token = self.register_student("stud2@test.ro")
        reg2 = self.client.post(f"/api/events/{event['id']}/register", headers=self.auth_header(other_token))
        self.assertEqual(reg2.status_code, 201)

    def test_upgrade_to_organizer_requires_code(self):
        student_token = self.register_student("code@test.ro")
        # missing/invalid code
        bad = self.client.post("/organizer/upgrade", json={"invite_code": "wrong"}, headers=self.auth_header(student_token))
        self.assertEqual(bad.status_code, 403)


if __name__ == "__main__":
    unittest.main()
