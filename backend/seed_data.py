#!/usr/bin/env python3
"""
Seed script for EventLink database.
Creates sample users, events, tags, and registrations for local development.

Usage:
    cd backend
    python seed_data.py
"""

import random
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from sqlalchemy import text
from app.database import SessionLocal
from app.models import User, UserRole, Event, Tag, Registration, FavoriteEvent

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Sample data
TAGS = [
    "Programare", "Design", "Business", "Marketing", "Startup",
    "AI & ML", "Web Development", "Mobile", "Cloud", "DevOps",
    "Data Science", "Cybersecurity", "Gaming", "Blockchain",
    "Career", "Networking", "Workshop", "Hackathon", "Conference",
    "Social", "Sport", "Muzică", "Rock", "Pop", "Hip-Hop", "EDM", "Jazz", "Clasică", "Folk", "Metal",
    "Artă", "Voluntariat"
]

CATEGORIES = [
    "Workshop", "Seminar", "Conference", "Hackathon", "Networking",
    "Career Fair", "Presentation", "Music", "Cultural", "Sports", "Social",
    "Volunteering", "Party", "Festival", "Technical", "Academic"
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
    "Online - Zoom/Teams"
]

COVER_IMAGES = [
    "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1559223607-a43c990c692c?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1505373877841-8d25f7d46678?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1591115765373-5207764f72e7?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1528901166007-3784c7dd3653?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1517048676732-d65bc937f952?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=800&h=400&fit=crop",
    "https://images.unsplash.com/photo-1522158637959-30385a09e0da?w=800&h=400&fit=crop"
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
        "max_seats": 30
    },
    {
        "title": "Tech Talk: Inteligența Artificială în 2024",
        "description": """Descoperă ultimele tendințe în AI și Machine Learning!

Speaker: Dr. Alexandru Popescu, Senior ML Engineer la Google

Topicuri:
- Large Language Models și aplicații
- Computer Vision avansat
- AI Ethics și responsabilitate
- Oportunități de carieră în AI

Nu rata această prezentare fascinantă!""",
        "category": "Presentation",
        "tags": ["AI & ML", "Conference", "Career"],
        "max_seats": 100
    },
    {
        "title": "Hackathon: Build for Good",
        "description": """24 de ore de programare pentru cauze sociale!

Formează o echipă de 3-5 persoane și dezvoltă o soluție tehnologică pentru una din temele:
- Educație accesibilă
- Sănătate mentală
- Mediu și sustenabilitate
- Incluziune socială

Premii: 3000€ în premii + mentorat de la sponsori

Include: mâncare, băuturi, și energie pentru toată noaptea! ☕""",
        "category": "Hackathon",
        "tags": ["Hackathon", "Programare", "Startup", "Voluntariat"],
        "max_seats": 150
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
        "max_seats": 500
    },
    {
        "title": "Workshop: Design Thinking",
        "description": """Învață metodologia Design Thinking folosită de companii precum Apple și IDEO!

Ce vei învăța:
1. Empathize - Înțelege utilizatorii
2. Define - Definește problema
3. Ideate - Generează soluții
4. Prototype - Creează prototipuri
5. Test - Validează soluțiile

Workshop practic cu exerciții în echipă. Vino deschis la idei noi!""",
        "category": "Workshop",
        "tags": ["Design", "Workshop", "Startup"],
        "max_seats": 25
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
        "max_seats": 40
    },
    {
        "title": "Seminar: Cum să-ți Începi Startup-ul",
        "description": """De la idee la business - ghid practic pentru antreprenori!

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
        "max_seats": 80
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
        "max_seats": 35
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
        "max_seats": 60
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
        "tags": ["Muzică", "Jazz", "Social", "Artă"],
        "max_seats": 120
    },
    {
        "title": "Concert: Rock Night în campus",
        "description": """O seară cu rock live, energie și bună dispoziție!

Line-up:
- Trupa A (alternative rock)
- Trupa B (classic rock covers)

Intrare liberă. Vino devreme pentru locuri bune! 🤘""",
        "category": "Music",
        "tags": ["Muzică", "Rock", "Social"],
        "max_seats": 200
    },
    {
        "title": "Festival: Pop & EDM Student Fest",
        "description": """Festival studențesc cu DJ sets și artiști locali.

Genuri: pop, EDM, dance

Acces pe bază de bilet (reducere studenți). 🎧""",
        "category": "Festival",
        "tags": ["Muzică", "Pop", "EDM", "Social"],
        "max_seats": 800
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
        "max_seats": 20
    },
    {
        "title": "Cybersecurity CTF Competition",
        "description": """Capture The Flag - competiție de securitate cibernetică!

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
        "max_seats": 100
    }
]

