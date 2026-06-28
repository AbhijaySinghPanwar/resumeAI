"""
extractors/projects.py — Phase 1.6 Project Reconstruction Engine.

Key improvements over Phase 1.5:
  - Generic continuation-line detection (not resume-specific heuristics).
  - A project block ends ONLY when another genuine project title is detected
    OR a section boundary occurs. Blank lines do NOT end a project.
  - Link-label lines (GitHub Link, Live Demo, Repository, Source Code, etc.)
    always attach to the current project — never start a new one.
  - Wrapped description sentences are merged into the preceding bullet/description.
  - Full backward-compatible output + Phase 1.5 enriched fields.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from resumeai.extractors._continuation import is_continuation, is_link_label_line

# ── Regex helpers ─────────────────────────────────────────────────────────────
URL_RE        = re.compile(r"https?://[^\s>|]+", re.IGNORECASE)
GITHUB_RE     = re.compile(r"(?:https?://)?github\.com/[\w\-./]+", re.IGNORECASE)
BULLET_RE     = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s*")

TECH_HEADER_RE = re.compile(
    r"^(?:tech(?:nolog(?:ies|y))?(?:\s*stack)?|stack|tools?|frameworks?|"
    r"libraries|built\s*(?:with|using)|using|technologies\s*used|"
    r"dependencies|language|languages?)[:\s]+(.+)",
    re.IGNORECASE,
)

# Link-label patterns WITH optional colon and optional URL.
# Also matches pipe-separated combos: "LiveDemo | GitHub", "LiveDemo|GitHub"
LINK_LINE_RE = re.compile(
    r"^((?:live\s*demo|livedemo|demo|preview|"
    r"github(?:\s*(?:link|repo(?:sitory)?|url))?|"
    r"deployed\s*(?:at|link|app)?|"
    r"repository|repo|source(?:\s*code)?|"
    r"working\s*(?:project\s*)?(?:link|demo)?|"
    r"project\s*link|app\s*link|website|portfolio|"
    r"view\s*(?:project|demo|source|code)?|"
    r"deployment|hosted(?:\s*(?:at|on))?"
    r")"
    r"(?:\s*[\|]\s*"
    r"(?:live\s*demo|livedemo|demo|github(?:\s*(?:link|repo)?)?|"
    r"repository|repo|source|preview|deployment|website))*"
    r")\s*[:\-]?\s*(https?://\S+)?$",
    re.IGNORECASE,
)

# ── Technology normalization ───────────────────────────────────────────────────
TECH_NORMALIZE: Dict[str, str] = {
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js", "node js": "Node.js",
    "express": "Express.js", "expressjs": "Express.js", "express.js": "Express.js",
    "reactjs": "React.js", "react": "React.js", "react.js": "React.js",
    "nextjs": "Next.js", "next.js": "Next.js",
    "vuejs": "Vue.js", "vue": "Vue.js", "vue.js": "Vue.js",
    "angularjs": "Angular", "angular.js": "Angular",
    "tailwindcss": "Tailwind CSS", "tailwind": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "python": "Python", "py": "Python",
    "streamlit": "Streamlit", "flask": "Flask", "django": "Django",
    "fastapi": "FastAPI", "fast api": "FastAPI",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "psql": "PostgreSQL", "redis": "Redis", "sqlite": "SQLite",
    "firebase": "Firebase", "supabase": "Supabase", "dynamodb": "DynamoDB",
    "aws": "AWS", "aws console": "AWS", "awsconsole": "AWS",
    "gcp": "GCP", "google cloud": "GCP", "azure": "Azure",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "github actions": "GitHub Actions", "ci/cd": "CI/CD",
    "terraform": "Terraform", "nginx": "Nginx", "linux": "Linux",
    "rest api": "REST APIs", "rest apis": "REST APIs", "restful": "REST APIs",
    "restful api": "REST APIs", "graphql": "GraphQL",
    "jwt": "JWT", "jwt authentication": "JWT", "jwt auth": "JWT",
    "oauth": "OAuth", "oauth2": "OAuth2", "websocket": "WebSocket",
    "websockets": "WebSocket",
    "twilio": "Twilio API", "twilioapi": "Twilio API", "twilio api": "Twilio API",
    "gemini": "Gemini API", "gemini api": "Gemini API",
    "google gemini": "Gemini API", "googlegeminiapi": "Gemini API",
    "google gemini api": "Gemini API",
    "openai": "OpenAI", "chatgpt": "OpenAI", "gpt": "OpenAI",
    "anthropic": "Claude API", "langchain": "LangChain",
    "llm": "LLM", "llms": "LLM", "large language model": "LLM",
    "rag": "RAG", "huggingface": "Hugging Face", "hugging face": "Hugging Face",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch", "torch": "PyTorch",
    "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "pandas": "Pandas", "numpy": "NumPy",
    "pinecone": "Pinecone", "weaviate": "Weaviate", "chroma": "Chroma",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab", "postman": "Postman",
    "esp32": "ESP32", "arduino": "Arduino",
    "flutter": "Flutter", "react native": "React Native",
    "kotlin": "Kotlin", "swift": "Swift",
    "javascript": "JavaScript", "typescript": "TypeScript",
    "java": "Java", "c++": "C++", "cpp": "C++", "c#": "C#",
    "golang": "Go", "rust": "Rust",
    "html": "HTML", "css": "CSS", "html/css": "HTML/CSS",
    "sql": "SQL",
}

# ── Technology → implied capabilities ─────────────────────────────────────────
TECH_IMPLIES: Dict[str, List[str]] = {
    "Node.js": ["JavaScript", "Backend Development"],
    "Express.js": ["Node.js", "JavaScript", "REST APIs", "Backend Development"],
    "React.js": ["JavaScript", "Frontend Development"],
    "Next.js": ["React.js", "JavaScript", "Full Stack Development"],
    "FastAPI": ["Python", "REST APIs", "Backend Development"],
    "Django": ["Python", "REST APIs", "Backend Development"],
    "Flask": ["Python", "REST APIs", "Backend Development"],
    "MongoDB": ["Database", "NoSQL"],
    "MySQL": ["Database", "SQL"],
    "PostgreSQL": ["Database", "SQL"],
    "Redis": ["Database", "Caching"],
    "Firebase": ["Database", "Cloud", "Real-time"],
    "Docker": ["DevOps", "Cloud Deployment"],
    "Kubernetes": ["DevOps", "Cloud Deployment", "Container Orchestration"],
    "AWS": ["Cloud", "Cloud Deployment"],
    "GCP": ["Cloud", "Cloud Deployment"],
    "JWT": ["Authentication", "Security"],
    "REST APIs": ["Backend Development", "API Design"],
    "GraphQL": ["Backend Development", "API Design"],
    "WebSocket": ["Real-time", "Backend Development"],
    "Gemini API": ["AI/ML", "LLM Integration", "Generative AI"],
    "OpenAI": ["AI/ML", "LLM Integration", "Generative AI"],
    "LangChain": ["AI/ML", "LLM Integration", "RAG"],
    "TensorFlow": ["AI/ML", "Deep Learning"],
    "PyTorch": ["AI/ML", "Deep Learning"],
    "Scikit-learn": ["AI/ML", "Machine Learning"],
    "Streamlit": ["Python", "Data Visualization", "AI/ML"],
    "ESP32": ["IoT", "Embedded Systems", "Hardware"],
    "GitHub Actions": ["CI/CD", "DevOps"],
    "CI/CD": ["DevOps", "Automation"],
    "Pinecone": ["Vector Database", "AI/ML"],
}

# ── Domain classification ─────────────────────────────────────────────────────
FRONTEND_TECHS = {"React.js","Vue.js","Angular","Svelte","HTML/CSS","HTML","CSS","Bootstrap","Tailwind CSS"}
BACKEND_TECHS  = {"Express.js","FastAPI","Django","Flask","Spring Boot","Node.js","REST APIs","GraphQL","gRPC"}
DB_TECHS       = {"MongoDB","MySQL","PostgreSQL","Redis","SQLite","Firebase","DynamoDB","Supabase"}
AI_TECHS       = {"TensorFlow","PyTorch","Scikit-learn","LangChain","OpenAI","Gemini API","RAG","LLM","Hugging Face","Streamlit","Pinecone"}
IOT_TECHS      = {"ESP32","Arduino","Raspberry Pi","WebSocket"}
CLOUD_TECHS    = {"AWS","GCP","Azure","Docker","Kubernetes","GitHub Actions","Terraform","CI/CD","Nginx"}

COMPLEXITY_RUBRIC: Dict[str, int] = {
    "database": 15, "auth": 15, "cloud_deploy": 15, "realtime": 15,
    "ai_ml": 20, "rest_api": 10, "multi_tech": 10, "testing": 10,
    "iot": 15, "ci_cd": 10, "containerized": 10, "frontend": 5, "backend": 5,
}

ACTION_CONFIDENCE: Dict[str, int] = {
    "architected": 100, "designed": 95, "built": 90, "developed": 90,
    "implemented": 88, "integrated": 85, "deployed": 85, "optimized": 85,
    "created": 80, "engineered": 90, "led": 85, "automated": 88,
    "configured": 82, "wrote": 78, "used": 70, "utilized": 70,
}


# ── Line classifiers ──────────────────────────────────────────────────────────

def _is_tech_header_line(line: str) -> bool:
    return bool(TECH_HEADER_RE.match(line.strip()))


def _is_link_line(line: str) -> bool:
    """True if the line is a link label or contains a URL."""
    stripped = line.strip()
    if URL_RE.search(stripped):
        return True
    return bool(LINK_LINE_RE.match(stripped))


_LIVE_DEMO_LABEL_RE = re.compile(
    r"^(live\s*demo|livedemo|demo|preview|website|app\s*link|site|"
    r"hosted|view|click\s*here|play|deployed\s*at|deployment)",
    re.IGNORECASE,
)
_GITHUB_LABEL_RE = re.compile(r"^github", re.IGNORECASE)
_REPO_LABEL_RE   = re.compile(
    r"^(source(?:\s*code)?|repo(?:sitory)?|working\s*(?:project\s*)?link)",
    re.IGNORECASE,
)

def _classify_url_line(line: str) -> Dict[str, Optional[str]]:
    """Classify a link/URL line into github/live_demo/deployment."""
    result: Dict[str, Optional[str]] = {"github": None, "live_demo": None, "deployment": None}
    stripped = line.strip()
    lower = stripped.lower()

    # Extract label (before the colon or before the URL)
    label = ""
    colon_idx = stripped.find(":")
    if colon_idx > 0 and colon_idx < 30:
        label = stripped[:colon_idx].strip()

    urls = URL_RE.findall(stripped)
    for url in urls:
        url_lower = url.lower()
        if "github.com" in url_lower:
            result["github"] = url
        elif any(k in url_lower for k in ["vercel", "netlify", "heroku", "railway",
                                           "render", "fly.io", "pages.dev",
                                           "web.app", "appspot", "glitch.me"]):
            result["live_demo"] = url
        elif label and _LIVE_DEMO_LABEL_RE.match(label):
            # Label says "Live Demo" → classify as live_demo regardless of domain
            result["live_demo"] = url
        elif label and _GITHUB_LABEL_RE.match(label):
            result["github"] = url
        elif label and _REPO_LABEL_RE.match(label):
            result["deployment"] = url
        else:
            result["deployment"] = result["deployment"] or url

    # Handle label-only lines with no embedded URL
    if not any(result.values()):
        if any(k in lower for k in ["github"]):
            result["github"] = "GitHub (URL not captured)"
        if any(k in lower for k in ["live demo", "livedemo", "demo", "preview", "deployed", "website"]):
            result["live_demo"] = "Live Demo (URL not captured)"
        if any(k in lower for k in ["repository", "repo", "source"]):
            result["deployment"] = "Repository (URL not captured)"

    return result


def _looks_like_project_title(line: str) -> bool:
    """
    Heuristic: does this non-bullet, non-tech, non-link line look like a project name?
    
    A project title is typically:
      - Short (≤ 80 chars, and ideally 1-6 words for a clean title)
      - Does NOT end with sentence punctuation (., ,, ;)
      - Does NOT start lowercase (not a continuation)
      - Not purely numeric/date
      - Not a tech header line
      - Not a link label
    
    Long sentence-like lines (>80 chars) are NEVER project titles — they are
    descriptions or continuation lines even if they don't end with a period.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if BULLET_RE.match(stripped):
        return False
    if _is_tech_header_line(stripped):
        return False
    if _is_link_line(stripped):
        return False
    if is_continuation(stripped):
        return False
    if stripped.endswith((".", ",", ";")):
        return False
    # Long lines are descriptions, not titles — even without a terminal period
    if len(stripped) > 80:
        return False
    if re.match(r"^[\d\s\-–—/()]+$", stripped):
        return False
    return True


