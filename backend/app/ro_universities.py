from __future__ import annotations

from typing import TypedDict


class UniversityCatalogItem(TypedDict, total=False):
    name: str
    city: str | None
    faculties: list[str]


def _guess_city(name: str) -> str | None:
    lowered = name.lower()
    mapping = [
        ("bucharest", "București"),
        ("bucuresti", "București"),
        ("cluj-napoca", "Cluj-Napoca"),
        ("cluj", "Cluj-Napoca"),
        ("iasi", "Iași"),
        ("timisoara", "Timișoara"),
        ("targu mures", "Târgu Mureș"),
        ("targu-mures", "Târgu Mureș"),
        ("sibiu", "Sibiu"),
        ("constanta", "Constanța"),
        ("craiova", "Craiova"),
        ("galatzi", "Galați"),
        ("brasov", "Brașov"),
        ("oradea", "Oradea"),
        ("suceava", "Suceava"),
        ("petrosani", "Petroșani"),
        ("pitesti", "Pitești"),
        ("arad", "Arad"),
        ("ploiesti", "Ploiești"),
        ("targu jiu", "Târgu Jiu"),
        ("targoviste", "Târgoviște"),
        ("alba iulia", "Alba Iulia"),
        ("baia mare", "Baia Mare"),
        ("resita", "Reșița"),
        ("bacau", "Bacău"),
    ]
    for needle, city in mapping:
        if needle in lowered:
            return city
    return None


# Note: Faculty lists are provided for a small subset of universities and can be expanded over time.
_FACULTIES_BY_UNIVERSITY: dict[str, list[str]] = {
    "University of Bucharest": [
        "Facultatea de Matematică și Informatică",
        "Facultatea de Drept",
        "Facultatea de Litere",
        "Facultatea de Psihologie și Științele Educației",
        "Facultatea de Geografie",
        "Facultatea de Istorie",
        "Facultatea de Sociologie și Asistență Socială",
        "Facultatea de Filosofie",
        "Facultatea de Limbi și Literaturi Străine",
        "Facultatea de Administrație și Afaceri",
        "Facultatea de Jurnalism și Științele Comunicării",
        "Facultatea de Chimie",
        "Facultatea de Fizică",
        "Facultatea de Biologie",
        "Facultatea de Geologie și Geofizică",
        "Facultatea de Științe Politice",
    ],
    "University Politehnica of Bucharest": [
        "Facultatea de Automatică și Calculatoare",
        "Facultatea de Electronică, Telecomunicații și Tehnologia Informației",
        "Facultatea de Inginerie Electrică",
        "Facultatea de Energetică",
        "Facultatea de Transporturi",
        "Facultatea de Inginerie Mecanică și Mecatronică",
        "Facultatea de Inginerie Industrială și Robotică",
        "Facultatea de Inginerie Chimică și Biotehnologii",
        "Facultatea de Ingineria Sistemelor Biotehnice",
        "Facultatea de Științe Aplicate",
    ],
    "Babes-Bolyai University of Cluj-Napoca": [
        "Facultatea de Matematică și Informatică",
        "Facultatea de Fizică",
        "Facultatea de Chimie și Inginerie Chimică",
        "Facultatea de Biologie și Geologie",
        "Facultatea de Drept",
        "Facultatea de Științe Economice și Gestiunea Afacerilor",
        "Facultatea de Litere",
        "Facultatea de Istorie și Filosofie",
        "Facultatea de Psihologie și Științe ale Educației",
        "Facultatea de Geografie",
        "Facultatea de Științe Politice, Administrative și ale Comunicării",
    ],
    "University of Iasi": [
        "Facultatea de Informatică",
        "Facultatea de Matematică",
        "Facultatea de Fizică",
        "Facultatea de Chimie",
        "Facultatea de Biologie",
        "Facultatea de Geografie și Geologie",
        "Facultatea de Drept",
        "Facultatea de Litere",
        "Facultatea de Istorie",
        "Facultatea de Filosofie și Științe Social-Politice",
        "Facultatea de Economie și Administrarea Afacerilor",
    ],
    "West University of Timisoara": [
        "Facultatea de Matematică și Informatică",
        "Facultatea de Fizică",
        "Facultatea de Chimie, Biologie, Geografie",
        "Facultatea de Drept",
        "Facultatea de Economie și de Administrare a Afacerilor",
        "Facultatea de Litere, Istorie și Teologie",
        "Facultatea de Sociologie și Psihologie",
        "Facultatea de Arte și Design",
        "Facultatea de Muzică și Teatru",
        "Facultatea de Științe Politice, Filosofie și Științe ale Comunicării",
    ],
}


def get_university_catalog() -> list[UniversityCatalogItem]:
    names = [
        "1 December University of Alba Iulia",
        "AISTEDA",
        "Academia Tehnica Militara",
        "Academia de Studii Economice din Bucuresti",
        'Academy of Arts "George Enescu" Iasi',
        'Academy of Music "Georghe Dima" Cluj-Napoca',
        "Babes-Bolyai University of Cluj-Napoca",
        "Constantin Brancoveanu University Pitesti",
        "Emanuel University",
        'Institute of Architecture "Ion Mincu" Bucharest',
        "Maritime University Constanta",
        "National Academy for Physical Education and Sports Bucharest",
        "National School of Political and Administrative Studies Bucharest",
        "National University of Arts",
        "National University of Music",
        "National University of Theater and Film Arts",
        "North University of Baia Mare",
        "Oradea University",
        "Petru Maior University of Targu Mures",
        "Polytechnic University of Timisoara",
        "Romanian-American University",
        "Spiru Haret University",
        "Targu-Mures University of Theatre",
        "Technical University of Civil Engineering Bucharest",
        "Technical University of Cluj-Napoca",
        "Technical University of Iasi",
        "Technical University of Timisoara",
        'Universitatea de Vest "Vasile Goldiş"',
        'University "Aurel Vlaicu" Arad',
        'University "Petre Andrei" Iasi',
        'University "Titu Maiorescu"',
        'University "Transilvany" of Brasov',
        "University Lucian Blaga of Sibiu",
        "University Oil- Gas Ploiesti",
        "University Politehnica of Bucharest",
        "University of Agriculture and Veterinary Medicine Bucharest",
        "University of Agriculture and Veterinary Medicine Cluj-Napoca",
        "University of Agriculture and Veterinary Medicine Iasi",
        "University of Agriculture and Veterinary Medicine Timisoara",
        "University of Art and Design Cluj-Napoca",
        "University of Bacau",
        "University of Bucharest",
        "University of Constanta",
        "University of Constanta Medical School",
        "University of Craiova",
        "University of Galatzi",
        "University of Iasi",
        "University of Medicine and Pharmacology of Oradea",
        "University of Medicine and Pharmacy of Bucharest",
        "University of Medicine and Pharmacy of Cluj-Napoca",
        "University of Medicine and Pharmacy of Iasi",
        "University of Medicine and Pharmacy of Targu Mures",
        "University of Medicine and Pharmacy of Timisoara",
        "University of Oradea",
        "University of Petrosani",
        "University of Pitesti",
        "University of Resita",
        "University of Sibiu",
        "University of Suceava",
        "University of Targu Jiu",
        "Valahia University of Targoviste",
        "West University of Timisoara",
    ]

    items: list[UniversityCatalogItem] = []
    for name in names:
        items.append(
            {
                "name": name,
                "city": _guess_city(name),
                "faculties": _FACULTIES_BY_UNIVERSITY.get(name, []),
            }
        )
    return items
