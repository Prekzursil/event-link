from datetime import datetime
from typing import Optional

from .models import Event, User
from .config import settings


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


def _frontend_hint() -> str:
    origins = getattr(settings, "allowed_origins", None) or []
    if not origins:
        return ""
    return str(origins[0]).rstrip("/")


def render_weekly_digest_email(
    user: User,
    events: list[Event],
    *,
    lang: str = "ro",
) -> tuple[str, str, str]:
    lang = (lang or "ro").split(",")[0][:2].lower()
    name = user.full_name or user.email
    frontend = _frontend_hint()

    lines_text: list[str] = []
    lines_html: list[str] = []
    for event in events[:10]:
        start_text = _format_dt(event.start_time)
        location = " • ".join([p for p in [event.city, event.location] if p]) or "-"
        link = f"{frontend}/events/{event.id}" if frontend else ""
        if lang == "en":
            lines_text.append(f"- {event.title} ({start_text}) — {location}{(' — ' + link) if link else ''}")
        else:
            lines_text.append(f"- {event.title} ({start_text}) — {location}{(' — ' + link) if link else ''}")
        safe_link = f' <a href="{link}">View</a>' if link else ""
        lines_html.append(
            f"<li><strong>{event.title}</strong> <span>({start_text})</span> — {location}{safe_link}</li>"
        )

    if lang == "en":
        subject = "Your weekly EventLink digest"
        body = (
            f"Hi {name},\n\n"
            "Here are some events you might like this week:\n"
            + ("\n".join(lines_text) if lines_text else "- No recommendations yet.\n")
            + "\n\nYou can update notification preferences in your profile."
        )
        html = (
            f"<p>Hi {name},</p>"
            "<p>Here are some events you might like this week:</p>"
            + (f"<ul>{''.join(lines_html)}</ul>" if lines_html else "<p><em>No recommendations yet.</em></p>")
            + "<p>You can update notification preferences in your profile.</p>"
        )
    else:
        subject = "Rezumat săptămânal EventLink"
        body = (
            f"Salut {name},\n\n"
            "Iată câteva evenimente recomandate pentru săptămâna aceasta:\n"
            + ("\n".join(lines_text) if lines_text else "- Încă nu avem recomandări.\n")
            + "\n\nPoți schimba preferințele de notificări în profil."
        )
        html = (
            f"<p>Salut {name},</p>"
            "<p>Iată câteva evenimente recomandate pentru săptămâna aceasta:</p>"
            + (f"<ul>{''.join(lines_html)}</ul>" if lines_html else "<p><em>Încă nu avem recomandări.</em></p>")
            + "<p>Poți schimba preferințele de notificări în profil.</p>"
        )
    return subject, body, html


def render_filling_fast_email(
    user: User,
    event: Event,
    *,
    available_seats: int | None,
    lang: str = "ro",
) -> tuple[str, str, str]:
    lang = (lang or "ro").split(",")[0][:2].lower()
    name = user.full_name or user.email
    start_text = _format_dt(event.start_time)
    location = " • ".join([p for p in [event.city, event.location] if p]) or "-"
    frontend = _frontend_hint()
    link = f"{frontend}/events/{event.id}" if frontend else ""
    seats_line = (
        f"{available_seats} seats left" if lang == "en" else f"{available_seats} locuri rămase"
        if available_seats is not None
        else ("Limited seats" if lang == "en" else "Locuri limitate")
    )

    if lang == "en":
        subject = f"Filling fast: {event.title}"
        body = (
            f"Hi {name},\n\n"
            f"'{event.title}' is filling up.\n"
            f"Starts: {start_text}\n"
            f"Location: {location}\n"
            f"{seats_line}\n\n"
            + (f"View event: {link}\n\n" if link else "")
            + "You can update notification preferences in your profile."
        )
        html = (
            f"<p>Hi {name},</p>"
            f"<p><strong>{event.title}</strong> is filling up.</p>"
            f"<p><strong>Starts:</strong> {start_text}<br>"
            f"<strong>Location:</strong> {location}<br>"
            f"<strong>{seats_line}</strong></p>"
            + (f"<p><a href=\"{link}\">View event</a></p>" if link else "")
            + "<p>You can update notification preferences in your profile.</p>"
        )
    else:
        subject = f"Se ocupă rapid: {event.title}"
        body = (
            f"Salut {name},\n\n"
            f"Evenimentul '{event.title}' se ocupă rapid.\n"
            f"Începe: {start_text}\n"
            f"Locație: {location}\n"
            f"{seats_line}\n\n"
            + (f"Vezi evenimentul: {link}\n\n" if link else "")
            + "Poți schimba preferințele de notificări în profil."
        )
        html = (
            f"<p>Salut {name},</p>"
            f"<p>Evenimentul <strong>{event.title}</strong> se ocupă rapid.</p>"
            f"<p><strong>Începe:</strong> {start_text}<br>"
            f"<strong>Locație:</strong> {location}<br>"
            f"<strong>{seats_line}</strong></p>"
            + (f"<p><a href=\"{link}\">Vezi evenimentul</a></p>" if link else "")
            + "<p>Poți schimba preferințele de notificări în profil.</p>"
        )
    return subject, body, html
