from __future__ import annotations

import re
import unicodedata
from typing import TypedDict


class UniversityCatalogItem(TypedDict, total=False):
    name: str
    city: str | None
    faculties: list[str]
    aliases: list[str]


def _normalize_university_key(value: str) -> str:
    # Normalize casing + diacritics + punctuation/whitespace so we can match legacy inputs.
    value = value.strip().casefold()
    value = (
        value.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _guess_city(name: str) -> str | None:
    lowered = name.lower()
    mapping = [
        ("romanian-american", _CITY_BUCURESTI),
        ("spiru haret", _CITY_BUCURESTI),
        ("bucharest", _CITY_BUCURESTI),
        ("bucuresti", _CITY_BUCURESTI),
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
        ("emanuel", "Oradea"),
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


# Note: Faculty lists are curated and incomplete; if a university is missing from this map, the UI
# falls back to manual input for the faculty field.
_UNIVERSITY_OIL_GAS_PLOIESTI = "University Oil-Gas Ploiesti"
_CITY_BUCURESTI = "București"
_FACULTY_STIINTE_ECONOMICE = "Facultatea de Științe Economice"
_FACULTY_DREPT = "Facultatea de Drept"
_FACULTY_MANAGEMENT = "Facultatea de Management"
_FACULTY_TEOLOGIE = "Facultatea de Teologie"
_FACULTY_PSIHOLOGIE_SI_STIINTELE_EDUCATIEI = "Facultatea de Psihologie și Științele Educației"
_FACULTY_TEOLOGIE_ORTODOXA = "Facultatea de Teologie Ortodoxă"
_FACULTY_MATEMATICA_SI_INFORMATICA = "Facultatea de Matematică și Informatică"
_FACULTY_FIZICA = "Facultatea de Fizică"
_FACULTY_LITERE = "Facultatea de Litere"
_FACULTY_EDUCATIE_FIZICA_SI_SPORT = "Facultatea de Educație Fizică și Sport"
_FACULTY_INGINERIE = "Facultatea de Inginerie"
_FACULTY_STIINTE = "Facultatea de Științe"
_FACULTY_ARTE = "Facultatea de Arte"
_FACULTY_MEDICINA_SI_FARMACIE = "Facultatea de Medicină și Farmacie"
_FACULTY_STIINTE_SOCIO_UMANE = "Facultatea de Științe Socio-Umane"
_FACULTY_ARHITECTURA_SI_URBANISM = "Facultatea de Arhitectură și Urbanism"
_FACULTY_AUTOMATICA_SI_CALCULATOARE = "Facultatea de Automatică și Calculatoare"
_FACULTY_CONSTRUCTII = "Facultatea de Construcții"
_FACULTY_HIDROTEHNICA = "Facultatea de Hidrotehnică"
_FACULTY_MECANICA = "Facultatea de Mecanică"
_FACULTY_ELECTRONICA_TELECOMUNICATII_SI_TEHNOLOGIA_INFORMATIEI = "Facultatea de Electronică, Telecomunicații și Tehnologia Informației"
_FACULTY_INGINERIE_ELECTRICA = "Facultatea de Inginerie Electrică"
_FACULTY_STIINTA_SI_INGINERIA_MATERIALELOR = "Facultatea de Știința și Ingineria Materialelor"
_FACULTY_MEDICINA = "Facultatea de Medicină"
_FACULTY_FARMACIE = "Facultatea de Farmacie"
_FACULTY_MEDICINA_DENTARA = "Facultatea de Medicină Dentară"
_FACULTY_AGRICULTURA = "Facultatea de Agricultură"
_FACULTY_HORTICULTURA = "Facultatea de Horticultură"
_FACULTY_MEDICINA_VETERINARA = "Facultatea de Medicină Veterinară"
_FACULTY_DREPT_SI_STIINTE_ADMINISTRATIVE = "Facultatea de Drept și Științe Administrative"
_FACULTY_ECONOMIE_SI_ADMINISTRAREA_AFACERILOR = "Facultatea de Economie și Administrarea Afacerilor"

_FACULTIES_BY_UNIVERSITY: dict[str, list[str]] = {
    "1 December University of Alba Iulia": [
        "Facultatea de Istorie, Litere și Științe ale Educației",
        "Facultatea de Drept și Științe Sociale",
        "Facultatea de Informatică și Inginerie",
        _FACULTY_STIINTE_ECONOMICE,
        _FACULTY_TEOLOGIE_ORTODOXA,
    ],
    "Academia Tehnica Militara": [
        "Facultatea de Comunicații și Sisteme Electronice pentru Apărare și Securitate",
        "Facultatea de Sisteme Informatice și Securitate Cibernetică",
        "Facultatea de Sisteme Integrate de Armament, Geniu și Mecatronică",
        "Facultatea de Aeronave și Autovehicule Militare",
    ],
    "Academia de Studii Economice din Bucuresti": [
        "Facultatea de Administrarea Afacerilor cu predare în limbi străine",
        "Facultatea de Administrație și Management Public",
        "Facultatea de Business și Turism",
        "Facultatea de Cibernetică, Statistică și Informatică Economică",
        "Facultatea de Contabilitate și Informatică de Gestiune",
        _FACULTY_DREPT,
        "Facultatea de Economie Agroalimentară și a Mediului",
        "Facultatea de Economie Teoretică și Aplicată",
        "Facultatea de Finanțe, Asigurări, Bănci și Burse de Valori",
        _FACULTY_MANAGEMENT,
        "Facultatea de Marketing",
        "Facultatea de Relații Economice Internaționale",
    ],
    "Academy of Arts \"George Enescu\" Iasi": [
        "Facultatea de Interpretare, Compoziție și Studii Muzicale Teoretice",
        "Facultatea de Teatru",
        "Facultatea de Arte Vizuale și Design",
    ],
    "Academy of Music \"Georghe Dima\" Cluj-Napoca": [
        "Facultatea de Interpretare Muzicală",
        "Facultatea Teoretică",
    ],
    "Babes-Bolyai University of Cluj-Napoca": [
        _FACULTY_MATEMATICA_SI_INFORMATICA,
        _FACULTY_FIZICA,
        "Facultatea de Chimie și Inginerie Chimică",
        "Facultatea de Biologie și Geologie",
        "Facultatea de Business",
        "Facultatea de Geografie",
        "Facultatea de Știința și Ingineria Mediului",
        _FACULTY_DREPT,
        _FACULTY_LITERE,
        "Facultatea de Istorie și Filosofie",
        "Facultatea de Sociologie și Asistență Socială",
        "Facultatea de Psihologie și Științe ale Educației",
        "Facultatea de Științe Economice și Gestiunea Afacerilor",
        "Facultatea de Studii Europene",
        "Facultatea de Științe Politice, Administrative și ale Comunicării",
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        _FACULTY_TEOLOGIE_ORTODOXA,
        "Facultatea de Teologie Greco-Catolică",
        "Facultatea de Teologie Reformată",
        "Facultatea de Teologie Romano-Catolică",
        "Facultatea de Teatru și Televiziune",
        _FACULTY_INGINERIE,
    ],
    "Constantin Brancoveanu University Pitesti": [
        "Facultatea de Management Marketing în Afaceri Economice",
        "Facultatea de Finanțe Contabilitate",
        "Facultatea de Științe Juridice, Administrative și ale Comunicării",
    ],
    "Emanuel University": [
        _FACULTY_TEOLOGIE,
        _FACULTY_MANAGEMENT,
    ],
    "Institute of Architecture \"Ion Mincu\" Bucharest": [
        "Facultatea de Arhitectură",
        "Facultatea de Urbanism",
        "Facultatea de Arhitectură de Interior",
    ],
    "Maritime University Constanta": [
        "Facultatea de Navigație și Transport Naval",
        "Facultatea de Electromecanică Navală",
    ],
    "National Academy for Physical Education and Sports Bucharest": [
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        "Facultatea de Kinetoterapie",
    ],
    "National School of Political and Administrative Studies Bucharest": [
        "Facultatea de Administrație Publică",
        "Facultatea de Comunicare și Relații Publice",
        _FACULTY_MANAGEMENT,
        "Facultatea de Științe Politice",
    ],
    "National University of Arts": [
        "Facultatea de Arte Plastice",
        "Facultatea de Arte Decorative și Design",
        "Facultatea de Istoria și Teoria Artei",
    ],
    "National University of Music": [
        "Facultatea de Compoziție, Muzicologie și Pedagogie muzicală",
        "Facultatea de Interpretare Muzicală",
    ],
    "National University of Theater and Film Arts": [
        "Facultatea de Teatru",
        "Facultatea de Film",
    ],
    "North University of Baia Mare": [
        _FACULTY_INGINERIE,
        _FACULTY_LITERE,
        _FACULTY_STIINTE,
    ],
    "Oradea University": [
        _FACULTY_ARTE,
        "Facultatea de Construcții, Cadastru și Arhitectură",
        _FACULTY_DREPT,
        "Facultatea de Geografie, Turism și Sport",
        "Facultatea de Inginerie Electrică și Tehnologia Informației",
        "Facultatea de Inginerie Energetică și Management Industrial",
        "Facultatea de Inginerie Managerială și Tehnologică",
        "Facultatea de Istorie, Relații Internaționale, Științe Politice și Științele Comunicării",
        _FACULTY_LITERE,
        _FACULTY_MEDICINA_SI_FARMACIE,
        "Facultatea de Protecția Mediului",
        "Facultatea de Informatică și Științe",
        _FACULTY_STIINTE_ECONOMICE,
        _FACULTY_STIINTE_SOCIO_UMANE,
        "Facultatea de Teologie Ortodoxă „Episcop Dr. Vasile Coman”",
    ],
    "Petru Maior University of Targu Mures": [
        _FACULTY_INGINERIE,
        "Facultatea de Științe și Litere",
        "Facultatea de Științe Economice, Juridice și Administrative",
    ],
    "Polytechnic University of Timisoara": [
        _FACULTY_ARHITECTURA_SI_URBANISM,
        _FACULTY_AUTOMATICA_SI_CALCULATOARE,
        "Facultatea de Chimie Industrială și Ingineria Mediului",
        _FACULTY_CONSTRUCTII,
        _FACULTY_HIDROTEHNICA,
        "Facultatea de Electronică, Telecomunicații și Tehnologii Informaționale",
        "Facultatea de Inginerie Electrică și Energetică",
        "Facultatea de Management în Producție și Transporturi",
        _FACULTY_MECANICA,
        "Facultatea de Inginerie din Hunedoara",
        "Facultatea de Științe ale Comunicării",
    ],
    "Romanian-American University": [
        "Facultatea de Afaceri Internaționale",
        _FACULTY_DREPT,
        "Facultatea de Educație Fizică, Sport și Kinetoterapie",
        "Facultatea de Finanțe și Contabilitate",
        "Facultatea de Informatică Managerială",
        "Facultatea de Management-Marketing",
        _FACULTY_PSIHOLOGIE_SI_STIINTELE_EDUCATIEI,
        "Facultatea de Turism și Managementul Ospitalității",
    ],
    "Spiru Haret University": [
        "Facultatea de Arhitectură (București)",
        "Facultatea de Arte (București)",
        "Facultatea de Științe Juridice și Administrative (Brașov)",
        "Facultatea de Științe Juridice, Politice și Administrative (București)",
        "Facultatea de Contabilitate și Finanțe (Râmnicu Vâlcea)",
        "Facultatea de Drept și Administrație Publică (Constanța)",
        "Facultatea de Drept și Administrație Publică (Craiova)",
        "Facultatea de Drept și Administrație Publică (Râmnicu Vâlcea)",
        "Facultatea de Științe Economice (Câmpulung-Muscel)",
        "Facultatea de Educație Fizică și Sport (București)",
        "Facultatea de Psihologie și Științele Educației (București)",
        "Facultatea de Finanțe și Bănci (București)",
        "Facultatea de Jurnalism și Științele Comunicării (București)",
        "Facultatea de Litere (București)",
        "Facultatea de Management (Brașov)",
        "Facultatea de Management Financiar Contabil (București)",
        "Facultatea de Management Financiar Contabil (Craiova)",
        "Facultatea de Management Financiar Contabil (Constanța)",
        "Facultatea de Marketing și Afaceri Economice Internaționale (București)",
        "Facultatea de Matematică, Informatică și Științele Naturii (București)",
        "Facultatea de Medicină Veterinară (București)",
        "Facultatea de Psihologie și Pedagogie (Brașov)",
        "Facultatea de Relații Internaționale, Istorie și Filosofie (București)",
    ],
    "Targu-Mures University of Theatre": [
        "Facultatea de Arte în Limba Română",
    ],
    "Technical University of Civil Engineering Bucharest": [
        "Facultatea de Construcții Civile, Industriale și Agricole",
        "Facultatea de Inginerie a Instalațiilor",
        _FACULTY_HIDROTEHNICA,
        "Facultatea de Căi Ferate, Drumuri și Poduri",
        "Facultatea de Geodezie",
        "Facultatea de Inginerie în Limbi Străine",
        "Facultatea de Utilaj Tehnologic",
    ],
    "Technical University of Cluj-Napoca": [
        _FACULTY_AUTOMATICA_SI_CALCULATOARE,
        _FACULTY_ELECTRONICA_TELECOMUNICATII_SI_TEHNOLOGIA_INFORMATIEI,
        _FACULTY_INGINERIE_ELECTRICA,
        _FACULTY_CONSTRUCTII,
        "Facultatea de Instalații",
        "Facultatea de Construcții de Mașini",
        "Facultatea de Inginerie Industrială, Robotică și Managementul Producției",
        _FACULTY_MECANICA,
        "Facultatea de Autovehicule Rutiere, Mecatronică și Mecanică",
        _FACULTY_STIINTA_SI_INGINERIA_MATERIALELOR,
        "Facultatea de Ingineria Materialelor și a Mediului",
        _FACULTY_ARHITECTURA_SI_URBANISM,
        _FACULTY_INGINERIE,
        _FACULTY_LITERE,
        _FACULTY_STIINTE,
    ],
    "Technical University of Iasi": [
        "Facultatea de Arhitectură „G. M. Cantacuzino”",
        _FACULTY_AUTOMATICA_SI_CALCULATOARE,
        "Facultatea de Construcții și Instalații",
        "Facultatea de Construcții de Mașini și Management Industrial",
        "Facultatea de Design Industrial și Managementul Afacerilor",
        _FACULTY_ELECTRONICA_TELECOMUNICATII_SI_TEHNOLOGIA_INFORMATIEI,
        "Facultatea de Hidrotehnică, Geodezie și Ingineria Mediului",
        "Facultatea de Inginerie Chimică și Protecția Mediului „Cristofor Simionescu”",
        "Facultatea de Inginerie Electrică, Energetică și Informatică Aplicată",
        _FACULTY_MECANICA,
        _FACULTY_STIINTA_SI_INGINERIA_MATERIALELOR,
    ],
    "Technical University of Timisoara": [
        _FACULTY_ARHITECTURA_SI_URBANISM,
        _FACULTY_AUTOMATICA_SI_CALCULATOARE,
        "Facultatea de Chimie Industrială și Ingineria Mediului",
        _FACULTY_CONSTRUCTII,
        _FACULTY_HIDROTEHNICA,
        "Facultatea de Electronică, Telecomunicații și Tehnologii Informaționale",
        "Facultatea de Inginerie Electrică și Energetică",
        "Facultatea de Management în Producție și Transporturi",
        _FACULTY_MECANICA,
        "Facultatea de Inginerie din Hunedoara",
        "Facultatea de Științe ale Comunicării",
    ],
    "Universitatea de Vest \"Vasile Goldiş\"": [
        _FACULTY_MEDICINA,
        _FACULTY_FARMACIE,
        _FACULTY_MEDICINA_DENTARA,
        "Facultatea de Științe Economice, Inginerie și Informatică",
        "Facultatea de Științe Juridice",
        "Facultatea de Științe Socio-Umane, Educației Fizice și Sport",
    ],
    "University \"Aurel Vlaicu\" Arad": [
        _FACULTY_STIINTE_ECONOMICE,
        "Facultatea de Științe Exacte",
        "Facultatea de Științe Umaniste și Sociale",
        "Facultatea de Științe ale Educației, Psihologie și Asistență Socială",
        "Facultatea de Teologie Ortodoxă „Ilarion V. Felea”",
        _FACULTY_INGINERIE,
        "Facultatea de Inginerie Alimentară, Turism și Protecția Mediului",
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        "Facultatea de Design",
    ],
    "University \"Petre Andrei\" Iasi": [
        _FACULTY_PSIHOLOGIE_SI_STIINTELE_EDUCATIEI,
        "Facultatea de Asistență Socială și Sociologie",
        "Facultatea de Științe Politice și Administrative",
        _FACULTY_DREPT,
        "Facultatea de Economie",
    ],
    "University \"Titu Maiorescu\"": [
        _FACULTY_DREPT,
        "Facultatea de Psihologie",
        "Facultatea de Informatică",
        _FACULTY_STIINTE_ECONOMICE,
        _FACULTY_MEDICINA,
        _FACULTY_MEDICINA_DENTARA,
        _FACULTY_FARMACIE,
        "Facultatea de Științele Educației, Comunicare și Relații Internaționale",
        "Facultatea de Asistență Medicală",
    ],
    "University \"Transilvania\" of Brasov": [
        "Facultatea de Inginerie Tehnologică și Management Industrial",
        _FACULTY_STIINTA_SI_INGINERIA_MATERIALELOR,
        "Facultatea de Design de Produs și Mediu",
        "Facultatea de Inginerie Electrică și Știința Calculatoarelor",
        "Facultatea de Silvicultură și Exploatări Forestiere",
        "Facultatea de Ingineria Lemnului",
        _FACULTY_CONSTRUCTII,
        "Facultatea de Științe Economice și Administrarea Afacerilor",
        "Facultatea de Alimentație și Turism",
        _FACULTY_MATEMATICA_SI_INFORMATICA,
        "Facultatea de Muzică",
        _FACULTY_MEDICINA,
        _FACULTY_DREPT,
        "Facultatea de Sociologie și Comunicare",
        "Facultatea de Educație Fizică și Sporturi Montane",
        _FACULTY_LITERE,
        _FACULTY_PSIHOLOGIE_SI_STIINTELE_EDUCATIEI,
    ],
    "University Lucian Blaga of Sibiu": [
        _FACULTY_TEOLOGIE,
        "Facultatea de Drept „Simion Bărnuțiu”",
        "Facultatea de Litere și Arte",
        _FACULTY_STIINTE_SOCIO_UMANE,
        _FACULTY_INGINERIE,
        _FACULTY_MEDICINA,
        _FACULTY_STIINTE,
        "Facultatea de Științe Agricole, Industrie Alimentară și Protecția Mediului",
        _FACULTY_STIINTE_ECONOMICE,
    ],
    _UNIVERSITY_OIL_GAS_PLOIESTI: [
        "Facultatea de Inginerie Mecanică și Electrică",
        "Facultatea de Ingineria Petrolului și Gazelor",
        "Facultatea de Tehnologia Petrolului și Petrochimie",
        "Facultatea de Litere și Științe",
        _FACULTY_STIINTE_ECONOMICE,
    ],
    "University Politehnica of Bucharest": [
        _FACULTY_AUTOMATICA_SI_CALCULATOARE,
        "Facultatea de Antreprenoriat, Ingineria și Managementul Afacerilor",
        "Facultatea de Chimie Aplicată și Știința Materialelor",
        "Facultatea de Energetică",
        _FACULTY_ELECTRONICA_TELECOMUNICATII_SI_TEHNOLOGIA_INFORMATIEI,
        "Facultatea de Ingineria și Managementul Sistemelor Tehnologice",
        "Facultatea de Ingineria Sistemelor Biotehnice",
        "Facultatea de Inginerie Aerospațială",
        _FACULTY_INGINERIE_ELECTRICA,
        "Facultatea de Inginerie Medicală",
        "Facultatea de Inginerie Mecanică și Mecatronică",
        "Facultatea de Inginerie cu predare în limbi străine",
        "Facultatea de Transporturi",
        _FACULTY_STIINTA_SI_INGINERIA_MATERIALELOR,
        "Facultatea de Științe Aplicate",
    ],
    "University of Agriculture and Veterinary Medicine Bucharest": [
        _FACULTY_AGRICULTURA,
        _FACULTY_HORTICULTURA,
        "Facultatea de Ingineria și Gestiunea Producțiilor Animaliere",
        _FACULTY_MEDICINA_VETERINARA,
        "Facultatea de Biotehnologii",
        "Facultatea de Îmbunătățiri Funciare și Ingineria Mediului",
        "Facultatea de Management și Dezvoltare Rurală",
    ],
    "University of Agriculture and Veterinary Medicine Cluj-Napoca": [
        _FACULTY_AGRICULTURA,
        _FACULTY_HORTICULTURA,
        "Facultatea de Zootehnie și Biotehnologii",
        _FACULTY_MEDICINA_VETERINARA,
        "Facultatea de Știința și Tehnologia Alimentelor",
        "Facultatea de Silvicultură și Cadastru",
    ],
    "University of Agriculture and Veterinary Medicine Iasi": [
        _FACULTY_AGRICULTURA,
        _FACULTY_HORTICULTURA,
        "Facultatea de Ingineria Resurselor Animale și Alimentare",
        _FACULTY_MEDICINA_VETERINARA,
    ],
    "University of Agriculture and Veterinary Medicine Timisoara": [
        _FACULTY_AGRICULTURA,
        "Facultatea de Bioingineria Resurselor Animaliere",
        "Facultatea de Inginerie Alimentară",
        "Facultatea de Inginerie și Tehnologii Aplicate",
        "Facultatea de Management și Turism Rural",
        _FACULTY_MEDICINA_VETERINARA,
    ],
    "University of Art and Design Cluj-Napoca": [
        "Facultatea de Arte Plastice",
        "Facultatea de Arte Decorative și Design",
    ],
    "University of Bacau": [
        _FACULTY_STIINTE,
        _FACULTY_INGINERIE,
        _FACULTY_STIINTE_ECONOMICE,
        _FACULTY_LITERE,
        "Facultatea de Științe ale Mișcării, Sportului și Sănătății",
    ],
    "University of Bucharest": [
        "Facultatea de Administrație și Afaceri",
        "Facultatea de Biologie",
        "Facultatea de Chimie",
        _FACULTY_DREPT,
        "Facultatea de Filosofie",
        _FACULTY_FIZICA,
        "Facultatea de Geografie",
        "Facultatea de Geologie și Geofizică",
        "Facultatea de Istorie",
        "Facultatea de Jurnalism și Științele Comunicării",
        "Facultatea de Limbi și Literaturi Străine",
        _FACULTY_LITERE,
        _FACULTY_MATEMATICA_SI_INFORMATICA,
        _FACULTY_PSIHOLOGIE_SI_STIINTELE_EDUCATIEI,
        "Facultatea de Sociologie și Asistență Socială",
        "Facultatea de Studii Interdisciplinare",
        "Facultatea de Științe Politice",
        "Facultatea de Teologie Baptistă",
        _FACULTY_TEOLOGIE_ORTODOXA,
        "Facultatea de Teologie Romano-Catolică și Asistență Socială",
    ],
    "University of Constanta": [
        "Facultatea de Istorie și Științe Politice",
        _FACULTY_FARMACIE,
        _FACULTY_MEDICINA,
        _FACULTY_PSIHOLOGIE_SI_STIINTELE_EDUCATIEI,
        _FACULTY_LITERE,
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        _FACULTY_TEOLOGIE,
        _FACULTY_MATEMATICA_SI_INFORMATICA,
        "Facultatea de Științe Aplicate și Inginerie",
        _FACULTY_ARTE,
        "Facultatea de Științe ale Naturii și Științe Agricole",
        _FACULTY_DREPT_SI_STIINTE_ADMINISTRATIVE,
        _FACULTY_CONSTRUCTII,
        "Facultatea de Inginerie Mecanică, Industrială și Maritimă",
    ],
    "University of Constanta Medical School": [
        _FACULTY_FARMACIE,
        _FACULTY_MEDICINA,
    ],
    "University of Craiova": [
        "Facultatea de Agronomie",
        "Facultatea de Automatică, Calculatoare și Electronică",
        _FACULTY_DREPT,
        _FACULTY_ECONOMIE_SI_ADMINISTRAREA_AFACERILOR,
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        _FACULTY_HORTICULTURA,
        _FACULTY_INGINERIE_ELECTRICA,
        _FACULTY_LITERE,
        _FACULTY_MECANICA,
        _FACULTY_TEOLOGIE_ORTODOXA,
        _FACULTY_STIINTE,
        "Facultatea de Științe Sociale",
    ],
    "University of Galatzi": [
        _FACULTY_INGINERIE,
        "Facultatea de Arhitectură Navală",
        "Facultatea de Știința și Ingineria Alimentelor",
        "Facultatea de Automatică, Calculatoare, Inginerie Electrică și Electronică",
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        _FACULTY_LITERE,
        "Facultatea de Științe și Mediu",
        "Facultatea de Istorie, Filosofie și Teologie",
        "Facultatea de Inginerie și Agronomie din Brăila",
        _FACULTY_ECONOMIE_SI_ADMINISTRAREA_AFACERILOR,
        _FACULTY_DREPT_SI_STIINTE_ADMINISTRATIVE,
        _FACULTY_MEDICINA_SI_FARMACIE,
        _FACULTY_ARTE,
        "Facultatea Transfrontalieră",
    ],
    "University of Iasi": [
        "Facultatea de Biologie",
        "Facultatea de Chimie",
        _FACULTY_DREPT,
        _FACULTY_ECONOMIE_SI_ADMINISTRAREA_AFACERILOR,
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        "Facultatea de Filosofie și Științe Social-Politice",
        _FACULTY_FIZICA,
        "Facultatea de Geografie și Geologie",
        "Facultatea de Informatică",
        "Facultatea de Istorie",
        _FACULTY_LITERE,
        "Facultatea de Matematică",
        "Facultatea de Psihologie și Științe ale Educației",
        _FACULTY_TEOLOGIE_ORTODOXA,
        "Facultatea de Teologie Romano-Catolică",
    ],
    "University of Medicine and Pharmacology of Oradea": [
        _FACULTY_MEDICINA_SI_FARMACIE,
    ],
    "University of Medicine and Pharmacy of Bucharest": [
        _FACULTY_MEDICINA,
        _FACULTY_MEDICINA_DENTARA,
        _FACULTY_FARMACIE,
        "Facultatea de Moașe și Asistență Medicală",
    ],
    "University of Medicine and Pharmacy of Cluj-Napoca": [
        _FACULTY_MEDICINA,
        _FACULTY_MEDICINA_DENTARA,
        _FACULTY_FARMACIE,
    ],
    "University of Medicine and Pharmacy of Iasi": [
        _FACULTY_MEDICINA,
        _FACULTY_MEDICINA_DENTARA,
        _FACULTY_FARMACIE,
        "Facultatea de Bioinginerie Medicală",
    ],
    "University of Medicine and Pharmacy of Targu Mures": [
        _FACULTY_MEDICINA,
        _FACULTY_MEDICINA_DENTARA,
        "Facultatea de Medicină Engleză",
        _FACULTY_FARMACIE,
        "Facultatea de Inginerie și Tehnologia Informației",
        "Facultatea de Științe și Litere",
        "Facultatea de Economie și Drept",
    ],
    "University of Medicine and Pharmacy of Timisoara": [
        _FACULTY_MEDICINA,
        _FACULTY_MEDICINA_DENTARA,
        _FACULTY_FARMACIE,
    ],
    "University of Oradea": [
        _FACULTY_ARTE,
        "Facultatea de Construcții, Cadastru și Arhitectură",
        _FACULTY_DREPT,
        "Facultatea de Geografie, Turism și Sport",
        "Facultatea de Inginerie Electrică și Tehnologia Informației",
        "Facultatea de Inginerie Energetică și Management Industrial",
        "Facultatea de Inginerie Managerială și Tehnologică",
        "Facultatea de Istorie, Relații Internaționale, Științe Politice și Științele Comunicării",
        _FACULTY_LITERE,
        _FACULTY_MEDICINA_SI_FARMACIE,
        "Facultatea de Protecția Mediului",
        "Facultatea de Informatică și Științe",
        _FACULTY_STIINTE_ECONOMICE,
        _FACULTY_STIINTE_SOCIO_UMANE,
        "Facultatea de Teologie Ortodoxă „Episcop Dr. Vasile Coman”",
    ],
    "University of Petrosani": [
        "Facultatea de Mine",
        "Facultatea de Inginerie Mecanică și Electrică",
        "Facultatea de Științe Economice, Administrative și Sociale",
    ],
    "University of Pitesti": [
        "Facultatea de Științe, Educație Fizică și Informatică",
        "Facultatea de Mecanică și Tehnologie",
        "Facultatea de Electronică, Comunicații și Calculatoare",
        "Facultatea de Științe Economice și Drept",
        "Facultatea de Științe ale Educației",
        "Facultatea de Teologie, Litere, Istorie, Arte",
    ],
    "University of Sibiu": [
        _FACULTY_TEOLOGIE,
        "Facultatea de Drept „Simion Bărnuțiu”",
        "Facultatea de Litere și Arte",
        _FACULTY_STIINTE_SOCIO_UMANE,
        _FACULTY_INGINERIE,
        _FACULTY_MEDICINA,
        _FACULTY_STIINTE,
        "Facultatea de Științe Agricole, Industrie Alimentară și Protecția Mediului",
        _FACULTY_STIINTE_ECONOMICE,
    ],
    "University of Suceava": [
        _FACULTY_DREPT_SI_STIINTE_ADMINISTRATIVE,
        "Facultatea de Economie, Administrație și Afaceri",
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        "Facultatea de Inginerie Alimentară",
        "Facultatea de Inginerie Electrică și Știința Calculatoarelor",
        "Facultatea de Inginerie Mecanică, Autovehicule și Robotică",
        "Facultatea de Istorie, Geografie și Științe Sociale",
        "Facultatea de Litere și Științe ale Comunicării",
        "Facultatea de Medicină și Științe Biologice",
        "Facultatea de Științe ale Educației",
        "Facultatea de Silvicultură",
    ],
    "University of Targu Jiu": [
        "Facultatea de Inginerie și Dezvoltare Durabilă",
        "Facultatea de Științe ale Educației și Management Public",
        "Facultatea de Științe Juridice",
        _FACULTY_STIINTE_ECONOMICE,
        "Facultatea de Științe Medicale și Comportamentale",
    ],
    "Valahia University of Targoviste": [
        _FACULTY_STIINTE_ECONOMICE,
        _FACULTY_DREPT_SI_STIINTE_ADMINISTRATIVE,
        "Facultatea de Inginerie Electrică, Electronică și Tehnologia Informației",
        "Facultatea de Științe și Arte",
        "Facultatea de Ingineria Mediului și Știința Alimentelor",
        "Facultatea de Ingineria Materialelor și Mecanică",
        "Facultatea de Teologie Ortodoxă și Științele Educației",
        "Facultatea de Științe Umaniste",
        "Facultatea de Științe Politice, Litere și Comunicare",
        "Facultatea de Științe și Inginerie Alexandria",
    ],
    "West University of Timisoara": [
        "Facultatea de Arte și Design",
        "Facultatea de Chimie, Biologie, Geografie",
        _FACULTY_DREPT,
        "Facultatea de Economie și de Administrare a Afacerilor",
        _FACULTY_EDUCATIE_FIZICA_SI_SPORT,
        _FACULTY_FIZICA,
        "Facultatea de Litere, Istorie și Teologie",
        _FACULTY_MATEMATICA_SI_INFORMATICA,
        "Facultatea de Muzică și Teatru",
        "Facultatea de Sociologie și Psihologie",
        "Facultatea de Științe Politice, Filosofie și Științe ale Comunicării",
    ],
}

_UNIVERSITY_NAMES = [
    "1 December University of Alba Iulia",
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
    'University "Transilvania" of Brasov',
    "University Lucian Blaga of Sibiu",
    _UNIVERSITY_OIL_GAS_PLOIESTI,
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
    "University of Sibiu",
    "University of Suceava",
    "University of Targu Jiu",
    "Valahia University of Targoviste",
    "West University of Timisoara",
]

_UNIVERSITY_ALIASES: dict[str, list[str]] = {
    'University "Transilvania" of Brasov': ['University "Transilvany" of Brasov'],
    _UNIVERSITY_OIL_GAS_PLOIESTI: ["University Oil- Gas Ploiesti"],
}

_UNIVERSITY_KEY_TO_CANONICAL: dict[str, str] = {}
for canonical in _UNIVERSITY_NAMES:
    _UNIVERSITY_KEY_TO_CANONICAL[_normalize_university_key(canonical)] = canonical
for canonical, aliases in _UNIVERSITY_ALIASES.items():
    for alias in aliases:
        _UNIVERSITY_KEY_TO_CANONICAL[_normalize_university_key(alias)] = canonical


def normalize_university_name(name: str | None) -> str | None:
    if name is None:
        return None
    trimmed = name.strip()
    if not trimmed:
        return None
    canonical = _UNIVERSITY_KEY_TO_CANONICAL.get(_normalize_university_key(trimmed))
    return canonical or trimmed


def get_university_catalog() -> list[UniversityCatalogItem]:
    items: list[UniversityCatalogItem] = []
    for name in _UNIVERSITY_NAMES:
        items.append(
            {
                "name": name,
                "city": _guess_city(name),
                "faculties": _FACULTIES_BY_UNIVERSITY.get(name, []),
                "aliases": _UNIVERSITY_ALIASES.get(name, []),
            }
        )
    return items
