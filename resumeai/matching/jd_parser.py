"""
matching/jd_parser.py — Job Description Parser for Phase 2.

Extracts structured fields from raw JD text:
- title, required_skills, preferred_skills, 
  experience_requirements, responsibilities, keywords
"""
from __future__ import annotations

import re
from typing import List, Dict, Any, Set
from .schemas import ParsedJD


# ── Normalization map ─────────────────────────────────────────────────────────
# Canonical form: lowercase key → preferred display form
SKILL_NORMALIZATION: Dict[str, str] = {
    # JavaScript ecosystem
    "js": "JavaScript",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angularjs": "Angular",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    # Python
    "python": "Python",
    "py": "Python",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "tf": "TensorFlow",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    # Java/JVM
    "java": "Java",
    "kotlin": "Kotlin",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    # Cloud
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    # DevOps
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "ci/cd": "CI/CD",
    "terraform": "Terraform",
    # Databases
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "sql": "SQL",
    "nosql": "NoSQL",
    # ML/AI
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "computer vision": "Computer Vision",
    "cv": "Computer Vision",
    "llm": "LLM",
    "large language model": "LLM",
    "langchain": "LangChain",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "rag": "RAG",
    # Other common
    "git": "Git",
    "github": "GitHub",
    "graphql": "GraphQL",
    "rest": "REST API",
    "rest api": "REST API",
    "restful": "REST API",
    "microservices": "Microservices",
    "linux": "Linux",
    "c++": "C++",
    "c#": "C#",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "scala": "Scala",
    "spark": "Apache Spark",
    "apache spark": "Apache Spark",
    "kafka": "Apache Kafka",
    "apache kafka": "Apache Kafka",
    "airflow": "Apache Airflow",
    "streamlit": "Streamlit",
    "jira": "Jira",
    "agile": "Agile",
    "scrum": "Scrum",
}

# ── Section header patterns ───────────────────────────────────────────────────
REQUIRED_HEADERS = re.compile(
    r"\b(required|requirements|must have|must-have|mandatory|qualifications?|"
    r"minimum qualifications?|basic qualifications?)\b",
    re.IGNORECASE,
)
PREFERRED_HEADERS = re.compile(
    r"\b(preferred|nice to have|nice-to-have|bonus|plus|desired|"
    r"additional qualifications?|preferred qualifications?)\b",
    re.IGNORECASE,
)
RESPONSIBILITIES_HEADERS = re.compile(
    r"\b(responsibilities|what you.ll do|role|duties|what we.re looking for|"
    r"your role|day-to-day|you will)\b",
    re.IGNORECASE,
)
EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE),
    re.compile(r"(\d+)[\s-]+(\d+)\s*years?", re.IGNORECASE),
    re.compile(r"(entry[\s-]level|junior|mid[\s-]level|senior|lead|staff|principal)", re.IGNORECASE),
    re.compile(r"(internship|intern|co-op)", re.IGNORECASE),
    re.compile(r"(fresher|fresh graduate|0[\s-]+\d+\s*years?)", re.IGNORECASE),
]

# ── Known tech skill tokens ───────────────────────────────────────────────────
# Comprehensive set for rapid skill detection inside sentences
KNOWN_SKILL_TOKENS: Set[str] = set(SKILL_NORMALIZATION.keys()) | {
    "html", "css", "scss", "sass", "webpack", "vite", "babel",
    "jest", "pytest", "junit", "selenium", "cypress", "postman",
    "swagger", "openapi", "jwt", "oauth", "oauth2", "ldap",
    "elasticsearch", "cassandra", "dynamodb", "bigquery", "snowflake",
    "tableau", "powerbi", "power bi", "looker", "matplotlib",
    "pandas", "numpy", "scipy", "huggingface", "transformers",
    "fastapi", "celery", "rabbitmq", "mqtt", "grpc", "protobuf",
    "ansible", "helm", "argocd", "istio", "prometheus", "grafana",
    "splunk", "datadog", "new relic", "nginx", "apache", "haproxy",
    "maven", "gradle", "sbt", "bazel", "cmake", "make",
    "bash", "shell", "powershell", "zsh",
    "firebase", "supabase", "vercel", "netlify",
}


def _normalize_skill(raw: str) -> str:
    """Return canonical form of a skill, or titlecase if unknown."""
    key = raw.strip().lower()
    return SKILL_NORMALIZATION.get(key, raw.strip().title())


def _extract_skills_from_text(text: str) -> List[str]:
    """
    Scan text for known skill tokens using word-boundary matching.
    Returns deduplicated, normalized skill list.
    """
    text_lower = text.lower()
    found: Set[str] = set()

    # Check multi-word tokens first (longest match)
    sorted_tokens = sorted(KNOWN_SKILL_TOKENS, key=len, reverse=True)
    for token in sorted_tokens:
        pattern = r"(?<!\w)" + re.escape(token) + r"(?!\w)"
        if re.search(pattern, text_lower):
            found.add(_normalize_skill(token))

    return sorted(found)


