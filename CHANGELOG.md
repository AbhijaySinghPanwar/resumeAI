# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc.1] - 2026-07-01

### Added
- `ONNXEngine` semantic matching integration to reduce memory footprint.
- Lightweight rate-limiting middleware (100 req/min per IP).
- Request logging middleware with `X-Request-ID`, execution duration, and RSS memory profiling.
- Application health check (`GET /api/health`) and version (`GET /api/version`) endpoints.
- Environment variable `EMBEDDING_ENGINE` to toggle between ONNX and PyTorch dynamically.
- Explicit timeout configurations (15.0s) for all Gemini API requests.
- Strict startup dependency validation (Database, ONNX, Gemini, Static Files) for `production` environment.
- Strict configuration hardening (`SECRET_KEY`, `ALLOWED_ORIGINS`, `DEBUG`).

### Changed
- Refactored `ResumeRepository` and `ReportRepository` to allow transaction management by the calling API endpoints, preventing partial database writes on failure.
- Updated Dockerfile to use `pip install .` instead of editable install mode to reduce layer bloat.
- Replaced `traceback.print_exc()` with sanitized HTTP 500 error messages to prevent exposing internal mechanics to the client.
- Restricted `/api/parse` upload limits to 10 MB.
- Restricted `/api/parse` MIME types to `application/pdf` and `text/plain`.

### Removed
- `PyPDF2` dependency (now completely replaced by the modern `pypdf` fork and `pdfplumber`).
