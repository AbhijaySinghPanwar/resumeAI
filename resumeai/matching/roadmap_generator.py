"""
matching/roadmap_generator.py — Learning Roadmap Generator for Phase 2.

Maps missing skills to curated learning recommendations.
Deterministic, no external API calls.
"""
from __future__ import annotations

from typing import List, Dict, Optional
from rapidfuzz import fuzz

from .schemas import RoadmapItem


# ── Curated skill → recommendation database ───────────────────────────────────
# Each entry: skill_key (lowercase) → list of RoadmapItem dicts

SKILL_ROADMAP_DB: Dict[str, List[Dict]] = {
    "aws": [
        {
            "resource_type": "certification",
            "recommendation": "AWS Certified Cloud Practitioner (CLF-C02)",
            "url": "https://aws.amazon.com/certification/certified-cloud-practitioner/",
            "estimated_time": "2-4 weeks",
            "difficulty": "Beginner",
        },
        {
            "resource_type": "certification",
            "recommendation": "AWS Certified Solutions Architect – Associate (SAA-C03)",
            "url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/",
            "estimated_time": "2-3 months",
            "difficulty": "Intermediate",
        },
    ],
    "docker": [
        {
            "resource_type": "course",
            "recommendation": "Docker Mastery: with Kubernetes + Swarm (Udemy – Bret Fisher)",
            "url": "https://www.udemy.com/course/docker-mastery/",
            "estimated_time": "3-4 weeks",
            "difficulty": "Beginner–Intermediate",
        },
        {
            "resource_type": "project",
            "recommendation": "Containerize a personal project and push to Docker Hub",
            "url": "https://hub.docker.com/",
            "estimated_time": "1 weekend",
            "difficulty": "Beginner",
        },
    ],
    "kubernetes": [
        {
            "resource_type": "certification",
            "recommendation": "Certified Kubernetes Application Developer (CKAD)",
            "url": "https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/",
            "estimated_time": "2-3 months",
            "difficulty": "Intermediate",
        },
        {
            "resource_type": "course",
            "recommendation": "Kubernetes for the Absolute Beginners (KodeKloud)",
            "url": "https://kodekloud.com/courses/kubernetes-for-the-absolute-beginners-hands-on/",
            "estimated_time": "4-6 weeks",
            "difficulty": "Beginner",
        },
    ],
    "react": [
        {
            "resource_type": "course",
            "recommendation": "The Ultimate React Course 2024 (Udemy – Jonas Schmedtmann)",
            "url": "https://www.udemy.com/course/the-ultimate-react-course/",
            "estimated_time": "6-8 weeks",
            "difficulty": "Beginner–Intermediate",
        },
        {
            "resource_type": "project",
            "recommendation": "Build a full-stack CRUD app using React + Vite + REST API",
            "url": "https://react.dev/learn",
            "estimated_time": "2-3 weeks",
            "difficulty": "Beginner",
        },
    ],
    "fastapi": [
        {
            "resource_type": "course",
            "recommendation": "FastAPI – The Complete Course (TestDriven.io)",
            "url": "https://testdriven.io/courses/tdd-fastapi/",
            "estimated_time": "3-4 weeks",
            "difficulty": "Intermediate",
        },
        {
            "resource_type": "book",
            "recommendation": "FastAPI Official Tutorial (free, interactive)",
            "url": "https://fastapi.tiangolo.com/tutorial/",
            "estimated_time": "1-2 weeks",
            "difficulty": "Beginner",
        },
    ],
    "postgresql": [
        {
            "resource_type": "course",
            "recommendation": "The Complete SQL Bootcamp with Postgres (Udemy – Jose Portilla)",
            "url": "https://www.udemy.com/course/the-complete-sql-bootcamp/",
            "estimated_time": "4-6 weeks",
            "difficulty": "Beginner",
        },
    ],
    "machine learning": [
        {
            "resource_type": "certification",
            "recommendation": "DeepLearning.AI Machine Learning Specialization (Coursera – Andrew Ng)",
            "url": "https://www.coursera.org/specializations/machine-learning-introduction",
            "estimated_time": "3-4 months",
            "difficulty": "Beginner–Intermediate",
        },
    ],
    "pytorch": [
        {
            "resource_type": "course",
            "recommendation": "PyTorch for Deep Learning & Machine Learning (freeCodeCamp)",
            "url": "https://www.youtube.com/watch?v=V_xro1bcAuA",
            "estimated_time": "4-6 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "tensorflow": [
        {
            "resource_type": "certification",
            "recommendation": "TensorFlow Developer Certificate (Google)",
            "url": "https://www.tensorflow.org/certificate",
            "estimated_time": "2-3 months",
            "difficulty": "Intermediate",
        },
    ],
    "langchain": [
        {
            "resource_type": "course",
            "recommendation": "LangChain & Vector Databases in Production (ActiveLoop)",
            "url": "https://learn.activeloop.ai/courses/langchain",
            "estimated_time": "3-4 weeks",
            "difficulty": "Intermediate",
        },
        {
            "resource_type": "project",
            "recommendation": "Build a RAG chatbot using LangChain + Chroma DB",
            "url": "https://python.langchain.com/docs/get_started/introduction",
            "estimated_time": "2 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "llm": [
        {
            "resource_type": "course",
            "recommendation": "Large Language Models (LLMs) Bootcamp (Full Stack Deep Learning)",
            "url": "https://fullstackdeeplearning.com/llm-bootcamp/",
            "estimated_time": "4-6 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "openai": [
        {
            "resource_type": "course",
            "recommendation": "ChatGPT Prompt Engineering for Developers (DeepLearning.AI – Free)",
            "url": "https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/",
            "estimated_time": "1-2 weeks",
            "difficulty": "Beginner",
        },
    ],
    "gcp": [
        {
            "resource_type": "certification",
            "recommendation": "Google Cloud Professional Cloud Architect",
            "url": "https://cloud.google.com/certification/cloud-architect",
            "estimated_time": "2-3 months",
            "difficulty": "Intermediate",
        },
        {
            "resource_type": "certification",
            "recommendation": "Google Cloud Associate Cloud Engineer",
            "url": "https://cloud.google.com/certification/cloud-engineer",
            "estimated_time": "4-6 weeks",
            "difficulty": "Beginner–Intermediate",
        },
    ],
    "azure": [
        {
            "resource_type": "certification",
            "recommendation": "Microsoft Azure Fundamentals (AZ-900)",
            "url": "https://learn.microsoft.com/en-us/certifications/azure-fundamentals/",
            "estimated_time": "2-3 weeks",
            "difficulty": "Beginner",
        },
    ],
    "ci/cd": [
        {
            "resource_type": "course",
            "recommendation": "GitHub Actions – The Complete Guide (Udemy – Maximilian Schwarzmüller)",
            "url": "https://www.udemy.com/course/github-actions-the-complete-guide/",
            "estimated_time": "3-4 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "typescript": [
        {
            "resource_type": "course",
            "recommendation": "TypeScript Course for Beginners (Academind – Free)",
            "url": "https://www.youtube.com/watch?v=BwuLxPH8IDs",
            "estimated_time": "2-3 weeks",
            "difficulty": "Beginner",
        },
    ],
    "javascript": [
        {
            "resource_type": "course",
            "recommendation": "The Complete JavaScript Course 2024 (Udemy – Jonas Schmedtmann)",
            "url": "https://www.udemy.com/course/the-complete-javascript-course/",
            "estimated_time": "6-8 weeks",
            "difficulty": "Beginner-Intermediate",
        },
    ],
    "node.js": [
        {
            "resource_type": "course",
            "recommendation": "Node.js, Express, MongoDB & More (Udemy – Jonas Schmedtmann)",
            "url": "https://www.udemy.com/course/nodejs-express-mongodb-bootcamp/",
            "estimated_time": "6 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "sql": [
        {
            "resource_type": "course",
            "recommendation": "SQL for Data Science (Coursera – UC Davis – Free Audit)",
            "url": "https://www.coursera.org/learn/sql-for-data-science",
            "estimated_time": "4 weeks",
            "difficulty": "Beginner",
        },
    ],
    "mongodb": [
        {
            "resource_type": "certification",
            "recommendation": "MongoDB Certified Developer Associate",
            "url": "https://www.mongodb.com/certification/developer/associate",
            "estimated_time": "4-6 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "apache spark": [
        {
            "resource_type": "course",
            "recommendation": "Spark and Python for Big Data with PySpark (Udemy – Jose Portilla)",
            "url": "https://www.udemy.com/course/spark-and-python-for-big-data-with-pyspark/",
            "estimated_time": "4-6 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "apache kafka": [
        {
            "resource_type": "course",
            "recommendation": "Apache Kafka Series – Learn Apache Kafka for Beginners (Udemy)",
            "url": "https://www.udemy.com/course/apache-kafka/",
            "estimated_time": "4 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "rag": [
        {
            "resource_type": "course",
            "recommendation": "Building Systems with the ChatGPT API (DeepLearning.AI – Free)",
            "url": "https://www.deeplearning.ai/short-courses/building-systems-with-chatgpt/",
            "estimated_time": "1-2 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "graphql": [
        {
            "resource_type": "course",
            "recommendation": "GraphQL with React: The Complete Developers Guide (Udemy)",
            "url": "https://www.udemy.com/course/graphql-with-react-course/",
            "estimated_time": "3-4 weeks",
            "difficulty": "Intermediate",
        },
    ],
    "microservices": [
        {
            "resource_type": "course",
            "recommendation": "Microservices with Node.js and React (Udemy – Stephen Grider)",
            "url": "https://www.udemy.com/course/microservices-with-node-js-and-react/",
            "estimated_time": "6-8 weeks",
            "difficulty": "Advanced",
        },
    ],
    "nlp": [
        {
            "resource_type": "course",
            "recommendation": "Natural Language Processing Specialization (Coursera – DeepLearning.AI)",
            "url": "https://www.coursera.org/specializations/natural-language-processing",
            "estimated_time": "4 months",
            "difficulty": "Intermediate",
        },
    ],
    "python": [
        {
            "resource_type": "course",
            "recommendation": "100 Days of Code: The Complete Python Pro Bootcamp (Udemy – Angela Yu)",
            "url": "https://www.udemy.com/course/100-days-of-code/",
            "estimated_time": "100 days",
            "difficulty": "Beginner",
        },
    ],
    "java": [
        {
            "resource_type": "course",
            "recommendation": "Java Programming Masterclass (Udemy – Tim Buchalka)",
            "url": "https://www.udemy.com/course/java-the-complete-java-developer-course/",
            "estimated_time": "2-3 months",
            "difficulty": "Beginner–Intermediate",
        },
    ],
}

# ── Alias mapping for lookup ──────────────────────────────────────────────────
SKILL_ALIASES: Dict[str, str] = {
    "react.js": "react",
    "reactjs": "react",
    "nodejs": "node.js",
    "node js": "node.js",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "gpt": "openai",
    "chatgpt": "openai",
    "gemini api": "openai",   # similar resource type
    "langchain": "langchain",
    "apache spark": "apache spark",
    "pyspark": "apache spark",
    "kafka": "apache kafka",
    "airflow": "apache kafka",  # suggest kafka for data pipeline skills
    "typescript": "typescript",
}


def _lookup_skill(skill: str) -> Optional[str]:
    """
    Find the best matching key in SKILL_ROADMAP_DB for a given skill.
    Uses exact match, alias lookup, then fuzzy match as fallback.
    """
    key = skill.strip().lower()

    # Exact
    if key in SKILL_ROADMAP_DB:
        return key

    # Alias
    alias_key = SKILL_ALIASES.get(key)
    if alias_key and alias_key in SKILL_ROADMAP_DB:
        return alias_key

    # Fuzzy match against DB keys
    best_match = None
    best_score = 0
    for db_key in SKILL_ROADMAP_DB:
        score = fuzz.token_sort_ratio(key, db_key)
        if score > best_score and score >= 80:
            best_score = score
            best_match = db_key

    return best_match


def generate_learning_roadmap(missing_skills: List[str]) -> List[RoadmapItem]:
    """
    Generate a curated learning roadmap for a list of missing skills.

    Args:
        missing_skills: List of skill strings that are absent from the resume

    Returns:
        List of RoadmapItem — top recommendations per skill, deduplicated
    """
    items: List[RoadmapItem] = []
    seen_recommendations: set = set()

    for skill in missing_skills:
        db_key = _lookup_skill(skill)

        if db_key:
            recs = SKILL_ROADMAP_DB[db_key]
            # Take the first (best) recommendation per skill
            for rec in recs[:1]:
                if rec["recommendation"] not in seen_recommendations:
                    items.append(RoadmapItem(
                        skill=skill,
                        resource_type=rec["resource_type"],
                        recommendation=rec["recommendation"],
                        url=rec.get("url"),
                        estimated_time=rec.get("estimated_time"),
                        difficulty=rec.get("difficulty"),
                    ))
                    seen_recommendations.add(rec["recommendation"])
        else:
            # Generic fallback — no curated recommendation
            generic_rec = f"Search for '{skill}' courses on Coursera, Udemy, or YouTube"
            if generic_rec not in seen_recommendations:
                items.append(RoadmapItem(
                    skill=skill,
                    resource_type="course",
                    recommendation=generic_rec,
                    url="https://www.coursera.org/search?query=" + skill.replace(" ", "+"),
                    estimated_time="4-6 weeks",
                    difficulty="Varies",
                ))
                seen_recommendations.add(generic_rec)

    return items