def _extract_bullets(text: str) -> List[str]:
    """Extract bullet-point lines from text."""
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        # Match lines starting with bullet chars or numbers
        if re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped):
            content = re.sub(r"^[\-\•\*\◦\▸\▪\·\–\—\d\.\)]+\s*", "", stripped).strip()
            if len(content) > 10:
                bullets.append(content)
    return bullets


def _split_sections(text: str) -> Dict[str, str]:
    """
    Split JD text into named sections.
    Returns dict: section_type -> section_text
    Possible types: required, preferred, responsibilities, experience, general
    """
    lines = text.splitlines()
    sections: Dict[str, List[str]] = {
        "required": [],
        "preferred": [],
        "responsibilities": [],
        "general": [],
    }
    current = "general"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Only treat as a section header if it's a SHORT line (< 80 chars)
        # AND does NOT start with a bullet character (i.e., it's a heading, not content)
        is_bullet = bool(re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped))
        is_header_candidate = len(stripped) < 80 and not is_bullet

        if is_header_candidate and REQUIRED_HEADERS.search(stripped):
            current = "required"
            continue
        elif is_header_candidate and PREFERRED_HEADERS.search(stripped):
            current = "preferred"
            continue
        elif is_header_candidate and RESPONSIBILITIES_HEADERS.search(stripped):
            current = "responsibilities"
            continue

        sections[current].append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


def _extract_title(text: str) -> str:
    """Extract job title from first few lines of JD."""
    lines = [l.strip() for l in text.splitlines()[:8] if l.strip()]
    title_patterns = [
        re.compile(r"^(job title|position|role|title)\s*:?\s*(.+)$", re.IGNORECASE),
    ]
    for line in lines:
        for pat in title_patterns:
            m = pat.match(line)
            if m:
                return m.group(2).strip()

    # Heuristic: first short non-bullet line likely title
    for line in lines:
        if len(line) < 80 and not re.match(r"^[\-\•\*\d]", line):
            if any(kw in line.lower() for kw in [
                "engineer", "developer", "analyst", "scientist", "manager",
                "architect", "lead", "intern", "associate", "consultant",
                "specialist", "designer", "devops", "sre", "backend",
                "frontend", "fullstack", "full-stack", "data",
            ]):
                return line
    return lines[0] if lines else "Software Engineer"


def _extract_experience_reqs(text: str) -> List[str]:
    """Find experience requirement statements in text."""
    reqs: List[str] = []
    seen: Set[str] = set()
    for line in text.splitlines():
        for pat in EXPERIENCE_PATTERNS:
            if pat.search(line):
                clean = line.strip()
                if clean and clean not in seen and len(clean) > 5:
                    reqs.append(clean)
                    seen.add(clean)
                break
    return reqs[:10]


def _extract_keywords(required_skills: List[str], preferred_skills: List[str],
                       text: str) -> List[str]:
    """Build a deduplicated keyword list: skills + domain terms."""
    domain_patterns = [
        re.compile(r"\b(agile|scrum|kanban|tdd|bdd|devops|sre|ci/cd|mlops|dataops)\b", re.IGNORECASE),
        re.compile(r"\b(b\.?tech|m\.?tech|bachelor|master|phd|degree)\b", re.IGNORECASE),
        re.compile(r"\b(startup|enterprise|saas|paas|iaas|b2b|b2c)\b", re.IGNORECASE),
    ]
    kws: Set[str] = set(required_skills) | set(preferred_skills)
    for pat in domain_patterns:
        for m in pat.finditer(text):
            kws.add(m.group(0).strip())
    return sorted(kws)[:40]


# ── Public API ────────────────────────────────────────────────────────────────

def parse_job_description(text: str) -> ParsedJD:
    """
    Parse a raw job description string into a structured ParsedJD object.

    Args:
        text: Raw JD text (plain text, may contain bullets and sections)

    Returns:
        ParsedJD with title, required_skills, preferred_skills,
        experience_requirements, responsibilities, keywords
    """
    if not text or not text.strip():
        return ParsedJD()

    text = text.strip()

    # Split into sections
    sections = _split_sections(text)

    # Title
    title = _extract_title(text)

    # Required skills: from required section + full text scan
    req_skills_from_section = _extract_skills_from_text(
        sections.get("required", "") + "\n" + sections.get("general", "")
    )
    req_bullets = _extract_bullets(
        sections.get("required", "") + "\n" + sections.get("general", "")
    )

    # Preferred skills: from preferred section
    pref_skills = _extract_skills_from_text(sections.get("preferred", ""))

    # Remove preferred skills from required (they shouldn't overlap in output)
    pref_set = set(pref_skills)
    required_skills = [s for s in req_skills_from_section if s not in pref_set]

    # Responsibilities
    responsibilities = _extract_bullets(sections.get("responsibilities", ""))
    if not responsibilities:
        responsibilities = _extract_bullets(sections.get("general", ""))[:8]

    # Experience requirements
    experience_requirements = _extract_experience_reqs(text)

    # Keywords
    keywords = _extract_keywords(required_skills, pref_skills, text)

    return ParsedJD(
        title=title,
        required_skills=required_skills,
        preferred_skills=pref_skills,
        experience_requirements=experience_requirements,
        responsibilities=responsibilities,
        keywords=keywords,
    )
