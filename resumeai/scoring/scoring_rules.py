"""
scoring_rules.py — Deterministic scoring functions for ATS Scorer v2.
"""

import re
from typing import Dict, List, Any, Tuple

# Contact: Returns 0-100
def score_contact(contact: Dict[str, Any]) -> float:
    score = 0
    if contact.get("name"): score += 20
    if contact.get("email"): score += 20
    if contact.get("phone"): score += 20
    
    linkedin = contact.get("linkedin")
    github = contact.get("github")
    other = " ".join(contact.get("other_links", [])).lower()
    
    if linkedin or "linkedin" in other: score += 20
    if github or "github" in other: score += 20
    return min(100.0, float(score))

# Education: Returns (Base 0-100, Bonus)
def score_education(
    education: List[Dict[str, Any]],
    candidate_type: str = "EXPERIENCED",
) -> Tuple[float, float]:
    if not education:
        return 0.0, 0.0
    score = 0
    has_degree = False
    has_inst = False
    has_year = False
    has_gpa = False
    
    max_cgpa = 0.0
    max_class_xii_pct = 0.0
    
    for edu in education:
        if edu.get("degree"): has_degree = True
        if edu.get("institution"): has_inst = True
        if edu.get("end_date"): has_year = True
        
        raw_text = " ".join(edu.get("raw_lines", []))
        education_text = " ".join(
            str(value or "")
            for value in (edu.get("degree"), edu.get("institution"), raw_text)
        ).lower()
        is_class_xii = any(
            marker in education_text
            for marker in ("12th", "class xii", "class 12", "higher secondary", "senior secondary", "hsc")
        )

        gpa_str = edu.get("gpa")
        if gpa_str:
            has_gpa = True
            try:
                gpa_val = float(re.search(r"[\d\.]+", gpa_str).group())
                if is_class_xii and gpa_val > 10:
                    max_class_xii_pct = max(max_class_xii_pct, gpa_val)
                # Handle /10 scale if gpa > 4.
                elif gpa_val > 4.0:
                    max_cgpa = max(max_cgpa, gpa_val)
                else:
                    # Scale 4.0 to 10.0 for academic threshold logic.
                    max_cgpa = max(max_cgpa, gpa_val * 2.5)
            except (AttributeError, ValueError):
                pass
        
    if has_degree: score += 30
    if has_inst: score += 30
    if has_year: score += 20
    if has_gpa: score += 20
    
    # Fresher academics are evidence of readiness, not merely an optional extra.
    # Strong CGPA establishes a floor even when a date or another metadata field
    # is absent from an otherwise credible education entry.
    if candidate_type == "FRESHER":
        if max_cgpa >= 9.0:
            score = max(score, 100)
        elif max_cgpa >= 8.5:
            score = max(score, 95)

    # Class XII performance is a small, transparent bonus rather than a hidden
    # multiplier. It can add at most one point to a 15-point fresher section.
    bonus = 5.0 if candidate_type == "FRESHER" and max_class_xii_pct > 90 else 0.0
        
    return min(100.0, float(score)), bonus

ACTION_VERBS = {
    "developed", "built", "implemented", "optimized", "designed",
    "created", "led", "engineered", "managed", "delivered", "architected"
}

METRIC_PATTERNS = [
    r"\d+%",
    r"\d+x\b",
    r"\d+\+",
    r"\$\d+",
    r"\d+\s*users",
    r"\d+\s*requests",
    r"\d+\s*records",
    r"\d+\s*ms",
    r"\d+\s*seconds"
]
METRIC_RE = re.compile("|".join(METRIC_PATTERNS), re.IGNORECASE)

ACHIEVEMENT_KEYWORDS = ["bug fixes", "defects", "performance improvement", "pr", "pull request", "open-source", "open source"]

# Experience: Returns (Base 0-100, Bonus)
def score_experience(experience: List[Dict[str, Any]]) -> Tuple[float, float]:
    if not experience:
        return 0.0, 0.0
    
    count = len(experience)
    count_score = 40 if count >= 3 else (25 if count == 2 else 15)
    
    all_text = ""
    for exp in experience:
        all_text += " ".join(exp.get("bullets", [])) + " "
        if exp.get("description"):
            all_text += exp["description"] + " "
            
    all_text_lower = all_text.lower()
    
    verbs_found = sum(1 for verb in ACTION_VERBS if f"{verb} " in all_text_lower)
    verb_score = 30 if verbs_found >= 5 else (20 if verbs_found >= 3 else (10 if verbs_found >= 1 else 0))
    
    quantified_matches = len(METRIC_RE.findall(all_text_lower))
    quant_score = 30 if quantified_matches >= 3 else (20 if quantified_matches == 2 else (10 if quantified_matches == 1 else 0))
    
    # Internship Achievement Bonus (separated to prevent clipping)
    bonus = float(sum(5 for kw in ACHIEVEMENT_KEYWORDS if kw in all_text_lower))
            
    return min(100.0, float(count_score + verb_score + quant_score)), bonus