# Sample users
STUDENTS = [
    {"email": "student@test.com", "full_name": "Ion Popescu", "password": "test123"},
    {"email": "natalia@student.ro", "full_name": "Natalia", "password": "test123"},
    {"email": "andrei@student.ro", "full_name": "Andrei", "password": "test123"},
    {"email": "antonio@student.ro", "full_name": "Antonio", "password": "test123"},
    {"email": "victor@student.ro", "full_name": "Victor", "password": "test123"},
]

ORGANIZERS = [
    {
        "email": "organizer@test.com",
        "full_name": "Admin Organizator",
        "password": "test123",
        "org_name": "Liga Studenților IT",
        "org_description": "Comunitatea studenților pasionați de tehnologie. Organizăm evenimente, workshop-uri și hackathoane pentru a conecta studenții cu industria IT.",
        "org_website": "https://ligait.ro",
        "org_logo_url": "https://api.dicebear.com/7.x/initials/svg?seed=LSIT&backgroundColor=3b82f6"
    },
    {
        "email": "career@uni.ro",
        "full_name": "Centrul de Cariere",
        "password": "test123",
        "org_name": "Centrul de Cariere UNI",
        "org_description": "Conectăm studenții cu angajatorii. Organizăm târguri de cariere, workshop-uri de dezvoltare profesională și sesiuni de mentorat.",
        "org_website": "https://cariere.uni.ro",
        "org_logo_url": "https://api.dicebear.com/7.x/initials/svg?seed=CC&backgroundColor=10b981"
    },
    {
        "email": "sport@uni.ro",
        "full_name": "Clubul Sportiv",
        "password": "test123",
        "org_name": "Clubul Sportiv Universitar",
        "org_description": "Promovăm sportul și viața sănătoasă în rândul studenților. Evenimente sportive, competiții și activități outdoor.",
        "org_website": "https://sport.uni.ro",
        "org_logo_url": "https://api.dicebear.com/7.x/initials/svg?seed=CSU&backgroundColor=ef4444"
    }
]

ADMINS = [
    {"email": "admin@test.com", "full_name": "EventLink Admin", "password": "test123"},
]


