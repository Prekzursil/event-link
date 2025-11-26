from datetime import datetime
from typing import Optional

from .models import Event, User


def _format_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    # Use ISO local string with date/time for simplicity; frontend shows local time.
    return dt.strftime("%Y-%m-%d %H:%M")


def render_registration_email(event: Event, user: User, lang: str = "ro") -> tuple[str, str, str]:
    lang = (lang or "ro").split(",")[0][:2].lower()
    start_text = _format_dt(event.start_time)
    common = {
        "title": event.title,
        "location": event.location or "-",
        "start": start_text,
        "name": user.full_name or user.email,
    }
    if lang == "en":
        subject = f"Registration confirmed: {common['title']}"
        body = (
            f"Hi {common['name']},\n\n"
            f"You are registered for '{common['title']}'.\n"
            f"Starts at: {common['start']}\n"
            f"Location: {common['location']}\n\n"
            "See you there!"
        )
        html = (
            f"<p>Hi {common['name']},</p>"
            f"<p>You are registered for <strong>{common['title']}</strong>.</p>"
            f"<p><strong>Starts:</strong> {common['start']}<br>"
            f"<strong>Location:</strong> {common['location']}</p>"
            "<p>See you there!</p>"
        )
    else:
        subject = f"Confirmare înscriere: {common['title']}"
        body = (
            f"Salut {common['name']},\n\n"
            f"Te-ai înscris la evenimentul '{common['title']}'.\n"
            f"Data și ora de start: {common['start']}.\n"
            f"Locația: {common['location']}.\n\n"
            "Ne vedem acolo!"
        )
        html = (
            f"<p>Salut {common['name']},</p>"
            f"<p>Te-ai înscris la <strong>{common['title']}</strong>.</p>"
            f"<p><strong>Începe la:</strong> {common['start']}<br>"
            f"<strong>Locație:</strong> {common['location']}</p>"
            "<p>Ne vedem acolo!</p>"
        )
    return subject, body, html
