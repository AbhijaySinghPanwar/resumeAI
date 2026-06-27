import json
import os

def expand_ontology():
    ontology_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resumeai", "matching", "skill_ontology.json"))
    
    with open(ontology_path, "r", encoding="utf-8") as f:
        ontology = json.load(f)
        
    # 1. Expand Domains
    new_domains = {
        "Data Science": {
            "weights": {"Python": 15, "R": 12, "Machine Learning": 10, "Pandas": 10, "Statistics": 12},
            "boosted_families": ["Data Science", "AI"]
        },
        "AI Engineering": {
            "weights": {"Python": 15, "Deep Learning": 15, "PyTorch": 12, "LLM": 12, "TensorFlow": 10},
            "boosted_families": ["AI", "Machine Learning"]
        },
        "Full Stack Engineer": {
            "weights": {"JavaScript": 15, "React": 12, "Node.js": 12, "SQL": 10, "REST APIs": 10},
            "boosted_families": ["Frontend", "Backend", "Databases"]
        },
        "Embedded Systems Engineer": {
            "weights": {"C": 15, "C++": 15, "Microcontrollers": 12, "RTOS": 12},
            "boosted_families": ["Embedded"]
        },
        "Game Developer": {
            "weights": {"C++": 15, "C#": 15, "Unity": 12, "Unreal Engine": 12, "3D Math": 10},
            "boosted_families": ["Game Development", "Graphics"]
        }
    }
    ontology["domains"].update(new_domains)
    
    # 2. Add New Categories & Skills
    if "AI & Machine Learning" not in ontology["categories"]:
        ontology["categories"]["AI & Machine Learning"] = {}
        
    ai_skills = {
        "LLM": {"aliases": ["Large Language Models", "Large Language Model"]},
        "Generative AI": {"aliases": ["GenAI"]},
        "Prompt Engineering": {"aliases": []},
        "OpenAI": {"aliases": ["OpenAI API", "GPT-3", "GPT-4"]},
        "Gemini": {"aliases": ["Gemini API", "Google Gemini"]},
        "RAG": {"aliases": ["Retrieval-Augmented Generation", "Retrieval Augmented Generation"]},
        "Vector Databases": {"aliases": ["Vector DB", "Pinecone", "ChromaDB", "FAISS", "Milvus"]},
        "LangChain": {"aliases": []},
        "HuggingFace": {"aliases": ["Hugging Face"]}
    }
    ontology["categories"]["AI & Machine Learning"].update(ai_skills)

    if "Embedded & IoT" not in ontology["categories"]:
        ontology["categories"]["Embedded & IoT"] = {}
        
    embedded_skills = {
        "C": {"aliases": []},
        "Microcontrollers": {"aliases": ["MCU", "Arduino", "ESP32", "STM32"]},
        "RTOS": {"aliases": ["Real-Time Operating System", "FreeRTOS"]},
        "IoT": {"aliases": ["Internet of Things"]}
    }
    ontology["categories"]["Embedded & IoT"].update(embedded_skills)
    
    # 3. Enhance Relationships
    if "relationships" not in ontology:
        ontology["relationships"] = []
        
    # We will clear and rewrite relationships for consistency
    new_relationships = [
        {"source": "FastAPI", "target": "Python", "type": "framework_of"},
        {"source": "FastAPI", "target": "REST APIs", "type": "implements"},
        {"source": "FastAPI", "target": "JWT", "type": "commonly_uses"},
        {"source": "JWT", "target": "Authentication", "type": "used_for"},
        {"source": "OAuth2", "target": "Authentication", "type": "used_for"},
        {"source": "Authentication", "target": "Backend", "type": "belongs_to"},
        {"source": "MySQL", "target": "SQL", "type": "implements"},
        {"source": "PostgreSQL", "target": "SQL", "type": "implements"},
        {"source": "MongoDB", "target": "NoSQL", "type": "belongs_to"},
        {"source": "Docker", "target": "DevOps", "type": "belongs_to"},
        {"source": "Kubernetes", "target": "Docker", "type": "orchestrates"},
        {"source": "Redis", "target": "Caching", "type": "belongs_to"},
        {"source": "Gemini", "target": "LLM", "type": "implements"},
        {"source": "OpenAI", "target": "LLM", "type": "implements"},
        {"source": "LLM", "target": "Generative AI", "type": "belongs_to"},
        {"source": "Generative AI", "target": "Artificial Intelligence", "type": "belongs_to"},
        {"source": "Artificial Intelligence", "target": "Software Engineering", "type": "belongs_to"},
        {"source": "Transformers", "target": "Machine Learning", "type": "belongs_to"},
        {"source": "TensorFlow", "target": "Machine Learning", "type": "belongs_to"},
        {"source": "PyTorch", "target": "Machine Learning", "type": "belongs_to"},
        {"source": "React", "target": "Frontend Framework", "type": "belongs_to"},
        {"source": "Node.js", "target": "Backend Runtime", "type": "belongs_to"},
        {"source": "Express.js", "target": "Backend Framework", "type": "belongs_to"},
        {"source": "Django", "target": "Python", "type": "framework_of"},
        {"source": "Flask", "target": "Python", "type": "framework_of"},
        {"source": "Spring Boot", "target": "Java", "type": "framework_of"},
        {"source": "Data Structures", "target": "Data Structures and Algorithms", "type": "belongs_to"},
        {"source": "Algorithms", "target": "Data Structures and Algorithms", "type": "belongs_to"},
        {"source": "AWS", "target": "Cloud Computing", "type": "belongs_to"},
        {"source": "Azure", "target": "Cloud Computing", "type": "belongs_to"},
        {"source": "GCP", "target": "Cloud Computing", "type": "belongs_to"}
    ]
    
    # Merge relationships (avoiding strict duplicates)
    existing_rels = {(r["source"], r["target"], r.get("type", "related_to")) for r in ontology.get("relationships", [])}
    for rel in new_relationships:
        if (rel["source"], rel["target"], rel["type"]) not in existing_rels:
            ontology["relationships"].append(rel)
            existing_rels.add((rel["source"], rel["target"], rel["type"]))

    # 4. Normalization improvements
    aliases_to_add = {
        "Problem Solving": ["ProblemSolving", "Problem-Solving"],
        "C++": ["C Plus Plus", "CPP"],
        "REST APIs": ["REST API", "RESTful APIs", "RESTful API"],
        "GitHub Actions": ["Github Actions", "GitHub Action"],
        "Object-Oriented Programming": ["OOP", "Object Oriented Programming"]
    }
    
    for category in ontology["categories"].values():
        for skill, data in category.items():
            if skill in aliases_to_add:
                current_aliases = set(data.get("aliases", []))
                for a in aliases_to_add[skill]:
                    current_aliases.add(a)
                data["aliases"] = list(current_aliases)

    with open(ontology_path, "w", encoding="utf-8") as f:
        json.dump(ontology, f, indent=2)
        
    print("Ontology expanded successfully.")

if __name__ == "__main__":
    expand_ontology()