# ── Technology extraction ─────────────────────────────────────────────────────

def _normalize_tech(raw: str) -> Optional[str]:
    return TECH_NORMALIZE.get(raw.strip().lower())


def _extract_tech_from_csv(text: str) -> List[str]:
    parts = re.split(r"[,/|]+", text)
    result, seen = [], set()
    for p in parts:
        raw = p.strip().strip(".")
        if not raw or len(raw) < 2:
            continue
        n = _normalize_tech(raw)
        if n and n not in seen:
            result.append(n); seen.add(n)
        elif not n:
            for sub in raw.split():
                n2 = _normalize_tech(sub)
                if n2 and n2 not in seen:
                    result.append(n2); seen.add(n2)
    return result


def _extract_tech_from_freetext(text: str) -> List[str]:
    text_lower = text.lower()
    found, seen = [], set()
    candidates = sorted(TECH_NORMALIZE.keys(), key=len, reverse=True)
    for alias in candidates:
        canonical = TECH_NORMALIZE[alias]
        if canonical in seen:
            continue
        pattern = r"(?<![a-zA-Z0-9/\-])" + re.escape(alias) + r"(?![a-zA-Z0-9/\-])"
        if re.search(pattern, text_lower):
            found.append(canonical); seen.add(canonical)
    return found


