"""Practice-sheet generator: a labelled handwriting dataset with ZERO real patient data.

The writer copies each printed line by hand onto a blank sheet, scans it, and
saves the scan next to the matching ground-truth file::

    dataset/
      pagina_001.txt   <- generated here (what was printed)
      pagina_001.jpg   <- the writer's scan of their hand-written copy

All names, document numbers and dates are fake (Faker ``es_CO``), so the dataset
can be shared, used for fine-tuning in the cloud, or published.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

INSTRUCTIONS = (
    "Instrucciones: copie a mano cada línea en una hoja en blanco o de renglones, "
    "una línea por renglón y en el mismo orden. No escriba los números de línea ni el "
    "título. Escriba como lo hace normalmente. Escanee o fotografíe la hoja y guárdela "
    "con el nombre indicado (p. ej. pagina_001.jpg) en la misma carpeta que su archivo .txt."
)

_CIE10 = [
    ("I10", "hipertensión esencial"),
    ("E11.9", "diabetes mellitus tipo 2 sin complicaciones"),
    ("J00", "rinofaringitis aguda"),
    ("K29.7", "gastritis no especificada"),
    ("N39.0", "infección de vías urinarias"),
    ("R51", "cefalea"),
    ("M54.5", "lumbago no especificado"),
    ("J45.9", "asma no especificada"),
    ("E78.5", "hiperlipidemia no especificada"),
    ("A09", "diarrea y gastroenteritis"),
    ("F41.1", "trastorno de ansiedad generalizada"),
    ("E03.9", "hipotiroidismo no especificado"),
]
_DRUGS = [
    ("acetaminofén", "500 mg"),
    ("ibuprofeno", "400 mg"),
    ("losartán", "50 mg"),
    ("metformina", "850 mg"),
    ("amoxicilina", "500 mg"),
    ("omeprazol", "20 mg"),
    ("atorvastatina", "20 mg"),
    ("levotiroxina", "50 mcg"),
    ("loratadina", "10 mg"),
    ("amlodipino", "5 mg"),
    ("naproxeno", "250 mg"),
    ("salbutamol", "100 mcg"),
]
_FREQ = ["cada 8 horas", "cada 12 horas", "cada 24 horas", "cada 6 horas", "en la noche"]
_SENTENCES = [
    "Refiere dolor de {n} días de evolución.",
    "Niega alergias a medicamentos.",
    "Paciente consciente, orientado y alerta.",
    "Se indica control en {n} semanas.",
    "Se solicitan exámenes de laboratorio.",
    "Buena tolerancia a la vía oral.",
    "Se explican signos de alarma.",
    "Abdomen blando, depresible, sin dolor.",
    "Ruidos cardiacos rítmicos sin soplos.",
    "Murmullo vesicular conservado.",
    "Se remite a medicina interna.",
    "Continúa con el mismo tratamiento.",
]


STYLES = ("notes", "form")

# Free-text consultation notes, the way they are usually handwritten: running
# sentences with the common Colombian clinical abbreviations. Grouped by section so
# each page reads like one (fictitious) note: reason → history → exam → dx → plan.
_SYMPTOMS = [
    "dolor abdominal",
    "cefalea",
    "tos seca",
    "fiebre",
    "dolor lumbar",
    "mareo",
    "odinofagia",
    "disuria",
    "dolor torácico",
    "diarrea",
    "malestar general",
    "dolor en rodilla derecha",
]
_HISTORY = ["HTA", "DM2", "hipotiroidismo", "asma", "dislipidemia", "gastritis", "ninguno"]
_LABS = [
    "hemograma y PCR",
    "parcial de orina",
    "glicemia y HbA1c",
    "perfil lipídico",
    "TSH",
    "creatinina y BUN",
    "Rx de tórax",
    "ecografía abdominal",
]
_SPECIALTIES = ["medicina interna", "ortopedia", "ginecología", "pediatría", "nutrición"]
_NOTE_SECTIONS: tuple[tuple[str, ...], ...] = (
    (  # motivo de consulta / enfermedad actual
        "Pte de {age} años consulta por {sym}.",
        "Consulta por {sym} de {n} días de evolución.",
        "Refiere {sym} y {sym2}.",
        "Cuadro de {n} días de {sym}, sin mejoría.",
        "Niega fiebre, vómito u otros síntomas.",
        "Refiere automedicación con {drug} sin mejoría.",
    ),
    (  # antecedentes
        "Antecedentes: {hist}.",
        "En tto con {chronic} {chronic_dose} c/{h}h.",
        "Niega alergias a medicamentos.",
        "Antecedente de {hist} en control.",
    ),
    (  # examen físico
        "SV: TA {sys}/{dia} FC {fc} FR {fr} T° {temp}",
        "Sat O2 {sat}% al ambiente.",
        "Pte alerta, orientado, hidratado, afebril.",
        "Abdomen blando, depresible, no doloroso.",
        "Ruidos cardiacos rítmicos, sin soplos.",
        "Murmullo vesicular conservado, sin agregados.",
        "Faringe eritematosa, sin placas.",
        "Dolor a la palpación en {sym_site}.",
    ),
    (  # diagnóstico
        "Dx: {code} {dx}",
        "Impresión dx: {dx}.",
    ),
    (  # plan
        "Se inicia {drug} {dose} VO c/{h}h por {n} días.",
        "Se solicita: {lab}.",
        "Control en {weeks} semanas con resultados.",
        "Se explican signos de alarma.",
        "Se remite a {spec}.",
        "Se continúa igual tto.",
        "Abundantes líquidos y reposo relativo.",
    ),
)


@dataclass(slots=True)
class PracticeSet:
    pdf: Path
    ground_truth: list[Path]


def _line_factories(rng: random.Random, fake: object) -> list[Callable[[], str]]:
    def rand_date() -> str:
        day = date(1940, 1, 1) + timedelta(days=rng.randint(0, 30_000))
        return day.strftime("%d/%m/%Y")

    def doc() -> str:
        kind = rng.choice(["CC", "CC", "CC", "TI", "CE"])
        digits = (
            rng.randint(10_000_000, 1_099_999_999)
            if kind == "CC"
            else rng.randint(1_000_000, 99_999_999)
        )
        return f"{kind} {digits:,}".replace(",", ".")

    def dx() -> str:
        code, name = rng.choice(_CIE10)
        return f"Diagnóstico: {code} {name}"

    def rx() -> str:
        drug, dose = rng.choice(_DRUGS)
        return f"{drug.capitalize()} {dose} {rng.choice(_FREQ)}"

    return [
        lambda: f"Paciente: {fake.name()}",  # type: ignore[attr-defined]
        doc,
        lambda: f"Fecha de nacimiento: {rand_date()}",
        lambda: f"Fecha de atención: {rand_date()}",
        dx,
        rx,
        lambda: (
            f"TA {rng.randint(95, 170)}/{rng.randint(55, 105)} mmHg FC {rng.randint(55, 120)} lpm"
        ),
        lambda: f"Peso {rng.randint(8, 110)} kg Talla {rng.randint(70, 190)} cm",
        lambda: f"Municipio: {fake.city()}",  # type: ignore[attr-defined]
        lambda: (
            f"Teléfono: 3{rng.randint(0, 2)}{rng.randint(0, 9)} "
            f"{rng.randint(100, 999)} {rng.randint(1000, 9999)}"
        ),
        lambda: rng.choice(_SENTENCES).format(n=rng.randint(2, 15)),
        lambda: rng.choice(_SENTENCES).format(n=rng.randint(2, 15)),
    ]


# Relative share of lines per section (reason, history, exam, dx, plan).
_SECTION_WEIGHTS = (3, 2, 3, 1, 3)


def _note_context(rng: random.Random) -> dict[str, object]:
    """Facts fixed for one note, so a page never contradicts itself."""
    code, dx = rng.choice(_CIE10)
    (drug, dose), (chronic, chronic_dose) = rng.sample(_DRUGS, 2)
    sym, sym2 = rng.sample(_SYMPTOMS, 2)
    return {
        "age": rng.randint(1, 90),
        "sym": sym,
        "sym2": sym2,
        "sym_site": rng.choice(["epigastrio", "flanco derecho", "fosa ilíaca derecha"]),
        "hist": rng.choice(_HISTORY),
        "drug": drug,
        "dose": dose,
        "chronic": chronic,
        "chronic_dose": chronic_dose,
        "code": code,
        "dx": dx,
        "sys": rng.randint(95, 170),
        "dia": rng.randint(55, 105),
        "fc": rng.randint(55, 120),
        "fr": rng.randint(12, 24),
        "temp": f"{rng.uniform(36.0, 39.2):.1f}",
        "sat": rng.randint(88, 99),
    }


def _section_plan(lines_per_page: int) -> list[int]:
    """Section index for each line, in clinical order and proportional to the weights."""
    total = sum(_SECTION_WEIGHTS)
    plan: list[int] = []
    cumulative = 0
    for section, weight in enumerate(_SECTION_WEIGHTS):
        cumulative += weight
        upto = round(lines_per_page * cumulative / total)
        plan.extend([section] * max(0, upto - len(plan)))
    return plan[:lines_per_page]


def _note_page(rng: random.Random, lines_per_page: int) -> list[str]:
    """One fictitious note: sections in clinical order, no line repeated."""
    ctx = _note_context(rng)
    page: list[str] = []
    used: set[str] = set()
    for section in _section_plan(lines_per_page):
        options = _NOTE_SECTIONS[section]
        fresh = [t for t in options if t not in used] or list(options)
        template = rng.choice(fresh)
        used.add(template)
        page.append(
            template.format(
                **ctx,
                n=rng.randint(2, 15),
                weeks=rng.randint(1, 8),
                h=rng.choice([6, 8, 12, 24]),
                lab=rng.choice(_LABS),
                spec=rng.choice(_SPECIALTIES),
            )
        )
    return page


def generate_lines(
    pages: int, lines_per_page: int, seed: int, style: str = "notes"
) -> list[list[str]]:
    """Ground-truth lines per page. ``notes`` = free-text consultation notes,
    ``form`` = field-per-line forms (names, IDs, dates, vitals)."""
    if style not in STYLES:
        raise ValueError(f"Unknown style {style!r}; choose one of {', '.join(STYLES)}")
    rng = random.Random(seed)  # noqa: S311 - not cryptographic, reproducible dataset
    if style == "notes":
        return [_note_page(rng, lines_per_page) for _ in range(pages)]

    from faker import Faker  # noqa: PLC0415 - optional dependency

    fake = Faker("es_CO")
    fake.seed_instance(seed)
    factories = _line_factories(rng, fake)
    return [[rng.choice(factories)() for _ in range(lines_per_page)] for _ in range(pages)]


def generate(
    out_dir: Path,
    pages: int = 10,
    lines_per_page: int = 12,
    seed: int = 7,
    style: str = "notes",
) -> PracticeSet:
    """Write ``practice_sheets.pdf`` and ``pagina_NNN.txt`` ground-truth files."""
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.units import cm  # noqa: PLC0415
    from reportlab.pdfgen import canvas  # noqa: PLC0415

    out_dir.mkdir(parents=True, exist_ok=True)
    content = generate_lines(pages, lines_per_page, seed, style)
    pdf_path = out_dir / "practice_sheets.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    pdf.setTitle("QuillVault practice sheets")
    width, height = A4

    truths: list[Path] = []
    for number, lines in enumerate(content, 1):
        name = f"pagina_{number:03d}"
        truth = out_dir / f"{name}.txt"
        truth.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        truths.append(truth)

        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(2 * cm, height - 2.2 * cm, f"Hoja de práctica {number}/{pages}")
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(width - 2 * cm, height - 2.2 * cm, f"Guardar escaneo como: {name}.jpg")

        text = pdf.beginText(2 * cm, height - 3.2 * cm)
        text.setFont("Helvetica-Oblique", 9)
        words, row = INSTRUCTIONS.split(), ""
        for word in words:
            if pdf.stringWidth(f"{row} {word}", "Helvetica-Oblique", 9) > width - 4 * cm:
                text.textLine(row)
                row = word
            else:
                row = f"{row} {word}".strip()
        text.textLine(row)
        pdf.drawText(text)

        y = height - 5.5 * cm
        for index, line in enumerate(lines, 1):
            pdf.setFont("Helvetica", 9)
            pdf.drawRightString(2.6 * cm, y, f"{index}.")
            pdf.setFont("Helvetica", 14)
            pdf.drawString(3 * cm, y, line)
            y -= 1.6 * cm
        pdf.showPage()
    pdf.save()
    return PracticeSet(pdf=pdf_path, ground_truth=truths)