def seed_database():
    """Seed the database with sample data."""
    print("🌱 Starting database seeding...")
    
    session = SessionLocal()
    try:
        # Check if data already exists
        result = session.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        
        if user_count > 0:
            print("⚠️  Database already has data. Clearing existing data...")
            # Clear existing data in correct order (respecting foreign keys)
            # Use try/except for tables that might not exist
            tables_to_clear = [
                "user_interest_tags",
                "favorite_events", 
                "registrations",
                "event_tags",
                "events",
                "password_reset_tokens",
                "users",
                "tags",
            ]
            for table in tables_to_clear:
                try:
                    session.execute(text(f"DELETE FROM {table}"))
                except Exception:
                    pass  # Table might not exist
            session.commit()
            print("✅ Existing data cleared")
        
        # Create tags
        print("📌 Creating tags...")
        tag_objects = {}
        for tag_name in TAGS:
            tag = Tag(name=tag_name)
            session.add(tag)
            tag_objects[tag_name] = tag
        session.flush()
        print(f"   Created {len(TAGS)} tags")
        
        # Create students
        print("👨‍🎓 Creating students...")
        student_objects = []
        for student_data in STUDENTS:
            student = User(
                email=student_data["email"],
                password_hash=pwd_context.hash(student_data["password"]),
                role=UserRole.student,
                full_name=student_data["full_name"]
            )
            session.add(student)
            student_objects.append(student)
        session.flush()
        print(f"   Created {len(STUDENTS)} students")
        
        # Assign interest tags to students
        print("🏷️  Assigning interest tags to students...")
        for student in student_objects:
            # Each student gets 3-6 random interest tags
            num_tags = random.randint(3, 6)
            selected_tags = random.sample(list(tag_objects.values()), num_tags)
            student.interest_tags = selected_tags
        session.flush()
        
        # Create organizers
        print("🏢 Creating organizers...")
        organizer_objects = []
        for org_data in ORGANIZERS:
            organizer = User(
                email=org_data["email"],
                password_hash=pwd_context.hash(org_data["password"]),
                role=UserRole.organizator,
                full_name=org_data["full_name"],
                org_name=org_data["org_name"],
                org_description=org_data["org_description"],
                org_website=org_data.get("org_website"),
                org_logo_url=org_data.get("org_logo_url")
            )
            session.add(organizer)
            organizer_objects.append(organizer)
        session.flush()
        print(f"   Created {len(ORGANIZERS)} organizers")

        # Create admins
        print("🛡️ Creating admins...")
        admin_objects = []
        for admin_data in ADMINS:
            admin = User(
                email=admin_data["email"],
                password_hash=pwd_context.hash(admin_data["password"]),
                role=UserRole.admin,
                full_name=admin_data["full_name"],
            )
            session.add(admin)
            admin_objects.append(admin)
        session.flush()
        print(f"   Created {len(ADMINS)} admins")
        
        # Create events
        print("📅 Creating events...")
        event_objects = []
        now = datetime.now(timezone.utc)
        
        for i, event_data in enumerate(SAMPLE_EVENTS):
            # Distribute events across time: some past, some upcoming
            if i < 3:
                # Past events (last 30 days)
                days_ago = random.randint(5, 30)
                start_time = now - timedelta(days=days_ago, hours=random.randint(10, 18))
            else:
                # Future events (next 60 days)
                days_ahead = random.randint(3, 60)
                start_time = now + timedelta(days=days_ahead, hours=random.randint(10, 18))
                
            # Round to nearest hour
            start_time = start_time.replace(minute=0, second=0, microsecond=0)
            
            # Event duration: 2-4 hours
            duration_hours = random.randint(2, 4)
            end_time = start_time + timedelta(hours=duration_hours)
            
            # Random organizer
            organizer = random.choice(organizer_objects)
            
            event = Event(
                title=event_data["title"],
                description=event_data["description"],
                category=event_data["category"],
                start_time=start_time,
                end_time=end_time,
                location=random.choice(LOCATIONS),
                max_seats=event_data["max_seats"],
                cover_url=random.choice(COVER_IMAGES),
                owner_id=organizer.id,
                status="published"
            )
            session.add(event)
            event_objects.append((event, event_data["tags"]))
        
        session.flush()
        
        # Assign tags to events
        for event, tag_names in event_objects:
            for tag_name in tag_names:
                if tag_name in tag_objects:
                    event.tags.append(tag_objects[tag_name])
        
        session.flush()
        print(f"   Created {len(SAMPLE_EVENTS)} events")
        
        # Create registrations
        print("📝 Creating registrations...")
        registration_count = 0
        for event, _ in event_objects:
            # Random students register for events
            num_registrations = random.randint(0, min(len(student_objects), event.max_seats // 2))
            registered_students = random.sample(student_objects, num_registrations)
            
            for student in registered_students:
                is_past = event.start_time < now
                registration = Registration(
                    user_id=student.id,
                    event_id=event.id,
                    attended=is_past and random.random() > 0.2  # 80% attendance for past events
                )
                session.add(registration)
                registration_count += 1
        
        session.flush()
        print(f"   Created {registration_count} registrations")
        
        # Create favorites
        print("❤️  Creating favorites...")
        favorite_count = 0
        for student in student_objects:
            # Each student favorites 2-5 random events
            num_favorites = random.randint(2, 5)
            favorite_events = random.sample([e for e, _ in event_objects], min(num_favorites, len(event_objects)))
            
            for event in favorite_events:
                favorite = FavoriteEvent(
                    user_id=student.id,
                    event_id=event.id
                )
                session.add(favorite)
                favorite_count += 1
        
        session.flush()
        print(f"   Created {favorite_count} favorites")
        
        session.commit()
        
        print("\n✅ Database seeding completed successfully!")
        print("\n📋 Test accounts:")
        print("   Students:")
        for s in STUDENTS:
            print(f"      - {s['email']} / {s['password']}")
        print("   Organizers:")
        for o in ORGANIZERS:
            print(f"      - {o['email']} / {o['password']}")
        print("   Admins:")
        for a in ADMINS:
            print(f"      - {a['email']} / {a['password']}")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