TECHNICAL_CAPABILITIES = {
    "full_stack": {
        "full stack", "full-stack", "frontend", "backend", "react", "angular",
        "vue", "node.js", "django", "flask", "fastapi", "spring", "ui", "ux",
        "html", "css", "javascript", "typescript", "tailwind", "bootstrap"
    },
    "api_integration": {
        "api", "rest", "restful", "graphql", "webhook", "third-party",
        "integration", "oauth", "jwt"
    },
    "ai_llm": {
        "gemini api", "openai api", "claude api", "langchain", "rag", 
        "vector database", "prompt engineering", "openai", "gemini", 
        "claude", "llm", "large language model", "generative ai"
    },
    "machine_learning": {
        "machine learning", "deep learning", "artificial intelligence", " ai ",
        "nlp", "computer vision", "tensorflow", "pytorch", "scikit-learn",
        "xgboost", "recommendation systems", "recommendation engine", "chatbot"
    },
    "backend": {
        "fastapi", "flask", "django", "node.js", "rest api", "graphql", "microservices",
        "express", "spring boot", "ruby on rails", ".net"
    },
    "cloud_devops": {
        "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "google cloud",
        "cloud", "serverless", "lambda", "terraform", "github actions", "gitlab ci"
    },
    "data_engineering": {
        "spark", "kafka", "airflow", "distributed systems", "hadoop", "data pipeline",
        "etl", "data warehouse", "snowflake", "bigquery"
    },
    "iot": {
        "iot", "internet of things", "arduino", "raspberry pi", "sensor",
        "mqtt", "embedded", "esp32", "real-time monitoring", "edge computing"
    },
    "database": {
        "database", "sql", "nosql", "postgresql", "mysql", "mongodb", "redis",
        "schema", "data model", "cassandra", "dynamodb", "elasticsearch"
    },
    "real_time": {
        "real-time", "real time", "websocket", "socket.io", "streaming",
        "kafka", "event-driven", "pub/sub", "websockets"
    }
}

IMPLEMENTATION_VERBS = ACTION_VERBS | {
    "integrated", "deployed", "trained", "tested", "modeled", "automated",
    "configured", "containerized", "streamed", "secured",
}

ARCHITECTURE_TERMS = {
    "architecture", "microservices", "client-server", "event-driven",
    "pipeline", "schema", "authentication", "authorization", "caching",
    "queue", "websocket", "containerized", "ci/cd", "cicd", "rbac",
    "profile management", "real-time updates", "websockets", "notifications",
    "matching engine", "recommendation engine", "payment integration",
    "analytics", "dashboard", "monitoring"
}

DEPLOYMENT_DOMAINS = [
    "vercel.app", "netlify.app", "render.com", "railway.app", "fly.io", 
    "herokuapp.com", "azurewebsites.net", "cloudfront.net", "firebaseapp.com",
    "aws", "azure", "gcp", "digitalocean"
]

TECH_FALLBACK_KEYWORDS = set().union(*TECHNICAL_CAPABILITIES.values())

IMPACT_VERBS = {
    "built", "trained", "processed", "served", "deployed", "optimized",
    "generated", "handled", "reduced", "improved", "created", "implemented", "engineered"
}

EXPANDED_METRIC_PATTERNS = [
    r"\d+",
    r"\d+\s+models",
    r"\d+\s+pipelines",
    r"\d+\s+apis",
    r"\d+\s+services",
    r"\d+\s+datasets",
    r"\d+\s+records",
    r"\d+\s+files",
]
EXPANDED_METRIC_RE = re.compile("|".join(EXPANDED_METRIC_PATTERNS), re.IGNORECASE)