def _merge_techs(*tech_lists: List[str]) -> List[str]:
    seen, result = set(), []
    for lst in tech_lists:
        for t in lst:
            if t not in seen:
                result.append(t); seen.add(t)
    return result


# ── Domain + complexity ───────────────────────────────────────────────────────

def _classify_domain(techs: List[str]) -> str:
    tech_set = set(techs)
    if tech_set & IOT_TECHS:
        return "IoT"
    if tech_set & AI_TECHS:
        has_be = bool(tech_set & BACKEND_TECHS); has_fe = bool(tech_set & FRONTEND_TECHS)
        return "AI Full Stack" if (has_be and has_fe) else "AI"
    if any(t in tech_set for t in ["Flutter","React Native","Kotlin","Swift"]):
        return "Mobile"
    if tech_set & CLOUD_TECHS and not (tech_set & FRONTEND_TECHS or tech_set & BACKEND_TECHS):
        return "Cloud/DevOps"
    has_be = bool(tech_set & BACKEND_TECHS); has_fe = bool(tech_set & FRONTEND_TECHS)
    has_db = bool(tech_set & DB_TECHS)
    if has_be and has_fe: return "Full Stack"
    if has_be and has_db: return "Backend"
    if has_fe: return "Frontend"
    if has_be: return "Backend"
    if has_db: return "Backend"
    return "General"


