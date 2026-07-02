# ResumeAI

🚀 **Live Demo:** [https://resumeai-sir1.onrender.com](https://resumeai-sir1.onrender.com)

ResumeAI is an intelligent, full-stack Resume Analysis and Parsing Platform. It parses resumes, scores them against job descriptions, and provides actionable insights powered by AI.

## Dashboards & Analysis

### ATS Score Dashboard
Get a detailed breakdown of your resume's tier, completeness, and section-by-section ATS score. Identify top strengths and risks to improve your recruiter readiness.

![ATS Score Dashboard](./assets/ats-score-dashboard.png)

### Job Match Analysis
Compare your resume directly against a target Job Description. See your overall match percentage, component breakdowns (Skill Match, Semantic Relevance, Experience Fit, Education Fit), and a gap analysis of missing vs. matched skills.

![Job Match Analysis](./assets/job-match-analysis.png)

## Architecture
- **Backend:** FastAPI, Python, Sentence-Transformers
- **Frontend:** HTML, CSS, JavaScript (React-style UI)

## Getting Started
To run locally, check out the documentation in the respective app directories:
- `resumeai_app/README.md` for full-stack instructions.
- `resumeai/README.md` for the core parser library.
