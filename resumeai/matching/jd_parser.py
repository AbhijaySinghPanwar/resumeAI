"""
matching/jd_parser.py — Job Description Parser for Phase 2 (v2).

Uses a curated CANONICAL_SKILLS dictionary for phrase-first skill extraction.
Generic words (engineer, intern, software, data, problem, solving, apis, etc.)
are NEVER extracted as standalone skills.

Multi-word skills are always kept together:
  "REST API" → one skill
  "Problem Solving" → one skill
  "Data Structures" → one skill
  "Machine Learning" → one skill
  "System Design" → one skill
"""
from __future__ import annotations

import re
from typing import List, Dict, Set
from .schemas import ParsedJD


# ── CANONICAL SKILLS — curated, phrase-first dictionary ──────────────────────
# Format: (canonical_display_name, [aliases_lowercase])
# Sorted LONGEST-FIRST at extraction time to prevent partial matches.

CANONICAL_SKILLS: List[tuple] = [
    # ── CS Fundamentals & Concepts ───────────────────────────────────────
    ("Data Structures and Algorithms", ["data structures and algorithms", "data structures & algorithms"]),
    ("Data Structures", ["data structures", "data structure"]),
    ("Algorithms", ["algorithms", "algorithm design"]),
    ("Problem Solving", ["problem solving", "problem-solving", "analytical skills"]),
    ("System Design", ["system design", "systems design", "high level design", "hld", "lld", "low level design"]),
    ("Object-Oriented Programming", ["object-oriented programming", "object oriented programming", "oop", "oops", "object-oriented design", "ood"]),
    ("Distributed Systems", ["distributed systems", "distributed computing"]),
    ("Operating Systems", ["operating systems", "os concepts"]),
    ("Computer Networks", ["computer networks", "networking", "network programming"]),
    ("Database Management Systems", ["database management systems", "dbms", "rdbms"]),
    ("Design Patterns", ["design patterns", "software design patterns"]),
    ("Competitive Programming", ["competitive programming", "cp", "competitive coding"]),

    # ── Programming Languages ─────────────────────────────────────────────
    ("Python", ["python", "python3", "python 3"]),
    ("JavaScript", ["javascript", "js", "es6", "es2015", "ecmascript"]),
    ("TypeScript", ["typescript", "ts"]),
    ("Java", ["java", "java 8", "java 11", "java 17"]),
    ("C++", ["c++", "cpp", "c plus plus"]),
    ("C", ["c programming", "c language"]),
    ("C#", ["c#", "csharp", "c sharp"]),
    ("Go", ["golang", "go language"]),
    ("Rust", ["rust", "rust-lang"]),
    ("Ruby", ["ruby", "ruby on rails"]),
    ("Kotlin", ["kotlin"]),
    ("Swift", ["swift", "swiftui"]),
    ("Scala", ["scala"]),
    ("PHP", ["php", "php7", "php8"]),
    ("R", ["r programming", "r language"]),
    ("MATLAB", ["matlab"]),
    ("Bash", ["bash", "bash scripting", "shell scripting", "shell script", "zsh"]),
    ("SQL", ["sql", "structured query language", "pl/sql", "plpgsql"]),
    ("HTML/CSS", ["html", "css", "html5", "css3", "html/css"]),

    # ── Web Frameworks & Libraries ────────────────────────────────────────
    ("FastAPI", ["fastapi", "fast api"]),
    ("Django", ["django", "django rest framework", "drf"]),
    ("Flask", ["flask"]),
    ("Spring Boot", ["spring boot", "springboot"]),
    ("Spring", ["spring framework", "spring mvc"]),
    ("React", ["react", "reactjs", "react.js", "react js"]),
    ("Next.js", ["next.js", "nextjs", "next js"]),
    ("Vue.js", ["vue.js", "vuejs", "vue js", "vue"]),
    ("Angular", ["angular", "angularjs", "angular.js"]),
    ("Node.js", ["node.js", "nodejs", "node js"]),
    ("Express.js", ["express.js", "expressjs", "express js", "express"]),
    ("Svelte", ["svelte", "sveltekit"]),
    ("Ruby on Rails", ["ruby on rails", "rails", "ror"]),
    ("Laravel", ["laravel"]),
    ("FastAPI", ["fastapi"]),

    # ── Databases ─────────────────────────────────────────────────────────
    ("PostgreSQL", ["postgresql", "postgres", "psql"]),
    ("MySQL", ["mysql", "mariadb"]),
    ("MongoDB", ["mongodb", "mongo"]),
    ("Redis", ["redis"]),
    ("SQLite", ["sqlite"]),
    ("Elasticsearch", ["elasticsearch", "elastic search", "opensearch"]),
    ("Cassandra", ["cassandra", "apache cassandra"]),
    ("DynamoDB", ["dynamodb", "amazon dynamodb"]),
    ("BigQuery", ["bigquery", "google bigquery"]),
    ("Snowflake", ["snowflake"]),
    ("Neo4j", ["neo4j", "graph database"]),
    ("Oracle", ["oracle", "oracle db", "oracle database"]),

    # ── Cloud & DevOps ────────────────────────────────────────────────────
    ("AWS", ["aws", "amazon web services", "amazon aws"]),
    ("GCP", ["gcp", "google cloud platform", "google cloud"]),
    ("Azure", ["azure", "microsoft azure"]),
    ("Docker", ["docker", "docker containers", "containerization"]),
    ("Kubernetes", ["kubernetes", "k8s"]),
    ("Terraform", ["terraform"]),
    ("Ansible", ["ansible"]),
    ("CI/CD", ["ci/cd", "continuous integration", "continuous deployment", "continuous delivery", "github actions", "gitlab ci", "jenkins", "circleci"]),
    ("GitHub Actions", ["github actions"]),
    ("Jenkins", ["jenkins"]),
    ("Nginx", ["nginx"]),
    ("Linux", ["linux", "ubuntu", "centos", "debian"]),
    ("Git", ["git", "version control"]),
    ("GitHub", ["github"]),
    ("GitLab", ["gitlab"]),

    # ── APIs & Integration ────────────────────────────────────────────────
    ("REST APIs", ["rest apis", "rest api", "restful api", "restful apis", "restful", "rest", "http api"]),
    ("GraphQL", ["graphql", "graph ql"]),
    ("gRPC", ["grpc"]),
    ("WebSockets", ["websockets", "websocket", "ws"]),
    ("OAuth", ["oauth", "oauth2", "oauth 2.0"]),
    ("JWT", ["jwt", "json web token"]),

    # ── Data Science & ML/AI ──────────────────────────────────────────────
    ("Machine Learning", ["machine learning", "ml algorithms", "supervised learning", "unsupervised learning"]),
    ("Deep Learning", ["deep learning", "dl", "neural networks", "neural network"]),
    ("NLP", ["nlp", "natural language processing", "text processing"]),
    ("Computer Vision", ["computer vision", "image processing", "cv"]),
    ("LLM", ["llm", "large language model", "large language models", "language models"]),
    ("LangChain", ["langchain", "lang chain"]),
    ("RAG", ["rag", "retrieval augmented generation"]),
    ("GenAI", ["genai", "generative ai", "gen ai"]),
    ("OpenAI", ["openai", "open ai", "gpt", "gpt-4", "chatgpt"]),
    ("Hugging Face", ["hugging face", "huggingface", "transformers"]),
    ("TensorFlow", ["tensorflow", "tf"]),
    ("PyTorch", ["pytorch", "torch"]),
    ("Scikit-learn", ["scikit-learn", "sklearn", "scikit learn"]),
    ("Pandas", ["pandas"]),
    ("NumPy", ["numpy", "numpy arrays"]),
    ("Matplotlib", ["matplotlib", "seaborn", "plotly"]),
    ("Apache Spark", ["apache spark", "pyspark", "spark"]),
    ("Apache Kafka", ["apache kafka", "kafka"]),
    ("Apache Airflow", ["apache airflow", "airflow"]),

    # ── Tools & Testing ───────────────────────────────────────────────────
    ("Postman", ["postman"]),
    ("Swagger", ["swagger", "openapi"]),
    ("Jira", ["jira"]),
    ("Figma", ["figma"]),
    ("Selenium", ["selenium"]),
    ("Jest", ["jest"]),
    ("Pytest", ["pytest"]),
    ("JUnit", ["junit"]),
    ("Cypress", ["cypress"]),
    ("Tableau", ["tableau"]),
    ("Power BI", ["power bi", "powerbi"]),

    # ── Methodologies & Soft Skills (technical context) ───────────────────
    ("Agile", ["agile", "agile methodology", "agile development"]),
    ("Scrum", ["scrum", "scrum master"]),
    ("Microservices", ["microservices", "microservice architecture", "service mesh"]),
    ("Test-Driven Development", ["test-driven development", "tdd", "test driven development"]),
    ("DevOps", ["devops"]),
    ("MLOps", ["mlops", "ml ops"]),
    ("Data Structures", ["dsa", "ds&a"]),  # alias: DSA matches Data Structures
]

