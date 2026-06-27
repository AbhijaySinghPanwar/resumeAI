import requests
import json
import os

def main():
    payload_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resumeai_app", "latest_parse_payload.json"))
    with open(payload_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # The frontend does: lastResult = data.result ?? {}
    # So the parse_result sent to the API is EXACTLY the unwrapped inner object
    parse_result = data.get("result", {})

    jd_text = """Job Title: Backend Software Engineer
Requirements:
- Python
- Django or FastAPI
- REST APIs
- SQL (PostgreSQL or MySQL)
- Docker
- Git
"""

    body = {
        "parse_result": parse_result,
        "job_description": jd_text
    }

    print("Sending POST /api/match...")
    res = requests.post("http://localhost:8000/api/match", json=body)
    print("Status:", res.status_code)
    try:
        j = res.json()
        print("Match Score:", j.get("match_score"))
        print("Skill Score:", j.get("component_scores", {}).get("skills"))
        print("Matched count:", len(j.get("matched_skills", [])))
        print("Missing count:", len(j.get("missing_skills", [])))
        print("\n--- Full JSON ---")
        print(json.dumps(j, indent=2))
    except Exception as e:
        print("Error parsing response:", e)
        print("Response text:", res.text)

if __name__ == "__main__":
    main()
