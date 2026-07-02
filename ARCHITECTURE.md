# ResumeAI v1.0 Architecture

## High-Level Overview
ResumeAI is built as a FastAPI monolithic backend with a vanilla HTML/JS/CSS frontend served statically from the backend. The core capabilities involve Resume Parsing, ATS Scoring, Semantic JD Matching, and AI-driven content generation.

## Components

### 1. Frontend Layer
- **Stack**: HTML5, Vanilla JavaScript, CSS variables.
- **Routing**: Handled by single-page hash fragments or lightweight file routing.
- **Integration**: Communicates with the backend REST API via standard `fetch`.

### 2. API Gateway & Middleware
- **FastAPI**: `main.py` is the entrypoint.
- **Middleware**: 
  - `CORSMiddleware`: Strict domain validation in production.
  - `production_middleware`: Logs memory usage, response times, assigns `X-Request-ID`, and enforces a 100 req/min rate limit per IP.
- **Authentication**: JWT-based authentication using PyJWT.

### 3. Pipeline Services
- **Parser (`resumeai.pipeline`)**: Uses `pdfplumber` dynamically for text extraction, then formats into a structured JSON schema.
- **ATS Scorer (`resumeai.scoring`)**: Rule-based heuristic engine assessing layout, keywords, and structural integrity.
- **Semantic Matcher (`resumeai.matching`)**: 
  - Compares Resume skills to Job Description skills using Cosine Similarity.
  - **ONNX Engine (`onnx_engine.py`)**: Default engine. Bypasses PyTorch overhead using `onnxruntime` and HuggingFace Tokenizers to perform inference on `all-MiniLM-L6-v2`. Peak RSS is <450MB.
- **AI Services (`services.gemini_service`)**: Interacts with the Gemini API for bullet improvement, project enhancement, and interview prep. Includes exponential backoff and 15-second timeouts.

### 4. Database Layer
- **ORM**: SQLAlchemy.
- **Provider**: Neon PostgreSQL (Production) / SQLite (Development).
- **Pooling**: Pre-ping enabled, limit 5 connections (to fit memory constraints).
- **Transactions**: Owned by the API controllers (`main.py`) which explicitly commit or rollback `ResumeRepository` and `ReportRepository` operations.