# ── Build lookup structures ───────────────────────────────────────────────────

# Map: lowercase_alias → canonical_display_name
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
# All aliases sorted by length descending (for greedy phrase matching)
_ALL_ALIASES_SORTED: List[tuple] = []   # (alias_lower, canonical)

for canonical, aliases in CANONICAL_SKILLS:
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical

# Sort all aliases by length descending so multi-word skills match before sub-words
_ALL_ALIASES_SORTED = sorted(
    _ALIAS_TO_CANONICAL.items(),
    key=lambda x: len(x[0]),
    reverse=True,
)


def normalize_skill(raw: str) -> str:
    """Return canonical form of a skill string."""
    return _ALIAS_TO_CANONICAL.get(raw.strip().lower(), raw.strip())


def extract_skills_from_text(text: str) -> List[str]:
    """
    Extract canonical skills from text using phrase-first matching.

    Uses the CANONICAL_SKILLS dictionary:
    - Multi-word phrases matched first (longest match wins)
    - Generic words never extracted standalone
    - Returns deduplicated, canonical skill names
    """
    if not text:
        return []
    text_lower = text.lower()
    found: Set[str] = set()
    consumed_spans: List[tuple] = []  # (start, end) of already-matched spans

    for alias, canonical in _ALL_ALIASES_SORTED:
        # Find all occurrences of this alias in text
        pattern = r"(?<![a-zA-Z0-9/\-])" + re.escape(alias) + r"(?![a-zA-Z0-9/\-])"
        for m in re.finditer(pattern, text_lower):
            start, end = m.start(), m.end()
            # Check no overlap with already-consumed span
            overlaps = any(s < end and start < e for s, e in consumed_spans)
            if not overlaps:
                found.add(canonical)
                consumed_spans.append((start, end))

    return sorted(found)


