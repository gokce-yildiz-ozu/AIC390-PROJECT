"""D-008: generate the bulk corpus (fictional courses) into data/corpus_bulk/, reproducibly from a seed.

Syllabi (some with a revised version) and course announcements, assembled from a hand-reviewed pool of section
texts with randomized values. Offline: no model and no API call. Rules from D-008 and docs/data_inventory.md §1:
never a core course code, no dormitory, tuition or fee content, no calendar-wide dates (make-up week, withdrawal),
no regulation article numbers, so no generated text competes with a fact the test sets depend on.

    python scripts/generate_bulk_corpus.py                 # default seed and size, about 11,000+ chunks
    python scripts/generate_bulk_corpus.py --courses 20 --out /tmp/bulk   # small run
"""

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aic390.rag.chunking import build_chunks  # noqa: E402

DEFAULT_SEED = 20261122
DEFAULT_COURSES = 900
CORE_CODES = {"CS-301", "CS-310", "CS-130", "MATH-212", "MATH-221", "ECON-101", "AIC-390"}
FORBIDDEN_WORDS = ("dorm", "tuition", "fee", "yurt", "harç", "ücret", "curv")

DEPARTMENTS = {
    "CS": (
        "Computer Science",
        [
            "Data Structures",
            "Computer Networks",
            "Databases",
            "Compilers",
            "Machine Learning",
            "Computer Graphics",
            "Software Engineering",
            "Distributed Systems",
            "Security",
        ],
    ),
    "MATH": (
        "Mathematics",
        [
            "Calculus",
            "Discrete Mathematics",
            "Probability",
            "Real Analysis",
            "Numerical Methods",
            "Differential Equations",
            "Abstract Algebra",
            "Topology",
        ],
    ),
    "ECON": (
        "Economics",
        [
            "Microeconomics",
            "Macroeconomics",
            "Econometrics",
            "Game Theory",
            "Labor Economics",
            "International Trade",
            "Public Economics",
        ],
    ),
    "EE": (
        "Electrical Engineering",
        [
            "Circuit Theory",
            "Signals and Systems",
            "Electromagnetics",
            "Control Systems",
            "Digital Design",
            "Power Systems",
        ],
    ),
    "ME": (
        "Mechanical Engineering",
        ["Statics", "Thermodynamics", "Fluid Mechanics", "Machine Design", "Heat Transfer", "Engineering Drawing"],
    ),
    "IE": (
        "Industrial Engineering",
        ["Operations Research", "Production Planning", "Quality Control", "Supply Chain Management", "Simulation"],
    ),
    "PHYS": ("Physics", ["General Physics", "Modern Physics", "Optics", "Quantum Mechanics", "Statistical Physics"]),
    "CHEM": ("Chemistry", ["General Chemistry", "Organic Chemistry", "Physical Chemistry", "Analytical Chemistry"]),
    "BUS": ("Business", ["Principles of Management", "Organizational Behavior", "Business Ethics", "Strategy"]),
    "FIN": ("Finance", ["Corporate Finance", "Investments", "Financial Markets", "Risk Management"]),
    "MKT": ("Marketing", ["Principles of Marketing", "Consumer Behavior", "Digital Marketing", "Marketing Research"]),
    "PSY": (
        "Psychology",
        ["Introduction to Psychology", "Cognitive Psychology", "Social Psychology", "Research Methods"],
    ),
    "STAT": ("Statistics", ["Statistical Inference", "Regression Analysis", "Time Series", "Bayesian Statistics"]),
    "ARCH": ("Architecture", ["Architectural Design Studio", "History of Architecture", "Building Technology"]),
    "LAW": ("Law", ["Introduction to Law", "Contract Law", "Constitutional Law", "Commercial Law"]),
    "IR": (
        "International Relations",
        ["Introduction to International Relations", "Foreign Policy Analysis", "International Organizations"],
    ),
    "PHIL": ("Philosophy", ["Introduction to Philosophy", "Logic", "Ethics", "Philosophy of Mind"]),
    "HIST": ("History", ["World History", "History of Science", "Ottoman History", "Modern Europe"]),
    "CE": ("Civil Engineering", ["Structural Analysis", "Soil Mechanics", "Hydraulics", "Transportation Engineering"]),
    "AE": ("Aerospace Engineering", ["Aerodynamics", "Flight Mechanics", "Propulsion"]),
}
FIRST_NAMES = [
    "Ahmet",
    "Zeynep",
    "Mehmet",
    "Elif",
    "Can",
    "Deniz",
    "Burak",
    "Selin",
    "Emre",
    "Ece",
    "Kerem",
    "Defne",
    "Oğuz",
    "Nil",
    "Tolga",
    "Pınar",
    "Barış",
    "İpek",
    "Kaan",
    "Derya",
    "Umut",
    "Gizem",
    "Serkan",
    "Aslı",
]
LAST_NAMES = [
    "Yılmaz",
    "Kaya",
    "Demir",
    "Şahin",
    "Çelik",
    "Arslan",
    "Doğan",
    "Kılıç",
    "Aslan",
    "Öztürk",
    "Aydın",
    "Özdemir",
    "Koç",
    "Kurt",
    "Polat",
    "Erdem",
    "Güneş",
    "Tekin",
    "Bulut",
    "Korkmaz",
    "Akın",
    "Ünal",
]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
SLOTS = ["08:40–10:30", "09:40–11:30", "10:40–12:30", "12:40–14:30", "13:40–15:30", "15:40–17:30", "16:40–18:30"]
MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTHS_TR = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]
TERM_START = date(2026, 9, 21)
TERM_END = date(2027, 1, 8)
ITEMS_EN = ["Homework", "Lab", "Problem Set", "Project milestone", "Quiz", "Essay", "Case study"]
# Turkish case suffixes after a percentage ("%10'u", "%60'ına"), so the Turkish text reads naturally.
PCT_ACC = {5: "i", 10: "u", 15: "i", 20: "si", 25: "i"}
PCT_DAT = {60: "ına", 70: "ine", 75: "ine", 80: "ine"}
ITEMS_TR = ["Ödev", "Lab", "Problem seti", "Proje aşaması", "Quiz", "Deneme", "Vaka çalışması"]