def _score_complexity(techs: List[str], bullets: List[str]) -> int:
    tech_set = set(techs)
    all_text = " ".join(bullets).lower()
    score = 0
    if tech_set & DB_TECHS:                             score += COMPLEXITY_RUBRIC["database"]
    if tech_set & {"JWT","OAuth2","OAuth"}:              score += COMPLEXITY_RUBRIC["auth"]
    if any(k in all_text for k in ["deploy","cloud","vercel","heroku","aws","railway"]):
        score += COMPLEXITY_RUBRIC["cloud_deploy"]
    if tech_set & {"WebSocket","Firebase","Redis"}:      score += COMPLEXITY_RUBRIC["realtime"]
    if tech_set & AI_TECHS:                              score += COMPLEXITY_RUBRIC["ai_ml"]
    if tech_set & {"REST APIs","GraphQL","gRPC"}:        score += COMPLEXITY_RUBRIC["rest_api"]
    if len(techs) >= 4:                                  score += COMPLEXITY_RUBRIC["multi_tech"]
    if any(k in all_text for k in ["test","pytest","jest"]): score += COMPLEXITY_RUBRIC["testing"]
    if tech_set & IOT_TECHS:                             score += COMPLEXITY_RUBRIC["iot"]
    if tech_set & {"CI/CD","GitHub Actions","Jenkins"}:  score += COMPLEXITY_RUBRIC["ci_cd"]
    if tech_set & {"Docker","Kubernetes"}:               score += COMPLEXITY_RUBRIC["containerized"]
    if tech_set & FRONTEND_TECHS:                        score += COMPLEXITY_RUBRIC["frontend"]
    if tech_set & BACKEND_TECHS:                         score += COMPLEXITY_RUBRIC["backend"]
    return min(100, score)


