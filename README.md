# ResumeAI 🚀

> An intelligent, full-stack Resume Analysis and Parsing Platform designed to help job seekers optimize their resumes for Applicant Tracking Systems (ATS) and specific Job Descriptions.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-005C84?style=for-the-badge&logo=onnx&logoColor=white)
![MIT License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)

---

## 🌍 Live Demo

**URL:** [http://32.236.237.82/](http://32.236.237.82/)

> **Note:** This application is currently deployed on AWS EC2. HTTPS and a custom domain are planned for a future update.

---

## 📸 Screenshots

### 📊 ATS Score Dashboard
Get a comprehensive breakdown of your resume's tier, completeness, and section-by-section ATS score. Identify top strengths and critical risks to improve your recruiter readiness.

![ATS Score Dashboard](./assets/ats-score-dashboard.png)

### 🎯 Job Match Analysis
Compare your resume directly against a target Job Description.

![Job Match Analysis](./assets/job-match-analysis.png)

---

## 🌟 Features

### 📄 Resume Parsing
- **PDF Extraction:** Accurate text extraction using `pdfplumber`.
- **Section Detection:** Intelligently identifies experience, education, skills, and projects.
- **Structured Parsing:** Converts raw resumes into structured JSON data.

### 📊 ATS Analysis
- **ATS Score & Tier:** Calculates a reliable ATS compatibility score and ranks the resume.
- **Section-Wise Scoring:** Granular scoring for each section.
- **Improvement Suggestions:** Actionable feedback to boost the ATS score.

### 🎯 Job Description Matching
- **Match %:** Overall compatibility score against a specific JD.
- **Skill Match & Semantic Similarity:** Uses embeddings to match skills semantically, not just exact keywords.
- **Experience & Education Match:** Validates years of experience and degree requirements.
- **Gap Analysis:** Identifies missing skills and provides a learning roadmap.

### 🤖 AI Resume Assistant
- **Resume Bullet Improvements:** Generates ATS-optimized, professional, and concise bullet points using Google Gemini API.
- **Project Enhancement:** Upgrades project descriptions for technical and recruiter audiences.
- **Interview Preparation:** Generates personalized technical, behavioral, and project-based questions.

### 🔐 Authentication
- **JWT Authentication:** Secure user authentication using JSON Web Tokens.
- **Protected APIs:** Secures user data and resume history.

### ⚡ Performance Optimization
- **ONNX Runtime:** By utilizing ONNX Runtime instead of PyTorch, ResumeAI achieves lower memory usage, faster inference, a smaller deployment size, and better startup times. This makes it highly suitable for low-cost EC2 instances.

---

## 🏗️ Architecture

```mermaid
graph TD
    Client[Internet] -->|HTTP| EC2[AWS EC2]
    EC2 --> Nginx[Nginx Reverse Proxy]
    Nginx --> Docker[Docker Container]
    Docker --> FastAPI[FastAPI Backend]
    FastAPI --> SQLAlchemy[SQLAlchemy ORM]
    SQLAlchemy --> RDS[(Amazon RDS PostgreSQL)]
    
    FastAPI <--> Alembic[Alembic Migrations]
    FastAPI <--> SSMP[AWS Systems Manager Parameter Store]
    FastAPI <--> Gemini[Google Gemini API]
    FastAPI <--> ONNX[ONNX Runtime]
```

---

## ☁️ AWS Deployment

The application is deployed on Amazon Web Services (AWS) using a cost-effective, containerized infrastructure:

- **Amazon EC2:** Hosts the application on Amazon Linux 2023, optimized for low memory usage.
- **Docker:** Containerized backend and frontend for consistent environments. Containers are configured with restart policies to recover automatically.
- **Nginx Reverse Proxy:** Manages incoming HTTP traffic and serves the frontend.
- **Amazon RDS PostgreSQL:** Fully managed relational database for production data.
- **AWS Systems Manager Parameter Store:** Securely stores secrets (e.g., Gemini API Key, JWT Secret, Database URLs).
- **Alembic:** Handles automated database schema migrations.
- **Health Endpoint:** Dedicated `/api/health` endpoint for monitoring application uptime and database connectivity.

---

## 🛠️ Tech Stack

### Frontend
- HTML5
- CSS3
- Vanilla JavaScript

### Backend
- FastAPI
- Python 3.11
- SQLAlchemy
- Alembic
- JWT Authentication

### Artificial Intelligence
- Google Gemini API
- ONNX Runtime
- `all-MiniLM-L6-v2` (Sentence Transformers)
- pdfplumber

### Database
- **Development:** SQLite
- **Production:** Amazon RDS PostgreSQL

### Cloud & DevOps
- AWS EC2
- Docker
- Nginx
- AWS Systems Manager Parameter Store

---

## ⚡ Performance & Optimization

ResumeAI was intentionally designed for a **low-memory footprint**, allowing it to run smoothly on small, cost-effective cloud instances.

Instead of running heavy PyTorch models in production, the semantic matching engine utilizes **ONNX Runtime**. 

**Key Benefits:**
- **Reduced RAM Usage:** Operates efficiently without the overhead of the full PyTorch library.
- **Faster Inference:** Accelerated semantic similarity computations.
- **Smaller Deployment Size:** Drastically reduces the Docker image size.
- **Lower Cold-Start Latency:** Much faster application startup time.

---

## 📁 Project Structure

```text
resumeAI/
├── assets/                 # Images and screenshots
├── resumeai/               # Core parser and matching library
│   ├── ats/                # ATS scoring logic
│   ├── extractors/         # PDF and text extractors
│   ├── matching/           # Skill and JD matching, ONNX embedding engine
│   ├── ontology/           # Skill ontology and synonyms
│   └── scoring/            # Scoring algorithms
├── resumeai_app/           # FastAPI application & Frontend
│   ├── backend/            # FastAPI backend
│   │   ├── alembic/        # Database migrations
│   │   ├── core/           # Configuration and settings
│   │   ├── database/       # SQLAlchemy models and engine
│   │   ├── routers/        # API routers (auth, history, etc.)
│   │   └── services/       # Business logic (Gemini, Auth)
│   └── frontend/           # Vanilla JS/HTML/CSS UI
├── Dockerfile              # Production Docker image configuration
└── README.md               # Project documentation
```

---

## 💻 Local Development

### 1. Clone the repository
```bash
git clone https://github.com/AbhijaySinghPanwar/resumeAI.git
cd resumeAI
```

### 2. Set up a virtual environment
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables
Create a `.env` file in `resumeai_app/backend/` and configure the necessary keys:
```env
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET=your_jwt_secret
DATABASE_URL=sqlite:///./resumeai.db
EMBEDDING_ENGINE=onnx
```

### 5. Run Locally
```bash
cd resumeai_app/backend
uvicorn main:app --reload
```
The application will be available at `http://localhost:8000`.

---

## 🐳 Docker Deployment

To run the application using Docker:

### 1. Build the image
```bash
docker build -t resumeai .
```

### 2. Run the container
```bash
docker run -d \
  --name resumeai \
  --restart unless-stopped \
  -p 80:80 \
  -e GEMINI_API_KEY="your_api_key" \
  -e JWT_SECRET="your_jwt_secret" \
  -e DATABASE_URL="postgresql://user:pass@host:5432/dbname" \
  resumeai
```
*Note: The `--restart unless-stopped` policy ensures the container restarts automatically if it crashes or the server reboots.*

---

## 🔌 API Documentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Returns server status and version |
| `GET` | `/api/version` | Returns detailed version information |
| `POST` | `/api/parse` | Parse a resume PDF or plain text |
| `POST` | `/api/score` | Score a parsed resume against a job description |
| `POST` | `/api/export` | Export resume to ATS formats (Greenhouse, Lever, etc.) |
| `POST` | `/api/parse_jd` | Parse a raw job description |
| `POST` | `/api/match` | Match a resume to a job description |
| `POST` | `/ai/improve-bullet` | Rewrite a resume bullet with AI |
| `POST` | `/ai/enhance-project`| Enhance a project description with AI |
| `POST` | `/ai/interview-questions` | Generate personalized interview questions |
| `GET` | `/ai/status` | Check Gemini API status |
| `POST` | `/auth/signup` | Register a new user |
| `POST` | `/auth/login` | Authenticate and return JWT |
| `GET` | `/auth/me` | Get current user profile (protected) |
| `POST` | `/auth/logout` | Logout (client-side token invalidation) |
| `GET` | `/auth/stats` | Get dashboard statistics for current user |

---

## 🔮 Future Improvements

- HTTPS Configuration
- Custom Domain Name
- GitHub Actions CI/CD Pipeline
- CloudWatch Monitoring
- Resume Version History
- Multi-language Support

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