def fmt_date(d: date, lang: str) -> str:
    months = MONTHS_EN if lang == "en" else MONTHS_TR
    return f"{d.day} {months[d.month - 1]} {d.year}"


def term_date(rng: random.Random, start: date = TERM_START, end: date = TERM_END) -> date:
    return start + timedelta(days=rng.randrange((end - start).days))


def make_codes(rng: random.Random, n: int) -> list[tuple[str, str, str]]:
    """Unique (code, department, course name); core codes are excluded by construction."""
    candidates = []
    for prefix, (dept, names) in DEPARTMENTS.items():
        for number in range(100, 500):
            code = f"{prefix}-{number}"
            if code not in CORE_CODES:
                candidates.append((code, dept, names))
    rng.shuffle(candidates)
    if n > len(candidates):
        raise ValueError(f"at most {len(candidates)} courses")
    return [(code, dept, rng.choice(names)) for code, dept, names in candidates[:n]]


def schedule_lines(rng: random.Random, lang: str, items: list[tuple[str, date]]) -> str:
    if lang == "en":
        lines = [f"{name} is due on {fmt_date(due, lang)} at 23:59." for name, due in items]
        return "Submissions are uploaded to the LMS. " + " ".join(lines)
    lines = [f"{name} için son teslim tarihi {fmt_date(due, lang)}, saat 23:59." for name, due in items]
    return "Teslimler LMS üzerinden yapılır. " + " ".join(lines)