# Projects: Returns structured dict
def score_projects(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not projects:
        return {
            "overall_score": 0,
            "project_count": 0,
            "average_project_score": 0,
            "strongest_project": "None",
            "weakest_project": "None",
            "breakdowns": []
        }

    breakdowns = []
    
    for proj in projects:
        name = proj.get("name", "Unnamed Project")
        desc = proj.get("description") or ""
        bullets = proj.get("bullets", [])
        tech_array = proj.get("technologies", [])
        url = (proj.get("url") or "").lower()
        
        # Unified text corpus for detection
        metadata_str = json.dumps(proj.get("metadata", {})) if isinstance(proj.get("metadata"), dict) else ""
        all_text = f"{name} {desc} {' '.join(bullets)} {' '.join(tech_array)} {url} {metadata_str}"
        all_text_lower = all_text.lower()
        
        # 1. Parser Confidence (0.0 to 1.0)
        conf = 0.0
        if name and name != "Unnamed Project": conf += 0.2
        if tech_array: conf += 0.2
        if bullets: conf += 0.2
        if url: conf += 0.2
        if desc: conf += 0.2
        parser_confidence = min(1.0, conf)
        
        # 2. Tech Stack Diversity (15)
        unique_techs = sum(1 for kw in TECH_FALLBACK_KEYWORDS if kw in all_text_lower)
        tech_stack_diversity = min(15, unique_techs * 3)
        
        # 3. Documentation Quality (10)
        doc_score_explicit = min(10, len(bullets) * 4) if bullets else 0
        
        sentences = all_text.count(".") + all_text.count("!") + all_text.count("?")
        words = len(all_text.split())
        newlines = all_text.count("\n")
        bullet_chars = sum(1 for c in all_text if c in ["•", "-", "*"])
        action_verbs_found = sum(1 for verb in ACTION_VERBS if f"{verb} " in all_text_lower)
        
        doc_score_fallback = 0
        if sentences >= 3 or words >= 30: doc_score_fallback += 4
        if newlines >= 2 or bullet_chars >= 2: doc_score_fallback += 3
        if action_verbs_found >= 2: doc_score_fallback += 3
        
        documentation = max(doc_score_explicit, min(10, doc_score_fallback))
            
        # 4. GitHub Presence (3)
        has_github = "github.com" in url or "github.com" in all_text_lower
        github = 3 if has_github else 0
        
        # 5. Deployment Evidence (5)
        deployed = any(domain in url for domain in DEPLOYMENT_DOMAINS if domain != "github.com")
        if not deployed:
            deployed = any(domain in all_text_lower for domain in DEPLOYMENT_DOMAINS if domain != "github.com")
        deployment = 5 if deployed else 0
        
        # 6. Technical Complexity (30)
        detected_categories = {
            cap
            for cap, keywords in TECHNICAL_CAPABILITIES.items()
            if any(keyword in all_text_lower for keyword in keywords)
        }
        
        complexity_base = len(detected_categories) * 5
        
        # Engineering Complexity Multipliers
        multiplier = 0
        active_multipliers = []
        cats = detected_categories
        if "ai_llm" in cats and "backend" in cats: 
            multiplier += 5
            active_multipliers.append("AI/LLM + Backend (+5)")
        if "ai_llm" in cats and "cloud_devops" in cats: 
            multiplier += 5
            active_multipliers.append("AI/LLM + Cloud (+5)")
        if "iot" in cats and "real_time" in cats: 
            multiplier += 5
            active_multipliers.append("IoT + Real-Time (+5)")
        if "full_stack" in cats and "database" in cats: 
            multiplier += 3
            active_multipliers.append("Full Stack + Database (+3)")
        if "cloud_devops" in cats and ("backend" in cats or "distributed_devops" in cats): 
            multiplier += 3
            active_multipliers.append("Cloud/DevOps + Backend (+3)")
        if "data_engineering" in cats and "cloud_devops" in cats: 
            multiplier += 3
            active_multipliers.append("Data Engineering + Cloud (+3)")
        
        technical_complexity = min(30, complexity_base + multiplier)
        
        # 7. Implementation Depth (25)
        impl_verbs = sum(1 for verb in IMPLEMENTATION_VERBS if f"{verb} " in all_text_lower)
        arch_terms = sum(1 for term in ARCHITECTURE_TERMS if term in all_text_lower)
        implementation_depth = min(25, (impl_verbs * 2) + (arch_terms * 5))
        
        # 8. Metrics Quality & Impact
        # Check if numbers are near impact verbs
        words_list = all_text_lower.split()
        metrics = 0
        project_impact = 0
        
        for i, word in enumerate(words_list):
            if word in IMPACT_VERBS:
                neighborhood = " ".join(words_list[max(0, i-5):min(len(words_list), i+6)])
                
                # Impact signals (10)
                if any(sig in neighborhood for sig in ["user", "record", "request", "latency", "accuracy", "cost", "speed", "%", "x", "million", "k"]):
                    project_impact += 5
                
                # Metrics signals (2)
                if EXPANDED_METRIC_RE.search(neighborhood):
                    metrics += 1
                    
        metrics = min(2, round(metrics))
        project_impact = min(10, round(project_impact))
        
        total = sum([technical_complexity, implementation_depth, tech_stack_diversity, documentation, github, deployment, metrics, project_impact])
        
        breakdowns.append({
            "project_name": name,
            "parser_confidence": round(parser_confidence, 2),
            "technical_complexity": technical_complexity,
            "implementation_depth": implementation_depth,
            "tech_stack_diversity": tech_stack_diversity,
            "documentation": documentation,
            "project_impact": project_impact,
            "deployment": deployment,
            "github": github,
            "metrics": metrics,
            "complexity_multipliers": active_multipliers,
            "complexity_base": complexity_base,
            "total": total
        })
        
    project_count = len(breakdowns)
    sorted_projects = sorted(breakdowns, key=lambda x: x["total"], reverse=True)
    strongest = sorted_projects[0]
    weakest = sorted_projects[-1]
    
    avg_score = sum(b["total"] for b in breakdowns) / project_count
    
    # Weighted sum favoring strong projects
    if project_count == 1:
        overall_score = sorted_projects[0]["total"]
    elif project_count == 2:
        overall_score = (sorted_projects[0]["total"] * 0.7) + (sorted_projects[1]["total"] * 0.4)
    else:
        overall_score = (sorted_projects[0]["total"] * 0.6) + (sorted_projects[1]["total"] * 0.3) + (sorted_projects[2]["total"] * 0.2)
        
    # Bonus for >3 projects
    if project_count > 3:
        overall_score += (project_count - 3) * 5

    overall_score = min(100, round(overall_score))

    return {
        "overall_score": overall_score,
        "project_count": project_count,
        "average_project_score": round(avg_score),
        "strongest_project": strongest["project_name"],
        "weakest_project": weakest["project_name"],
        "breakdowns": sorted_projects
    }

SKILL_CATEGORIES = {
    "Languages": {"python", "java", "c++", "javascript", "typescript", "c#", "ruby", "go", "rust", "php"},
    "Frameworks": {"react", "node.js", "django", "flask", "spring", "angular", "vue", "fastapi"},
    "Databases": {"sql", "mongodb", "postgresql", "mysql", "redis", "elasticsearch"},
    "Cloud": {"aws", "azure", "gcp", "google cloud"},
    "DevOps": {"docker", "kubernetes", "jenkins", "cicd", "terraform"},
    "AI/ML": {"machine learning", "deep learning", "tensorflow", "pytorch", "nlp", "computer vision", "llm"}
}

# Skills: Returns (Score 0-100, Diversity Score 0-10)
def score_skills(skills: Dict[str, Any]) -> Tuple[float, int]:
    flat_list = [s.lower() for s in skills.get("flat_list", [])]
    count = len(flat_list)
    
    pct = 0.0
    if count >= 20: pct = 100.0
    elif count >= 15: pct = 80.0
    elif count >= 10: pct = 60.0
    elif count >= 5: pct = 40.0
    elif count > 0: pct = 20.0
    
    detected_cats = set()
    for skill in flat_list:
        for cat, kw_set in SKILL_CATEGORIES.items():
            if skill in kw_set or any(kw in skill for kw in kw_set):
                detected_cats.add(cat)
                
    diversity_score = min(10, len(detected_cats) * 2)
    return pct, diversity_score

TECH_KEYWORDS = {
    "python", "java", "c++", "javascript", "react", "node.js", "aws", "docker",
    "kubernetes", "sql", "mongodb", "postgresql", "machine learning", "data science",
    "git", "github", "azure", "gcp", "django", "flask", "spring", "typescript", "c#"
}

def score_keywords(resume: Dict[str, Any]) -> float:
    text_corpus = ""
    for sec in ["summary"]:
        if resume.get(sec): text_corpus += str(resume[sec]) + " "
    for sec in ["experience", "projects", "education", "leadership", "certifications"]:
        for item in resume.get(sec, []):
            text_corpus += str(item) + " "
    for skill in resume.get("skills", {}).get("flat_list", []):
        text_corpus += skill + " "
        
    text_lower = text_corpus.lower()
    matches = sum(1 for kw in TECH_KEYWORDS if kw in text_lower)
    
    if matches >= 8: return 100.0
    if matches >= 5: return 70.0
    if matches >= 3: return 40.0
    if matches > 0: return 20.0
    return 0.0

def score_certifications_leadership(certs: List[Dict], leadership: List[Dict]) -> float:
    score = 0
    if certs: score += 50
    if leadership: score += 50
    return float(score)

def score_awards(awards: List[Any], text_corpus: str = "") -> float:
    """Awards Section Scoring (Returns 0-100)"""
    score = 0
    if awards:
        score += 40
        
    text_lower = text_corpus.lower()
    award_keywords = ["scholarship", "branch topper", "academic excellence", "competition", "hackathon", "dean's list", "merit"]
    matches = sum(1 for kw in award_keywords if kw in text_lower)
    score += matches * 30
    
    return min(100.0, float(score))

def score_formatting(resume: Dict[str, Any]) -> float:
    score = 100
    
    contact = resume.get("contact", {})
    if not contact.get("name") and not contact.get("email"):
        score -= 50
        
    if not resume.get("skills", {}).get("flat_list"):
        score -= 30
        
    if not resume.get("education"):
        score -= 20
        
    anomalies = resume.get("metadata", {}).get("anomaly_count", 0)
    score -= anomalies * 10
    
    return max(0.0, min(100.0, float(score)))
