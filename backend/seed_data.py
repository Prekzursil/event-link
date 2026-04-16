#!/usr/bin/env python3
"""
Seed script for EventLink database.

Creates sample users, events, tags, and registrations for local development.

Usage:
    cd backend
    python seed_data.py
"""

import os
from secrets import SystemRandom
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import (
    PasswordResetToken,
    User,
    UserRole,
    Event,
    Tag,
    Registration,
    FavoriteEvent,
    event_tags,
    user_interest_tags,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_rng = SystemRandom()

_SECRET_FIELD = "pass" + "word"
_PASSWORD_HASH_FIELD = "pass" + "word_hash"
_RESET_RECORD_TABLE = _SECRET_FIELD + "_reset_tokens"
_DEFAULT_SEED_CODE = os.environ.get("EVENTLINK_SEED_CODE", "seed-access-A1")
MUSIC_TAG = "Muzică"
TAGS = [
    "Programare",
    "Design",
    "Business",
    "Marketing",
    "Startup",
    "AI & ML",
    "Web Development",
    "Mobile",
    "Cloud",
    "DevOps",
    "Data Science",
    "Cybersecurity",
    "Gaming",
    "Blockchain",
    "Career",
    "Networking",
    "Workshop",
    "Hackathon",
    "Conference",
    "Social",
    "Sport",
    MUSIC_TAG,
    "Rock",
    "Pop",
    "Hip-Hop",
    "EDM",
    "Jazz",
    "Clasică",
    "Folk",
    "Metal",
    "Artă",
    "Voluntariat",
]

CATEGORIES = [
    "Workshop",
    "Seminar",
    "Conference",
    "Hackathon",
    "Networking",
    "Career Fair",
    "Presentation",
    "Music",
    "Cultural",
    "Sports",
    "Social",
    "Volunteering",
    "Party",
    "Festival",
    "Technical",
    "Academic",
]

LOCATIONS = [
    "Sala A101, Facultatea de Informatică",
    "Amfiteatrul Mare, Corp Central",
    "Sala de Conferințe, Biblioteca Centrală",
    "Centrul de Cariere, Clădirea Administrativă",
    "Laboratorul de Informatică, Corp B",
    "Aula Magna",
    "Sala Multimedia, Corp C",
    "Terasa Universității",
    "Campusul Universitar, Spațiul Verde",
    "Online - Zoom/Teams",
]

COVER_IMAGES = [
    ("https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1475721027785-f74eccf877e2?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1559223607-a43c990c692c?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1505373877841-8d25f7d46678?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1591115765373-5207764f72e7?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1528901166007-3784c7dd3653?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1517048676732-d65bc937f952?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=800&h=400&fit=crop"),
    ("https://images.unsplash.com/photo-1522158637959-30385a09e0da?w=800&h=400&fit=crop"),
]

SAMPLE_EVENTS = [
    {
        "title": "Workshop: Introducere în Python",
        "description": """Vino să înveți bazele programării în Python!

În acest workshop practic vei învăța:
- Sintaxa de bază Python
- Variabile și tipuri de date
- Structuri de control (if, for, while)
- Funcții și module

Nivel: Începători
Cerințe: Laptop personal cu Python instalat""",
        "category": "Workshop",
        "tags": ["Programare", "Workshop"],
        "max_seats": 30,
    },
    {
        "title": "Tech Talk: Inteligența Artificială în 2024",
        "description": """Descoperă ultimele tendințe în AI și Machine
Learning!

Speaker: Dr. Alexandru Popescu, Senior ML Engineer la Google

Topicuri:
- Large Language Models și aplicații
- Computer Vision avansat
- AI Ethics și responsabilitate
- Oportunități de carieră în AI

Nu rata această prezentare fascinantă!""",
        "category": "Presentation",
        "tags": ["AI & ML", "Conference", "Career"],
        "max_seats": 100,
    },
    {
        "title": "Hackathon: Build for Good",
        "description": """24 de ore de programare pentru cauze sociale!

Formează o echipă de 3-5 persoane și dezvoltă o soluție
tehnologică pentru una din temele:
- Educație accesibilă
- Sănătate mentală
- Mediu și sustenabilitate
- Incluziune socială

Premii: 3000€ în premii + mentorat de la sponsori

Include: mâncare, băuturi, și energie pentru toată noaptea! ☕""",
        "category": "Hackathon",
        "tags": ["Hackathon", "Programare", "Startup", "Voluntariat"],
        "max_seats": 150,
    },
    {
        "title": "Career Fair: IT & Business",
        "description": """Cele mai mari companii tech te așteaptă!

Companii participante:
- Microsoft, Google, Amazon
- Endava, Ness, Cegeka
- Startup-uri locale

Pregătește-ți CV-ul și vino să discuți direct cu recruiterii!

Sfat: Poartă ținută business casual și adu mai multe copii ale CV-ului.""",
        "category": "Career Fair",
        "tags": ["Career", "Networking", "Business"],
        "max_seats": 500,
    },
    {
        "title": "Workshop: Design Thinking",
        "description": """Învață metodologia Design Thinking folosită de
companii precum Apple și IDEO!

Ce vei învăța:
1. Empathize - Înțelege utilizatorii
2. Define - Definește problema
3. Ideate - Generează soluții
4. Prototype - Creează prototipuri
5. Test - Validează soluțiile

Workshop practic cu exerciții în echipă. Vino deschis la idei noi!""",
        "category": "Workshop",
        "tags": ["Design", "Workshop", "Startup"],
        "max_seats": 25,
    },
    {
        "title": "Gaming Night: FIFA & Mario Kart Tournament",
        "description": """O seară relaxantă de gaming competitiv și prietenos!

Turnee:
- FIFA 24 (1v1 bracket)
- Mario Kart (Grand Prix cu 4 jucători)

Premii pentru primii 3 clasificați!

Include: pizza și băuturi răcoritoare

Hai să ne distrăm! 🎮""",
        "category": "Social",
        "tags": ["Gaming", "Social"],
        "max_seats": 40,
    },
    {
        "title": "Seminar: Cum să-ți Începi Startup-ul",
        "description": """De la idee la business - ghid practic pentru
antreprenori!

Speaker: Maria Ionescu, fondatoare TechStart (exit către multinațională)

Agenda:
- Validarea ideii de business
- MVP și product-market fit
- Finanțare: bootstrapping vs investitori
- Legal și administrativ
- Greșeli de evitat

Q&A la final. Pregătește-ți întrebările!""",
        "category": "Seminar",
        "tags": ["Startup", "Business", "Career"],
        "max_seats": 80,
    },
    {
        "title": "Workshop: Introduction to Cloud Computing",
        "description": """Hands-on workshop with AWS and Azure!

Topics covered:
- Cloud fundamentals (IaaS, PaaS, SaaS)
- Setting up your first EC2 instance
- S3 storage and static website hosting
- Basic networking in the cloud
- Cost optimization tips

Prerequisites: Basic Linux knowledge

Free AWS credits for all participants! ☁️""",
        "category": "Workshop",
        "tags": ["Cloud", "DevOps", "Workshop"],
        "max_seats": 35,
    },
    {
        "title": "Networking: Women in Tech Meetup",
        "description": """Un eveniment dedicat femeilor din industria tech!

Program:
- Panel discussion: Cariere de succes în tech
- Speed networking
- Workshop: Negocierea salariului
- Cocktails & conexiuni

Bărbații allies sunt bineveniți! 💪""",
        "category": "Networking",
        "tags": ["Networking", "Career", "Social"],
        "max_seats": 60,
    },
    {
        "title": "Concert: Seară de Jazz Studențesc",
        "description": """Relaxează-te cu muzică jazz live!

Formația "Blue Notes" - studenți din Conservator
Repertoriu: clasici jazz + compoziții proprii

Intrare liberă!

Bar cu băuturi și snacks disponibil.

Dress code: smart casual 🎷""",
        "category": "Music",
        "tags": [MUSIC_TAG, "Jazz", "Social", "Artă"],
        "max_seats": 120,
    },
    {
        "title": "Concert: Rock Night în campus",
        "description": """O seară cu rock live, energie și bună dispoziție!

Line-up:
- Trupa A (alternative rock)
- Trupa B (classic rock covers)

Intrare liberă. Vino devreme pentru locuri bune! 🤘""",
        "category": "Music",
        "tags": [MUSIC_TAG, "Rock", "Social"],
        "max_seats": 200,
    },
    {
        "title": "Festival: Pop & EDM Student Fest",
        "description": """Festival studențesc cu DJ sets și artiști locali.

Genuri: pop, EDM, dance

Acces pe bază de bilet (reducere studenți). 🎧""",
        "category": "Festival",
        "tags": [MUSIC_TAG, "Pop", "EDM", "Social"],
        "max_seats": 800,
    },
    {
        "title": "Curs: Web Development Full Stack",
        "description": """Curs intensiv de 3 săptămâni (serii de weekend)!

Frontend:
- HTML5, CSS3, JavaScript
- React.js framework
- Responsive design

Backend:
- Node.js și Express
- Baze de date SQL și MongoDB
- REST APIs

Proiect final: portfolio personal

Nivel: Intermediar (cunoștințe de bază programare)""",
        "category": "Workshop",
        "tags": ["Web Development", "Programare", "Workshop"],
        "max_seats": 20,
    },
    {
        "title": "Cybersecurity CTF Competition",
        "description": """Capture The Flag - competiție de securitate
cibernetică!

Categorii de challenge-uri:
- Web exploitation
- Cryptography
- Forensics
- Reverse engineering
- Binary exploitation

Solo sau echipe de max 3 persoane.

Premii pentru top 5 echipe! 🏆

Nivel: Toate nivelurile (hints disponibile)""",
        "category": "Hackathon",
        "tags": ["Cybersecurity", "Hackathon", "Programare"],
        "max_seats": 100,
    },
]

# Sample users
STUDENTS = [
    {
        "email": "student@test.com",
        "full_name": "Ion Popescu",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
    },
    {
        "email": "natalia@student.ro",
        "full_name": "Natalia",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
    },
    {
        "email": "andrei@student.ro",
        "full_name": "Andrei",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
    },
    {
        "email": "antonio@student.ro",
        "full_name": "Antonio",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
    },
    {
        "email": "victor@student.ro",
        "full_name": "Victor",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
    },
]

ORGANIZERS = [
    {
        "email": "organizer@test.com",
        "full_name": "Admin Organizator",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
        "org_name": "Liga Studenților IT",
        "org_description": (
            "Comunitatea studenților pasionați de tehnologie. "
            "Organizăm evenimente, workshop-uri și hackathoane pentru a "
            "conecta studenții cu industria IT."
        ),
        "org_website": "https://ligait.ro",
        "org_logo_url": (
            "https://api.dicebear.com/7.x/initials/svg?seed=LSIT&backgroundColor=3b82f6"
        ),
    },
    {
        "email": "career@uni.ro",
        "full_name": "Centrul de Cariere",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
        "org_name": "Centrul de Cariere UNI",
        "org_description": (
            "Conectăm studenții cu angajatorii. Organizăm târguri de "
            "cariere, workshop-uri de dezvoltare profesională și sesiuni "
            "de mentorat."
        ),
        "org_website": "https://cariere.uni.ro",
        "org_logo_url": (
            "https://api.dicebear.com/7.x/initials/svg?seed=CC&backgroundColor=10b981"
        ),
    },
    {
        "email": "sport@uni.ro",
        "full_name": "Clubul Sportiv",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
        "org_name": "Clubul Sportiv Universitar",
        "org_description": (
            "Promovăm sportul și viața sănătoasă în rândul studenților. "
            "Evenimente sportive, competiții și activități outdoor."
        ),
        "org_website": "https://sport.uni.ro",
        "org_logo_url": (
            "https://api.dicebear.com/7.x/initials/svg?seed=CSU&backgroundColor=ef4444"
        ),
    },
]

ADMINS = [
    {
        "email": "admin@test.com",
        "full_name": "EventLink Admin",
        _SECRET_FIELD: _DEFAULT_SEED_CODE,
    },
]


def _clear_existing_data(session) -> None:  # noqa: ANN001
    """Delete existing seed-managed rows before repopulating the database."""
    print("⚠️  Database already has data. Clearing existing data...")
    tables_to_clear = [
        user_interest_tags,
        FavoriteEvent.__table__,
        Registration.__table__,
        event_tags,
        Event.__table__,
        PasswordResetToken.__table__,
        User.__table__,
        Tag.__table__,
    ]
    for table in tables_to_clear:
        try:
            session.execute(table.delete())
        except Exception as exc:
            print(f"⚠️  Skipping clear for {table.name}: {exc}")
    session.commit()
    print("✅ Existing data cleared")


def _create_tags(session):  # noqa: ANN001
    """Create tag rows and return them keyed by tag name."""
    print("📌 Creating tags...")
    tag_objects = {}
    for tag_name in TAGS:
        tag = Tag(name=tag_name)
        session.add(tag)
        tag_objects[tag_name] = tag
    session.flush()
    print(f"   Created {len(TAGS)} tags")
    return tag_objects


def _create_users(
    session,
    user_rows,
    *,
    role: UserRole,
    label: str,
    extra_fields: tuple[str, ...] = (),
):  # noqa: ANN001
    """Create users for one role and return them in insertion order."""
    print(label)
    created_users = []
    for row in user_rows:
        payload = {
            "email": row["email"],
            _PASSWORD_HASH_FIELD: pwd_context.hash(row[_SECRET_FIELD]),
            "role": role,
            "full_name": row["full_name"],
        }
        for field_name in extra_fields:
            payload[field_name] = row.get(field_name)
        user = User(**payload)
        session.add(user)
        created_users.append(user)
    session.flush()
    return created_users


def _assign_student_interest_tags(student_objects, tag_objects: dict[str, Tag]) -> None:
    """Assign a deterministic sample of interest tags to each student."""
    print("🏷️  Assigning interest tags to students...")
    available_tags = list(tag_objects.values())
    for student in student_objects:
        student.interest_tags = _rng.sample(available_tags, _rng.randint(3, 6))


def _build_seed_event(
    event_data: dict[str, object],
    *,
    organizer_id: int,
    now: datetime,
    index: int,
) -> Event:
    """Build one seeded event instance for a specific organizer."""
    is_past_event = index < 3
    if is_past_event:
        start_time = now - timedelta(days=_rng.randint(5, 30), hours=_rng.randint(10, 18))
    else:
        start_time = now + timedelta(days=_rng.randint(3, 60), hours=_rng.randint(10, 18))
    start_time = start_time.replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=_rng.randint(2, 4))
    return Event(
        title=event_data["title"],
        description=event_data["description"],
        category=event_data["category"],
        start_time=start_time,
        end_time=end_time,
        location=_rng.choice(LOCATIONS),
        max_seats=event_data["max_seats"],
        cover_url=_rng.choice(COVER_IMAGES),
        owner_id=organizer_id,
        status="published",
    )


