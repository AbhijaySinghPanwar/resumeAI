"""
projects.py — Extract project entries from projects section blocks.
"""

import re
from typing import Dict, List, Optional

from resumeai.extractors.date_utils import extract_years

BULLET_RE = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"github\.com/[\w\-/]+", re.IGNORECASE)

TECH_KEYWORDS = [
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "nodejs", "django", "flask", "fastapi", "spring", "express",
    "tensorflow", "pytorch", "keras", "scikit", "pandas", "numpy",
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "docker", "kubernetes", "aws", "gcp", "azure", "git", "linux",
    "html", "css", "rest", "api", "graphql", "grpc", "kafka",
    "c++", "c#", "golang", "go", "rust", "swift", "kotlin", "r",
    "langchain", "openai", "huggingface", "llm", "rag", "bert",
]

TECH_MARKER_RE = re.compile(
    r"(?:tech(?:nologies)?|stack|tools?|built with|using|technologies used)[:\s]+(.+)",
    re.IGNORECASE,
)


def extract_projects(raw_lines: List[str]) -> List[Dict]:
    content_lines = _get_content_lines(raw_lines)
    groups = _group_into_entries(content_lines)
    return [e for e in (_parse_entry(g) for g in groups) if e]


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    if any(kw in first_lower for kw in ["project", "portfolio", "open source"]) and len(lines[0].strip()) < 40:
        return lines[1:]
    return lines


def _is_project_header(line: str) -> bool:
    """Heuristic: does this look like a project name line?"""
    stripped = line.strip()
    if not stripped or BULLET_RE.match(stripped):
        return False
    # Project names are usually short, no terminal punctuation
    if len(stripped) > 80 or stripped.endswith((".", ",", ";")):
        return False
    # Not a pure date line
    if re.match(r"^[\d\s\-–—/]+$", stripped):
        return False
    return True


def _group_into_entries(lines: List[str]) -> List[List[str]]:
    if not lines:
        return []
    groups: List[List[str]] = []
    current: List[str] = []

    def calc_affinity(current_group: List[str], next_line: str) -> float:
        stripped = next_line.strip()
        lower = stripped.lower()
        
        if BULLET_RE.match(stripped):
            return 1.0
            
        if URL_RE.search(stripped) or GITHUB_RE.search(stripped) or "github" in lower or "link" in lower:
            return 0.8
            
        if TECH_MARKER_RE.search(stripped) or any(kw in lower for kw in ["tech stack", "technologies", "built with", "using"]):
            return 0.8
            
        words = stripped.split()
        is_title_case = all(w[0].isupper() for w in words if w.isalpha() and len(w) > 2)
        if 1 <= len(words) <= 8 and not stripped.endswith(('.', ',')) and is_title_case:
            return -1.0 
            
        # If it looks like "Project Name - Tech, Tech", it's a new project title
        dash_split = re.split(r"\s+[\-\u2013\u2014]\s+", stripped, maxsplit=1)
        if len(dash_split) > 1:
            pre_dash = dash_split[0]
            pre_words = pre_dash.split()
            if pre_words and all(w[0].isupper() for w in pre_words if w.isalpha() and len(w) > 2):
                return -1.0
                
        tech_hits = sum(1 for kw in TECH_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", lower))
        if tech_hits >= 2:
            return 0.6
            
        if len(stripped) > 40 or stripped.endswith('.'):
            return 0.5
            
        if len(current_group) == 1:
            return 0.4
            
        return 0.0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                groups.append(current)
                current = []
            continue

        if not current:
            current.append(stripped)
            continue
            
        affinity = calc_affinity(current, stripped)
        
        if affinity < 0.2:
            groups.append(current)
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        groups.append(current)
    return groups


def _parse_entry(lines: List[str]) -> Optional[Dict]:
    if not lines:
        return None

    bullets = []
    name_line = None
    tech_line = None
    url = None

    for line in lines:
        stripped = line.strip()
        # Check for URL
        url_m = URL_RE.search(stripped)
        if url_m and url is None:
            url = url_m.group(0)

        if BULLET_RE.match(stripped):
            content = BULLET_RE.sub("", stripped).strip()
            # Check if bullet is actually a tech stack declaration
            tech_m = TECH_MARKER_RE.match(content)
            if tech_m:
                tech_line = tech_m.group(1)
            else:
                bullets.append(content)
        elif name_line is None:
            name_line = stripped

    # Extract technologies from tech line or from bullets/name
    technologies = _extract_technologies(
        " ".join(filter(None, [tech_line, name_line, " ".join(bullets)]))
    )

    # Description: first bullet or first substantive content
    description = bullets[0] if bullets else None

    return {
        "name": name_line,
        "description": description,
        "technologies": technologies,
        "url": url,
        "bullets": bullets,
        "raw_lines": lines,
    }


def _extract_technologies(text: str) -> List[str]:
    """Find known technology keywords in text."""
    text_lower = text.lower()
    found = []
    for tech in TECH_KEYWORDS:
        # Use word boundary matching
        pattern = rf"\b{re.escape(tech)}\b"
        if re.search(pattern, text_lower):
            found.append(tech)
    return found
