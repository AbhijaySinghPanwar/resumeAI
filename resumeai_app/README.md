# ResumeAI — Full Stack App

A complete web application for the ResumeAI v7.0.0 parser.  
**FastAPI backend** + **HTML/CSS/JS frontend** using the Corporate Trust design system.

---

## Project Structure

```
resumeai_app/
├── backend/
│   └── main.py          ← FastAPI server (4 endpoints)
├── frontend/
│   └── index.html       ← Single-file React-style UI
├── run_backend.sh        ← Start the API server
├── run_frontend.sh       ← Serve the UI
└── README.md

resumeai/                 ← The parser library (one level up)
├── core/
├── extractors/
├── ats/
├── pipeline.py
└── ...
```

---

## How to Run

### Step 1 — Install dependencies

```bash
pip install fastapi uvicorn python-multipart pdfplumber rapidfuzz python-dateutil
```

Or from the resumeai folder:
```bash
pip install -r resumeai/requirements.txt
pip install -e resumeai/
pip install fastapi uvicorn python-multipart
```

### Step 2 — Start the backend (Terminal 1)

```bash
cd resumeai_app
bash run_backend.sh
```

The API will be live at:
- **http://localhost:8000** — API root
- **http://localhost:8000/docs** — Interactive Swagger UI
- **http://localhost:8000/api/health** — Health check

### Step 3 — Start the frontend (Terminal 2)

```bash
cd resumeai_app
bash run_frontend.sh
```

Open **http://localhost:3000** in your browser.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/parse` | Parse resume (file upload or text) |
| POST | `/api/score` | Score against a job description |
| POST | `/api/export` | Export to Greenhouse / Lever / Workday / CSV |

### POST /api/parse

**Form data** (multipart):
- `file` — PDF or text file upload *(optional)*
- `text` — Plain text resume *(optional, use if no file)*

Returns:
```json
{
  "result": { ...v7.0.0 schema... },
  "gate":   { "passed": true, "summary": "PASSED", ... }
}
```

### POST /api/score

**JSON body:**
```json
{
  "parse_result": { ...from /api/parse... },
  "job_description": "Looking for a Python engineer with 3+ years..."
}
```

Returns:
```json
{
  "overall_score": 78.5,
  "grade": "B",
  "matched_skills": ["python", "django", "aws"],
  "missing_skills": ["kubernetes"],
  "recommendation": "Good match — recommend for screening call"
}
```

### POST /api/export

**JSON body:**
```json
{
  "parse_result": { ...from /api/parse... },
  "format": "greenhouse"
}
```

Supported formats: `generic_json`, `greenhouse`, `lever`, `workday`, `csv`

---

## What the UI Does

1. **Paste text or upload PDF** — drag-and-drop or browse
2. **Add a job description** (optional) — enables match scoring
3. **Parse** — calls the backend, renders structured results
4. **View** — contact, education, experience, projects, leadership, certifications, skills
5. **Score** — JD match score with per-category bars and skill gap analysis
6. **Export** — download as JSON, Greenhouse, Lever, Workday, or CSV
7. **Debug** — toggle raw debug output (section transitions, ownership log, anomalies)

---

## Troubleshooting

**"Parse failed" error in the browser:**
- Make sure the backend is running: `curl http://localhost:8000/api/health`
- Check the terminal for Python errors

**CORS error:**
- The backend allows all origins by default — this should not happen
- Ensure you're opening `http://localhost:3000`, not a `file://` URL

**PDF not parsing:**
- `pdfplumber` must be installed: `pip install pdfplumber`
- Some heavily-scanned PDFs may produce poor text extraction — try paste-text mode

**Port conflicts:**
- Backend port: change `--port 8000` in `run_backend.sh`
- Frontend port: change `PORT=3000` in `run_frontend.sh`
- Update `API_BASE` in `frontend/index.html` to match