def _infer_capabilities(techs: List[str], bullets: List[str]) -> List[str]:
    caps: Set[str] = set()
    for tech in techs:
        for cap in TECH_IMPLIES.get(tech, []):
            caps.add(cap)
    all_text = " ".join(bullets).lower()
    if "real-time" in all_text or "realtime" in all_text or "websocket" in all_text:
        caps.add("Real-time Systems")
    if "authentication" in all_text or "login" in all_text or "jwt" in all_text:
        caps.add("Authentication")
    if "dashboard" in all_text or "visualization" in all_text:
        caps.add("Data Visualization")
    if "api" in all_text:
        caps.add("API Development")
    if "deploy" in all_text or "cloud" in all_text:
        caps.add("Cloud Deployment")
    if "test" in all_text:
        caps.add("Testing")
    return sorted(caps)


def _build_skill_evidence(techs, project_name, bullets, raw_lines):
    evidence, best = [], {}
    for i, line in enumerate(raw_lines):
        if TECH_HEADER_RE.match(line.strip()):
            for tech in techs:
                if tech.lower() in line.lower() or _normalize_tech(tech.lower()) == tech:
                    ev = {"skill": tech, "source": "tech_stack_declaration",
                          "section": "projects", "project": project_name,
                          "confidence": 90, "line_number": i}
                    if tech not in best or 90 > best[tech]["confidence"]:
                        best[tech] = ev
            break
    for i, bullet in enumerate(bullets):
        lower = bullet.lower()
        verb_conf = 80
        for verb, conf in ACTION_CONFIDENCE.items():
            if lower.strip().startswith(verb):
                verb_conf = conf; break
        for tech in _extract_tech_from_freetext(bullet):
            ev = {"skill": tech, "source": "project_bullet",
                  "section": "projects", "project": project_name,
                  "confidence": verb_conf, "line_number": i}
            if tech not in best or verb_conf > best[tech]["confidence"]:
                best[tech] = ev
    return list(best.values())


# ── Core grouping algorithm ───────────────────────────────────────────────────

# Section header keywords — if we see one of these, stop the current project section
SECTION_STOP_WORDS = re.compile(
    r"^(experience|education|skills|certifications?|leadership|awards?|"
    r"volunteer|honors?|scholarships?|publications?|research|hackathons?|"
    r"open\s*source|about|summary|objective|contact|references?|"
    r"positions?\s*of\s*responsibility|extracurricular|activities)\s*$",
    re.IGNORECASE,
)