def syllabus_sections(rng: random.Random, course: dict, lang: str, items: list[tuple[str, date]]) -> list[tuple]:
    """Section (heading, text) pairs; values come from `course` so v1 and v2 differ only where intended."""
    c = course
    en = lang == "en"
    sections = []
    if en:
        sections.append(
            (
                "Course information",
                rng.choice(
                    [
                        f"Instructor: {c['instructor']}. Lectures on {c['day1']} and {c['day2']}, {c['slot']}. "
                        f"This course is offered by the Department of {c['dept']}.",
                        f"{c['name']} is taught by {c['instructor']} ({c['dept']}). "
                        f"Lectures: {c['day1']} and {c['day2']}, "
                        f"{c['slot']}.",
                    ]
                ),
            )
        )
        sections.append(
            (
                "Grading",
                f"Assignments {c['w_hw']}%, midterm exam {c['w_mid']}%, final exam {100 - c['w_hw'] - c['w_mid']}%.",
            )
        )
        sections.append(("Schedule", schedule_lines(rng, lang, items)))
        if c["late_days"] == 0:
            late = "Late submissions are not accepted; work submitted after the deadline receives 0."
        else:
            late = (
                f"Late submissions lose {c['late_pct']}% of their grade for each day they are late, for at most "
                f"{c['late_days']} days. A submission more than {c['late_days']} days late receives 0."
            )
        sections.append(("Late policy", late))
        if c["attendance"] is not None:
            sections.append(
                (
                    "Attendance",
                    rng.choice(
                        [
                            f"Attendance is mandatory: students must attend at least {c['attendance']}% "
                            "of the lectures.",
                            f"Students who attend less than {c['attendance']}% of the sessions "
                            "cannot take the final exam.",
                        ]
                    ),
                )
            )
        sections.append(
            (
                "Office hours",
                f"{c['instructor']} holds office hours on {c['oh_day']}, {c['oh_slot']}, "
                "or by appointment through the LMS.",
            )
        )
        sections.append(
            (
                "Academic integrity",
                rng.choice(
                    [
                        "All submitted work must be your own. Copying from other students or from online sources "
                        "is reported "
                        "to the disciplinary committee.",
                        "Collaboration on ideas is allowed, but every student writes and submits their own solutions. "
                        "Plagiarism results in a grade of 0 for the assignment.",
                    ]
                ),
            )
        )
        sections.append(
            (
                "Course materials",
                rng.choice(
                    [
                        "Lecture slides and readings are posted on the LMS each week.",
                        "There is no required textbook; the lecture notes on the LMS cover the course.",
                    ]
                ),
            )
        )
    else:
        sections.append(
            (
                "Ders bilgileri",
                f"Öğretim üyesi: {c['instructor']}. Dersler {c['day1_tr']} ve "
                f"{c['day2_tr']}, {c['slot']}. Ders {c['dept']} bölümü tarafından verilir.",
            )
        )
        sections.append(
            (
                "Değerlendirme",
                f"Ödevler %{c['w_hw']}, ara sınav %{c['w_mid']}, final sınavı %{100 - c['w_hw'] - c['w_mid']}.",
            )
        )
        sections.append(("Takvim", schedule_lines(rng, lang, items)))
        if c["late_days"] == 0:
            late = "Geç teslim kabul edilmez; son tarihten sonra yapılan teslim 0 alır."
        else:
            late = (
                f"Geç teslimlerde her gün için notun %{c['late_pct']}'{PCT_ACC[c['late_pct']]} düşülür, "
                f"en fazla {c['late_days']} gün. "
                f"{c['late_days']} günden fazla geciken teslim 0 alır."
            )
        sections.append(("Geç teslim", late))
        if c["attendance"] is not None:
            sections.append(
                (
                    "Devam",
                    f"Derslere devam zorunludur: öğrenciler derslerin "
                    f"en az %{c['attendance']}'{PCT_DAT[c['attendance']]} katılmalıdır.",
                )
            )
        sections.append(
            (
                "Görüşme saatleri",
                f"{c['instructor']}, {c['oh_day_tr']} {c['oh_slot']} saatlerinde ofisinde öğrencilerle görüşür.",
            )
        )
        sections.append(
            (
                "Akademik dürüstlük",
                "Teslim edilen her çalışma öğrencinin kendisine ait olmalıdır. Kopya disiplin kuruluna bildirilir.",
            )
        )
    return sections


