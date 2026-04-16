"""Support module: email templates."""
from datetime import datetime
from typing import Optional

from .config import settings
from .models import Event, User


def _format_dt(dt: Optional[datetime]) -> str:
    """Implements the format dt helper."""
    if not dt:
        return ""
    # Use ISO local string with date/time for simplicity; frontend shows local time.
    return dt.strftime("%Y-%m-%d %H:%M")


def _normalized_lang(lang: str) -> str:
    """Implements the normalized lang helper."""
    return (lang or "ro").split(",")[0][:2].lower()


def _user_name(user: User) -> str:
    """Implements the user name helper."""
    return user.full_name or user.email


def render_registration_email(event: Event, user: User, lang: str = "ro") -> tuple[str, str, str]:
    """Implements the render registration email helper."""
    lang = _normalized_lang(lang)
    start_text = _format_dt(event.start_time)
    common = {
        "title": event.title,
        "location": event.location or "-",
        "start": start_text,
        "name": _user_name(user),
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
    """Implements the render password reset email helper."""
    lang = _normalized_lang(lang)
    if lang == "en":
        subject = "Reset your EventLink password"
        body = (
            f"You requested a password reset for {user.email}.\n\n"
            f"Use this link (valid for 1 hour): {reset_link}\n\n"
            "If you did not request this, please ignore this email."
        )
        html = (
            f"<p>You requested a password reset for <strong>{user.email}</strong>.</p>"
            f'<p><a href="{reset_link}">Reset password</a> (valid for 1 hour)</p>'
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
            f'<p><a href="{reset_link}">Resetează parola</a> (valabil 1 oră)</p>'
            "<p>Dacă nu ai cerut tu această resetare, poți ignora acest email.</p>"
        )
    return subject, body, html


def _frontend_hint() -> str:
    """Implements the frontend hint helper."""
    origins = getattr(settings, "allowed_origins", None) or []
    if not origins:
        return ""
    return str(origins[0]).rstrip("/")


def _event_location(event: Event) -> str:
    """Implements the event location helper."""
    return " • ".join(part for part in [event.city, event.location] if part) or "-"


def _event_link(event: Event, frontend: str) -> str:
    """Implements the event link helper."""
    return f"{frontend}/events/{event.id}" if frontend else ""


def _digest_item(event: Event, frontend: str) -> tuple[str, str]:
    """Implements the digest item helper."""
    start_text = _format_dt(event.start_time)
    location = _event_location(event)
    link = _event_link(event, frontend)
    text_suffix = f" — {link}" if link else ""
    text = f"- {event.title} ({start_text}) — {location}{text_suffix}"
    html_link = f' <a href="{link}">View</a>' if link else ""
    html = f"<li><strong>{event.title}</strong> <span>({start_text})</span> — {location}{html_link}</li>"
    return text, html


def _digest_items(events: list[Event], frontend: str) -> tuple[list[str], list[str]]:
    """Implements the digest items helper."""
    lines_text: list[str] = []
    lines_html: list[str] = []
    for event in events[:10]:
        text, html = _digest_item(event, frontend)
        lines_text.append(text)
        lines_html.append(html)
    return lines_text, lines_html


def _digest_fallback(lang: str) -> tuple[str, str]:
    """Implements the digest fallback helper."""
    if lang == "en":
        return "- No recommendations yet.\n", "<p><em>No recommendations yet.</em></p>"
    return "- Încă nu avem recomandări.\n", "<p><em>Încă nu avem recomandări.</em></p>"


def _digest_copy(lang: str, name: str, lines_text: list[str], lines_html: list[str]) -> tuple[str, str, str]:
    """Implements the digest copy helper."""
    if lang == "en":
        subject = "Your weekly EventLink digest"
        intro = f"Hi {name},\n\nHere are some events you might like this week:\n"
        html_intro = f"<p>Hi {name},</p><p>Here are some events you might like this week:</p>"
        outro = "\n\nYou can update notification preferences in your profile."
        html_outro = "<p>You can update notification preferences in your profile.</p>"
    else:
        subject = "Rezumat săptămânal EventLink"
        intro = f"Salut {name},\n\nIată câteva evenimente recomandate pentru săptămâna aceasta:\n"
        html_intro = f"<p>Salut {name},</p><p>Iată câteva evenimente recomandate pentru săptămâna aceasta:</p>"
        outro = "\n\nPoți schimba preferințele de notificări în profil."
        html_outro = "<p>Poți schimba preferințele de notificări în profil.</p>"

    fallback_text, fallback_html = _digest_fallback(lang)
    body_lines = "\n".join(lines_text) if lines_text else fallback_text
    html_lines = f"<ul>{''.join(lines_html)}</ul>" if lines_html else fallback_html
    return subject, intro + body_lines + outro, html_intro + html_lines + html_outro


def render_weekly_digest_email(
    user: User,
    events: list[Event],
    *,
    lang: str = "ro",
) -> tuple[str, str, str]:
    """Implements the render weekly digest email helper."""
    lang = _normalized_lang(lang)
    lines_text, lines_html = _digest_items(events, _frontend_hint())
    return _digest_copy(lang, _user_name(user), lines_text, lines_html)


def _seats_line(lang: str, available_seats: int | None) -> str:
    """Implements the seats line helper."""
    if available_seats is None:
        return "Limited seats" if lang == "en" else "Locuri limitate"
    return f"{available_seats} seats left" if lang == "en" else f"{available_seats} locuri rămase"


def _filling_fast_copy(
    *,
    lang: str,
    name: str,
    event: Event,
    start_text: str,
    location: str,
    seats_line: str,
    link: str,
) -> tuple[str, str, str]:
    """Implements the filling fast copy helper."""
    if lang == "en":
        subject = f"Filling fast: {event.title}"
        headline = f"<strong>{event.title}</strong> is filling up."
        intro = f"Hi {name},\n\n'{event.title}' is filling up.\n"
        labels = {"start": "Starts", "location": "Location", "link": "View event"}
        outro = "You can update notification preferences in your profile."
    else:
        subject = f"Se ocupă rapid: {event.title}"
        headline = f"Evenimentul <strong>{event.title}</strong> se ocupă rapid."
        intro = f"Salut {name},\n\nEvenimentul '{event.title}' se ocupă rapid.\n"
        labels = {"start": "Începe", "location": "Locație", "link": "Vezi evenimentul"}
        outro = "Poți schimba preferințele de notificări în profil."

    body = intro + f"{labels['start']}: {start_text}\n{labels['location']}: {location}\n{seats_line}\n\n"
    html_intro = (
        f"<p>{'Hi' if lang == 'en' else 'Salut'} {name},</p>"
        f"<p>{headline}</p>"
        f"<p><strong>{labels['start']}:</strong> {start_text}<br>"
        f"<strong>{labels['location']}:</strong> {location}<br>"
        f"<strong>{seats_line}</strong></p>"
    )
    link_body = f"{labels['link']}: {link}\n\n" if link else ""
    link_html = f"<p><a href=\"{link}\">{labels['link']}</a></p>" if link else ""
    body += link_body + outro
    html = html_intro + link_html + f"<p>{outro}</p>"
    return subject, body, html


def render_filling_fast_email(
    user: User,
    event: Event,
    *,
    available_seats: int | None,
    lang: str = "ro",
) -> tuple[str, str, str]:
    """Implements the render filling fast email helper."""
    lang = _normalized_lang(lang)
    return _filling_fast_copy(
        lang=lang,
        name=_user_name(user),
        event=event,
        start_text=_format_dt(event.start_time),
        location=_event_location(event),
        seats_line=_seats_line(lang, available_seats),
        link=_event_link(event, _frontend_hint()),
    )
