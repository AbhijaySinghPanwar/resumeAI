import requests
import json
import os

payload_path = os.path.join(os.path.dirname(__file__), '..', 'resumeai_app', 'latest_parse_payload.json')
with open(payload_path, 'r') as f:
    payload = json.load(f)

# If it has a 'result' wrapper, use that or use the whole thing depending on how frontend does it.
# Let's see what frontend sends. We'll try sending the whole thing as `parse_result`.

jd_text = """
Job Title: Backend Engineer
Requirements:
- 3+ years experience
- Python
- Django or FastAPI
- REST APIs
- SQL (PostgreSQL or MySQL)
- Docker
- Git
"""

# Let's simulate frontend request
req_body = {
    "parse_result": payload, 
    "job_description": jd_text
}

resp = requests.post("http://localhost:8000/api/match", json=req_body)
print("Status:", resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception as e:
    print(resp.text)