def announcement(rng: random.Random, course: dict, lang: str, items: list[tuple[str, date]], n: int) -> dict:
    name, due = rng.choice(items)
    posted = max(TERM_START, due - timedelta(days=rng.randint(3, 14)))
    kind = rng.choice(["posted", "extended", "room", "office", "reminder"])
    en = lang == "en"
    if kind == "posted":
        text = (
            f"{name} is now available on the LMS. Please submit it by {fmt_date(due, lang)} at 23:59."
            if en
            else f"{name} LMS'te yayınlandı. Lütfen {fmt_date(due, lang)} saat 23:59'a kadar teslim edin."
        )
    elif kind == "extended":
        days = rng.choice([2, 3, 7])
        text = (
            f"The deadline for {name} is extended by {days} days."
            if en
            else f"{name} için teslim süresi {days} gün uzatılmıştır."
        )
    elif kind == "room":
        text = (
            f"From next week on, the {course['day1']} lecture meets in room {rng.randint(101, 499)}."
            if en
            else f"Önümüzdeki haftadan itibaren {course['day1_tr']} dersi {rng.randint(101, 499)} numaralı "
            "sınıfta yapılacak."
        )
    elif kind == "office":
        text = (
            f"Office hours this week move to {rng.choice(DAYS_EN)}, {rng.choice(SLOTS)}."
            if en
            else f"Bu haftaki görüşme saati {rng.choice(DAYS_TR)} {rng.choice(SLOTS)} olarak değişti."
        )
    else:
        text = (
            f"Reminder: {name} is due on {fmt_date(due, lang)} at 23:59. Late submissions follow the syllabus."
            if en
            else f"Hatırlatma: {name} {fmt_date(due, lang)} saat 23:59'da teslim edilmelidir."
        )
    heading = "Announcement" if en else "Duyuru"
    title = f"{course['code']} announcement {n}" if en else f"{course['code']} duyuru {n}"
    return {
        "suffix": f"announcement-{n}",
        "title": title,
        "doc_type": "announcement",
        "version": 1,
        "valid_from": posted.isoformat(),
        "audience": f"enrolled:{course['code']}",
        "lang": lang,
        "sections": [(heading, f"{text} {course['instructor']}")],
    }


def course_profile(rng: random.Random, code: str, dept: str, name: str) -> dict:
    d1, d2 = sorted(rng.sample(range(5), 2))
    oh = rng.randrange(5)
    w_hw = rng.choice([20, 25, 30, 35, 40])
    late_days = rng.choice([0, 1, 2, 3, 3, 4, 5])
    return {
        "code": code,
        "dept": dept,
        "name": name,
        "instructor": f"Dr. {rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
        "day1": DAYS_EN[d1],
        "day2": DAYS_EN[d2],
        "day1_tr": DAYS_TR[d1],
        "day2_tr": DAYS_TR[d2],
        "slot": rng.choice(SLOTS),
        "oh_day": DAYS_EN[oh],
        "oh_day_tr": DAYS_TR[oh],
        "oh_slot": rng.choice(SLOTS),
        "w_hw": w_hw,
        "w_mid": rng.choice([20, 25, 30]),
        "late_pct": rng.choice([5, 10, 15, 20, 25]),
        "late_days": late_days,
        "attendance": rng.choice([None, None, 60, 70, 75, 80]),
    }