def _is_section_stop(line: str) -> bool:
    return bool(SECTION_STOP_WORDS.match(line.strip()))


def _group_raw_lines_into_projects(lines: List[str]) -> List[List[str]]:
    """
    Group consecutive lines into project blocks.

    Rules (in priority order):
      1. Section header line → stop. (Should not appear inside a projects block
         but can appear in raw_lines if ownership engine is loose.)
      2. Tech-header line (TechStack:, Built with:, etc.) → belongs to current project.
      3. Link/URL line (GitHub, Live Demo, https://...) → belongs to current project.
      4. Bullet line → belongs to current project.
      5. Continuation line (starts lowercase, starts with and/with/for, etc.) → append.
      6. Previous line ended with hyphen → append (wrapped word).
      7. Blank line → does NOT end a project (projects span blank lines).
      8. New title-case short non-sentence line → starts new project.
    """
    # Strip the section header ("Projects", "Portfolio", etc.)
    content: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            content.append("")  # preserve blanks for context
            continue
        lower = stripped.lower()
        if lower in ("projects","project","portfolio","open source contributions",
                     "personal projects","academic projects","side projects"):
            continue
        content.append(stripped)

    if not content:
        return []

    groups: List[List[str]] = []
    current: List[str] = []
    prev_nonempty: str = ""

    for line in content:
        stripped = line.strip()

        # ── Blank line: does NOT end a project ────────────────────────
        if not stripped:
            if current:
                current.append("")  # keep blank in raw_lines for later
            continue

        # ── Section stop (shouldn't happen but be safe) ────────────────
        if _is_section_stop(stripped):
            if current:
                groups.append([l for l in current if l])
                current = []
            prev_nonempty = stripped
            continue

        # ── Tech-header, link, or bullet → always attach to current ───
        if (_is_tech_header_line(stripped)
                or _is_link_line(stripped)
                or BULLET_RE.match(stripped)):
            if not current:
                current = [stripped]
            else:
                current.append(stripped)
            prev_nonempty = stripped
            continue

        # ── Continuation line → attach to current ─────────────────────
        if is_continuation(stripped, prev_nonempty):
            if current:
                current.append(stripped)
            else:
                current = [stripped]
            prev_nonempty = stripped
            continue

        # ── This looks like a new project title ───────────────────────
        if _looks_like_project_title(stripped):
            if current:
                groups.append([l for l in current if l])
                current = []
            current = [stripped]
            prev_nonempty = stripped
            continue

        # ── Fallback: attach to current block ─────────────────────────
        if current:
            current.append(stripped)
        else:
            current = [stripped]
        prev_nonempty = stripped

    if current:
        groups.append([l for l in current if l])

    return [g for g in groups if g]


# ── Single project parser ─────────────────────────────────────────────────────

