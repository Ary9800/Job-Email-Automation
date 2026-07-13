import re

JOB_TITLE_IN_COMPANY = re.compile(
    r"\b(java|software|engineer|developer|backend|fullstack|full[\s-]?stack|senior|junior|associate|engin)\b",
    re.I,
)

KNOWN_DOMAIN_COMPANIES = {
    "spec-india": "SPEC INDIA",
    "apideltech": "Apidel Technologies",
    "programming": "Programming.com",
    "nebulogic": "NebuLogic Technologies",
    "nebulogictech": "NebuLogic Technologies",
}

# Most specific roles first — order matters
ROLE_DETECTION_PATTERNS: list[tuple[str, list[str]]] = [
    ("Java Backend Engineer", [
        r"java\s+backend\s+engineer",
        r"backend\s+engineer[^.\n]{0,40}\bjava\b",
        r"\bjava\b[^.\n]{0,40}backend\s+engineer",
        r"software\s+engineer\s*\(\s*java\s+backend",
        r"\(\s*java\s+backend\s*\)",
    ]),
    ("Java Backend Developer", [
        r"java\s+backend\s+devel",
        r"java\s+backend\s+developer",
        r"backend\s+devel[^.\n]{0,40}\bjava\b",
        r"entry[\s-]?level\s+java\s+backend",
    ]),
    ("Java Full Stack Developer", [
        r"java\s+full\s*stack",
        r"full\s*stack\s+java",
        r"java\s+fullstack",
    ]),
    ("Java Software Engineer", [
        r"java\s+software\s+engin",
    ]),
    ("Application Developer – Java", [
        r"application\s+developer[^.\n]*\bjava\b",
        r"developer\s*[–\-]\s*java",
    ]),
    ("Backend Engineer", [
        r"backend\s+engineer",
        r"back[\s-]?end\s+engineer",
    ]),
    ("Software Engineer", [
        r"software\s+engineer",
    ]),
    ("Java Developer", [
        r"java\s+developer",
        r"java\s+dev\b",
        r"hiring\s+for\s+a\s+java\s+developer",
    ]),
]


def detect_role_from_text(text: str, allowed: list[str] | None = None) -> str | None:
    """Detect the most specific job title from post/OCR text."""
    if not text:
        return None
    text_lower = text.lower()
    for role_name, patterns in ROLE_DETECTION_PATTERNS:
        if allowed and role_name not in allowed:
            continue
        for pat in patterns:
            if re.search(pat, text_lower):
                return role_name
    return None


def resolve_role(raw_role: str | None, raw_text: str | None) -> str | None:
    """Prefer role detected from full OCR text over generic AI/Ollama guesses."""
    combined = " ".join(filter(None, [raw_text, raw_role]))
    detected = detect_role_from_text(combined)
    if detected:
        return clean_role(detected)
    return clean_role(raw_role)


def clean_role(role: str | None) -> str | None:
    """Remove experience years from role, fix OCR mashed text."""
    if not role:
        return role

    role = role.strip()

    role = re.sub(
        r"[\s\-–—]+(\d+\s*to\s*\d+|\d+\+)\s*(years?|yrs?)[^\n]*",
        "",
        role,
        flags=re.IGNORECASE,
    )
    role = re.sub(r"[\s\-–—]+\d+to\d+[^\n]*", "", role, flags=re.IGNORECASE)
    role = re.sub(r"[\s\-–—]+(fresher|senior|mid)[^\n]*$", "", role, flags=re.IGNORECASE)

    role = re.sub(r"([a-z])([A-Z])", r"\1 \2", role)
    role = re.sub(
        r"(Developer|Engineer|Analyst|Manager|Architect|Consultant)(\d)",
        r"\1 \2",
        role,
        flags=re.IGNORECASE,
    )
    role = re.sub(r"(\d)([A-Za-z])", r"\1 \2", role)

    # OCR truncations: Engin -> Engineer, Devel -> Developer
    role = re.sub(r"\bEngin\b(?!\w)", "Engineer", role, flags=re.I)
    role = re.sub(r"\bDevel\b(?!\w)", "Developer", role, flags=re.I)

    role = re.sub(r"\s+\d+.*$", "", role).strip()
    role = re.sub(r"\s+", " ", role)

    return role or None


def _is_garbled_company(name: str) -> bool:
    if not name or len(name.strip()) < 2:
        return True

    name = name.strip()
    lowered = name.lower()

    if lowered in ("company", "[company]", "your company", "n/a", ""):
        return True

    # Mashed OCR blob: comJavaSoftwareEnginNebuLogic...
    if re.match(r"^com[A-Z]", name):
        return True

    # Long string with no spaces — almost always OCR garbage
    if len(name) > 16 and " " not in name:
        return True

    # Job title words stuck inside company name without spaces
    if JOB_TITLE_IN_COMPANY.search(name) and " " not in name:
        return True

    # Repeated fragment: NebuLogicNebuLogic
    if re.search(r"([A-Za-z]{4,})\1", name):
        return True

    return False


def _extract_company_from_text(text: str) -> str | None:
    if not text:
        return None

    patterns = [
        r"(NebuLogic\s*Technologies?)",
        r"([A-Z][a-zA-Z]*Logic)\s*Technologies",
        r"([A-Z][a-zA-Z][a-z]+)\s+Technologies(?:\s+(?:Pvt|Ltd|Inc)\.?)?",
        r"SPEC\s*INDIA",
        r"Apidel\s*Technologies",
        r"(?:Hiring at|at|join)\s+([A-Z][A-Za-z0-9\s&\-]+(?:INDIA|Technologies|Tech|Ltd|Inc|Pvt))",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            comp = (m.group(1) if m.lastindex else m.group(0)).strip()
            comp = re.sub(r"\s+", " ", comp)
            if not _is_garbled_company(comp):
                return comp

    return None


def _company_from_email(email: str) -> str | None:
    domain = email.split("@")[1].lower()
    org_key = domain.split(".")[0]
    if org_key in KNOWN_DOMAIN_COMPANIES:
        return KNOWN_DOMAIN_COMPANIES[org_key]
    org = org_key.replace("-", " ").replace("_", " ")
    return org.title()


def clean_company(
    company: str | None,
    email: str | None = None,
    raw_text: str | None = None,
) -> str | None:
    """Clean company name; recover from OCR text or email when garbled."""
    combined_text = " ".join(filter(None, [company, raw_text]))

    if company:
        company = company.strip()
        company = re.sub(r"^\[|\]$", "", company)
        if not _is_garbled_company(company):
            return company

    # Email domain is more reliable than OCR text for known companies
    if email and "@" in email:
        from_email = _company_from_email(email)
        if from_email:
            return from_email

    extracted = _extract_company_from_text(combined_text)
    if extracted:
        return extracted

    return None


def extract_experience(text: str) -> str | None:
    """Pull experience into separate field, not role."""
    patterns = [
        r"(\d+\s*to\s*\d+\s*years?)",
        r"(\d+\+\s*years?)",
        r"(\d+\s*years?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def normalize_extracted(data: dict) -> dict:
    """Apply cleaning to extracted job data."""
    email = data.get("recruiter_email")
    raw_role = data.get("role")
    raw_company = data.get("company")
    raw_text = data.get("raw_text")

    if raw_role:
        if not data.get("experience_required"):
            exp = extract_experience(raw_role) or extract_experience(raw_text or "")
            if exp:
                data["experience_required"] = exp

    data["role"] = resolve_role(raw_role, raw_text)

    data["company"] = clean_company(raw_company, email, raw_text)

    return data