def course_documents(rng: random.Random, code: str, dept: str, name: str, turkish_share: float) -> list[dict]:
    course = course_profile(rng, code, dept, name)
    lang = "tr" if rng.random() < turkish_share else "en"
    labels = ITEMS_EN if lang == "en" else ITEMS_TR
    picks = rng.sample(labels, 3)
    items = sorted(
        ((f"{label} {rng.randint(1, 5)}", term_date(rng, TERM_START + timedelta(days=21))) for label in picks),
        key=lambda item: item[1],
    )
    title = f"{code} {name}, " + ("Syllabus, Fall 2026" if lang == "en" else "Ders İzlencesi, Güz 2026")
    docs = []
    # One sub-seed for both versions: v2 repeats v1's wording and differs only in the moved due date.
    wording_seed = rng.getrandbits(32)
    revised = rng.random() < 0.3
    v1 = {
        "suffix": "syllabus-v1" if revised else "syllabus",
        "title": title,
        "doc_type": "syllabus",
        "version": 1,
        "valid_from": TERM_START.isoformat(),
        "audience": "all",
        "lang": lang,
        "sections": syllabus_sections(random.Random(wording_seed), course, lang, items),
    }
    docs.append(v1)
    if revised:
        changed = rng.randrange(len(items))
        name_changed, due = items[changed]
        new_items = list(items)
        new_items[changed] = (name_changed, due + timedelta(days=rng.choice([7, 14])))
        valid_from = max(TERM_START + timedelta(days=14), due - timedelta(days=rng.randint(7, 20)))
        docs.append(
            {
                "suffix": "syllabus-v2",
                "title": title.replace(", Syllabus", ", Syllabus (version 2)"),
                "doc_type": "syllabus",
                "version": 2,
                "valid_from": valid_from.isoformat(),
                "audience": "all",
                "lang": lang,
                "sections": syllabus_sections(random.Random(wording_seed), course, lang, new_items),
            }
        )
    for n in range(1, rng.randint(2, 4) + 1):
        docs.append(announcement(rng, course, lang, items, n))
    for doc in docs:
        doc["course"] = code
    return docs


def render(doc: dict, seed: int) -> tuple[str, str]:
    doc_id = f"{doc['course'].replace('-', '').lower()}-{doc['suffix']}"
    front = {
        "doc_id": doc_id,
        "title": doc["title"],
        "course": doc["course"],
        "doc_type": doc["doc_type"],
        "version": doc["version"],
        "valid_from": doc["valid_from"],
        "language": doc["lang"],
        "audience": doc["audience"],
        "source": f"synthetic, scripts/generate_bulk_corpus.py seed {seed}",
        "reviewed": False,
    }
    lines = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items()] + ["---", ""]
    lines += [f"# {doc['title']}", ""]
    for heading, text in doc["sections"]:
        lines += [f"## {heading}", "", text, ""]
    return doc_id, "\n".join(lines)


def generate(seed: int, courses: int, turkish_share: float = 0.2) -> dict[str, str]:
    """doc_id -> Markdown text. Same seed and arguments, same output."""
    rng = random.Random(seed)
    out: dict[str, str] = {}
    for code, dept, name in make_codes(rng, courses):
        for doc in course_documents(rng, code, dept, name, turkish_share):
            doc_id, text = render(doc, seed)
            out[doc_id] = text
    return out


def check(documents: dict[str, str]) -> None:
    for doc_id, text in documents.items():
        lower = text.lower()
        for code in CORE_CODES:
            if code.lower() in lower or code.replace("-", "").lower() in lower:
                raise ValueError(f"{doc_id}: core course code {code}")
        for word in FORBIDDEN_WORDS:
            if word in lower:
                raise ValueError(f"{doc_id}: forbidden word {word!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--courses", type=int, default=DEFAULT_COURSES)
    parser.add_argument("--turkish-share", type=float, default=0.2)
    parser.add_argument("--out", type=Path, default=ROOT / "data/corpus_bulk")
    parser.add_argument("--summary", type=Path, default=None, help="also write the counts to this JSON file")
    args = parser.parse_args()

    documents = generate(args.seed, args.courses, args.turkish_share)
    check(documents)
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    for doc_id, text in documents.items():
        (args.out / f"{doc_id}.md").write_text(text, encoding="utf-8", newline="\n")

    chunks = build_chunks([args.out])
    summary = {
        "seed": args.seed,
        "courses": args.courses,
        "documents": len(documents),
        "chunks": len(chunks),
        "documents_by_type": dict(
            sorted(Counter(c["doc_type"] for c in {c["doc_id"]: c for c in chunks}.values()).items())
        ),
        "chunks_by_language": dict(sorted(Counter(c["language"] for c in chunks).items())),
        "revised_syllabi": sum(1 for d in documents if d.endswith("-syllabus-v2")),
        "out": str(args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out),
    }
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    print(text)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