# ── Section header patterns ───────────────────────────────────────────────────
REQUIRED_HEADERS = re.compile(
    r"^(required|requirements|must have|must-have|mandatory|qualifications?|"
    r"minimum qualifications?|basic qualifications?|what you.ll need|what we need):?\s*$",
    re.IGNORECASE,
)
PREFERRED_HEADERS = re.compile(
    r"^(preferred|nice to have|nice-to-have|bonus|plus|desired|"
    r"additional qualifications?|preferred qualifications?|good to have|advantages?):?\s*$",
    re.IGNORECASE,
)
RESPONSIBILITIES_HEADERS = re.compile(
    r"^(responsibilities|what you.ll do|role|duties|your role|"
    r"day-to-day|you will|what you will do|key responsibilities):?\s*$",
    re.IGNORECASE,
)
EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE),
    re.compile(r"(\d+)[\s-]+(\d+)\s*years?", re.IGNORECASE),
    re.compile(r"(entry[\s-]level|junior|mid[\s-]level|senior|lead|staff|principal)", re.IGNORECASE),
    re.compile(r"(internship|intern|co-op|fresher|fresh graduate)", re.IGNORECASE),
]


def _split_sections(text: str) -> Dict[str, str]:
    """Split JD into named sections without mis-tagging bullet content as headers."""
    lines = text.splitlines()
    sections: Dict[str, List[str]] = {
        "required": [], "preferred": [], "responsibilities": [], "general": [],
    }
    current = "general"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Only allow section switch on SHORT lines that are NOT bullet content
        is_bullet = bool(re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped))
        is_candidate = len(stripped) < 80 and not is_bullet

        if is_candidate and REQUIRED_HEADERS.match(stripped):
            current = "required"
            continue
        elif is_candidate and PREFERRED_HEADERS.match(stripped):
            current = "preferred"
            continue
        elif is_candidate and RESPONSIBILITIES_HEADERS.match(stripped):
            current = "responsibilities"
            continue

        sections[current].append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


