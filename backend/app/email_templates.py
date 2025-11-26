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


def render_password_reset_email(user: User, reset_link: str, lang: str = "ro") -> tuple[str, str, str]:
    lang = (lang or "ro").split(",")[0][:2].lower()
    if lang == "en":
        subject = "Reset your EventLink password"
        body = (
            f"You requested a password reset for {user.email}.\n\n"
            f"Use this link (valid for 1 hour): {reset_link}\n\n"
            "If you did not request this, please ignore this email."
        )
        html = (
            f"<p>You requested a password reset for <strong>{user.email}</strong>.</p>"
            f"<p><a href=\"{reset_link}\">Reset password</a> (valid for 1 hour)</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        )
    else:
        subject = "Resetare parolă EventLink"
        body = (
            f"Ai cerut resetarea parolei pentru contul {user.email}.\n\n"
            f"Folosește link-ul (valabil 1 oră): {reset_link}\n\n"
            "Dacă nu ai cerut tu această resetare, poți ignora acest email."
        )
        html = (
            f"<p>Ai cerut resetarea parolei pentru <strong>{user.email}</strong>.</p>"
            f"<p><a href=\"{reset_link}\">Resetează parola</a> (valabil 1 oră)</p>"
            "<p>Dacă nu ai cerut tu această resetare, poți ignora acest email.</p>"
        )
    return subject, body, html