def _parse_single_project(group: List[str]) -> Optional[Dict[str, Any]]:
    if not group:
        return None

    name: Optional[str] = None
    tech_from_header: List[str] = []
    tech_from_bullets: List[str] = []
    tech_from_name: List[str] = []
    bullets: List[str] = []
    description_parts: List[str] = []
    github: Optional[str] = None
    live_demo: Optional[str] = None
    deployment: Optional[str] = None

    prev_line = ""
    for line in group:
        stripped = line.strip()
        if not stripped:
            prev_line = stripped
            continue

        # ── Tech-stack header line ────────────────────────────────────
        m = TECH_HEADER_RE.match(stripped)
        if m:
            payload = m.group(1).strip()
            tech_from_header = _merge_techs(
                tech_from_header,
                _extract_tech_from_csv(payload),
                _extract_tech_from_freetext(payload),
            )
            prev_line = stripped
            continue

        # ── Link / URL line ───────────────────────────────────────────
        if _is_link_line(stripped):
            urls = _classify_url_line(stripped)
            github    = github    or urls["github"]
            live_demo = live_demo or urls["live_demo"]
            deployment= deployment or urls["deployment"]
            prev_line = stripped
            continue

        # ── Bullet line ───────────────────────────────────────────────
        if BULLET_RE.match(stripped):
            content = BULLET_RE.sub("", stripped).strip()
            # Merge with previous bullet if that ended with hyphen
            if (bullets and prev_line.rstrip().endswith("-")):
                bullets[-1] = bullets[-1].rstrip("-") + content
            elif content:
                bullets.append(content)
            tech_from_bullets.extend(_extract_tech_from_freetext(content))
            prev_line = stripped
            continue

        # ── Continuation (lowercase / and/with/for / previous hyphen) ─
        if is_continuation(stripped, prev_line):
            # Append to last bullet or description
            if bullets and (prev_line.startswith("•") or BULLET_RE.match(prev_line)):
                bullets[-1] = bullets[-1].rstrip("-") + " " + stripped
            elif description_parts:
                description_parts[-1] = description_parts[-1].rstrip("-") + " " + stripped
            elif name is not None:
                description_parts.append(stripped)
            tech_from_bullets.extend(_extract_tech_from_freetext(stripped))
            prev_line = stripped
            continue

        # ── Project name or description ───────────────────────────────
        if name is None:
            name = stripped
            tech_from_name = _extract_tech_from_freetext(stripped)
        else:
            # Could be a description sentence
            description_parts.append(stripped)
            tech_from_bullets.extend(_extract_tech_from_freetext(stripped))

        prev_line = stripped

    # Reject if name is itself a tech header or link label
    if name and (_is_tech_header_line(name) or _is_link_line(name)):
        return None
    if name is None:
        return None

    # Merge technologies
    technologies = _merge_techs(tech_from_header, tech_from_bullets, tech_from_name)

    # Build description
    description = " ".join(description_parts).strip() if description_parts else (bullets[0] if bullets else None)

    inferred_capabilities = _infer_capabilities(technologies, bullets)
    domain                = _classify_domain(technologies)
    complexity            = _score_complexity(technologies, bullets)
    skill_evidence        = _build_skill_evidence(technologies, name or "", bullets, group)

    return {
        # Backward-compatible core fields
        "name":                  name,
        "description":           description,
        "technologies":          technologies,
        "bullets":               bullets,
        "url":                   live_demo or github,
        "raw_lines":             group,
        # Phase 1.5+ enriched fields
        "github":                github,
        "live_demo":             live_demo,
        "deployment":            deployment,
        "inferred_capabilities": inferred_capabilities,
        "domain":                domain,
        "complexity":            complexity,
        "skill_evidence":        skill_evidence,
        "knowledge_graph": {
            "project":        name,
            "technologies":   technologies,
            "capabilities":   inferred_capabilities,
            "domain":         domain,
        },
    }


# ── Public API ────────────────────────────────────────────────────────────────

def extract_projects(raw_lines: List[str]) -> List[Dict[str, Any]]:
    """Main entry point. Returns list of project dicts; never emits TechStack as a project."""
    groups  = _group_raw_lines_into_projects(raw_lines)
    results = []
    for group in groups:
        parsed = _parse_single_project(group)
        if parsed is not None:
            results.append(parsed)
    return results


def build_resume_knowledge_graph(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build cross-project knowledge graph (resume-level)."""
    all_techs:   Set[str] = set()
    all_caps:    Set[str] = set()
    all_domains: Set[str] = set()
    for proj in projects:
        all_techs.update(proj.get("technologies", []))
        all_caps.update(proj.get("inferred_capabilities", []))
        domain = proj.get("domain")
        if domain:
            all_domains.add(domain)
    for tech in list(all_techs):
        for cap in TECH_IMPLIES.get(tech, []):
            all_caps.add(cap)
    return {
        "projects":            [p["name"] for p in projects if p.get("name")],
        "all_technologies":    sorted(all_techs),
        "all_capabilities":    sorted(all_caps),
        "all_domains":         sorted(all_domains),
        "cross_project_techs": sorted(all_techs),
    }