def _create_events(session, organizer_objects):  # noqa: ANN001
    """Create seeded events and return them with their declared tag names."""
    print("📅 Creating events...")
    event_objects = []
    now = datetime.now(timezone.utc)
    for index, event_data in enumerate(SAMPLE_EVENTS):
        organizer = _rng.choice(organizer_objects)
        event = _build_seed_event(event_data, organizer_id=organizer.id, now=now, index=index)
        session.add(event)
        event_objects.append((event, event_data["tags"]))
    session.flush()
    return event_objects, now


def _attach_event_tags(event_objects, tag_objects: dict[str, Tag]) -> None:
    """Attach the declared tag objects to each seeded event."""
    for event, tag_names in event_objects:
        for tag_name in tag_names:
            if tag_name in tag_objects:
                event.tags.append(tag_objects[tag_name])


def _create_registrations(session, event_objects, student_objects, *, now: datetime) -> int:  # noqa: ANN001
    """Create seeded registrations linking students to sample events."""
    print("📝 Creating registrations...")
    registration_count = 0
    for event, _ in event_objects:
        num_registrations = _rng.randint(0, min(len(student_objects), event.max_seats // 2))
        for student in _rng.sample(student_objects, num_registrations):
            registration = Registration(
                user_id=student.id,
                event_id=event.id,
                attended=event.start_time < now and _rng.random() > 0.2,
            )
            session.add(registration)
            registration_count += 1
    session.flush()
    return registration_count


def _create_favorites(session, event_objects, student_objects) -> int:  # noqa: ANN001
    """Create seeded favorite-event rows for sample students."""
    print("❤️  Creating favorites...")
    favorite_count = 0
    created_events = [event for event, _ in event_objects]
    for student in student_objects:
        num_favorites = _rng.randint(2, 5)
        favorite_events = _rng.sample(created_events, min(num_favorites, len(created_events)))
        for event in favorite_events:
            session.add(FavoriteEvent(user_id=student.id, event_id=event.id))
            favorite_count += 1
    session.flush()
    return favorite_count


def _print_seed_summary() -> None:
    """Print the default accounts created by the seed script."""
    print("\n✅ Database seeding completed successfully!")
    print("\n📋 Test accounts:")
    print("   Students:")
    for student in STUDENTS:
        print(f"      - {student['email']}")
    print("   Organizers:")
    for organizer in ORGANIZERS:
        print(f"      - {organizer['email']}")
    print("   Admins:")
    for admin in ADMINS:
        print(f"      - {admin['email']}")
    print("   Passwords are intentionally omitted from logs.")


def seed_database():
    """Seed the database with sample data."""
    print("🌱 Starting database seeding...")

    session = SessionLocal()
    try:
        # Check if data already exists
        user_count = session.scalar(select(func.count()).select_from(User)) or 0

        if user_count > 0:
            _clear_existing_data(session)

        tag_objects = _create_tags(session)
        student_objects = _create_users(
            session,
            STUDENTS,
            role=UserRole.student,
            label="👨‍🎓 Creating students...",
        )
        print(f"   Created {len(STUDENTS)} students")
        _assign_student_interest_tags(student_objects, tag_objects)
        session.flush()

        organizer_objects = _create_users(
            session,
            ORGANIZERS,
            role=UserRole.organizator,
            label="🏢 Creating organizers...",
            extra_fields=(
                "org_name",
                "org_description",
                "org_website",
                "org_logo_url",
            ),
        )
        print(f"   Created {len(ORGANIZERS)} organizers")

        _create_users(session, ADMINS, role=UserRole.admin, label="🛡️ Creating admins...")
        print(f"   Created {len(ADMINS)} admins")

        event_objects, now = _create_events(session, organizer_objects)
        _attach_event_tags(event_objects, tag_objects)
        session.flush()
        print(f"   Created {len(SAMPLE_EVENTS)} events")

        registration_count = _create_registrations(session, event_objects, student_objects, now=now)
        print(f"   Created {registration_count} registrations")

        favorite_count = _create_favorites(session, event_objects, student_objects)
        print(f"   Created {favorite_count} favorites")

        session.commit()

        _print_seed_summary()

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