def _extract_bullets(text: str) -> List[str]:
    """Extract bullet-point lines from text."""
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped):
            content = re.sub(r"^[\-\•\*\◦\▸\▪\·\–\—\d\.\)]+\s*", "", stripped).strip()
            if len(content) > 5:
                bullets.append(content)
    return bullets


def _extract_title(text: str) -> str:
    """Extract job title from first few non-bullet lines of JD."""
    lines = [l.strip() for l in text.splitlines()[:10] if l.strip()]
    title_kws = [
        "engineer", "developer", "analyst", "scientist", "manager",
        "architect", "lead", "intern", "associate", "consultant",
        "specialist", "designer", "devops", "sre", "backend",
        "frontend", "fullstack", "full-stack", "data", "software",
    ]
    for line in lines:
        if len(line) < 90 and not re.match(r"^[\-\•\*\d]", line):
            if any(kw in line.lower() for kw in title_kws):
                return line
    return lines[0] if lines else "Software Engineer"


def _extract_experience_reqs(text: str) -> List[str]:
    """Find experience requirement statements."""
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


# ── Public API ────────────────────────────────────────────────────────────────

def parse_job_description(text: str) -> ParsedJD:
    """
    Parse a raw job description string into a structured ParsedJD object.

    Skills are extracted using the curated CANONICAL_SKILLS dictionary.
    Generic words (engineer, intern, software, data, apis, problem, solving)
    are NEVER extracted as standalone skills.

    Args:
        text: Raw JD text (plain text, may contain bullets and sections)

    Returns:
        ParsedJD with title, required_skills, preferred_skills,
        experience_requirements, responsibilities, keywords
    """
    if not text or not text.strip():
        return ParsedJD()

    text = text.strip()
    sections = _split_sections(text)

    title = _extract_title(text)

    # Required skills: scan required section + general section (full text scan)
    required_text = sections.get("required", "") + "\n" + sections.get("general", "")
    all_required = extract_skills_from_text(required_text)

    # Preferred skills: scan preferred section only
    pref_skills = extract_skills_from_text(sections.get("preferred", ""))

    # Remove preferred from required
    pref_set = set(pref_skills)
    required_skills = [s for s in all_required if s not in pref_set]

    # Responsibilities
    responsibilities = _extract_bullets(sections.get("responsibilities", ""))
    if not responsibilities:
        responsibilities = _extract_bullets(sections.get("general", ""))[:8]

    # Experience requirements
    experience_requirements = _extract_experience_reqs(text)

    # Keywords: union of required + preferred skills (clean, canonical)
    keywords = sorted(set(required_skills) | set(pref_skills))

    return ParsedJD(
        title=title,
        required_skills=required_skills,
        preferred_skills=pref_skills,
        experience_requirements=experience_requirements,
        responsibilities=responsibilities,
        keywords=keywords,
    )
