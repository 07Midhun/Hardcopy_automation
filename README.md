# AI Document Intelligence – Bulk PDF to Excel Automation System

A production-ready, cloud-native document automation system engineered to process **approximately 6,000 physical scanned/photographed single-page documents** containing mixed printed and handwritten information. The platform dynamically classifies diverse document layouts (without predefined templates), performs OCR and handwriting recognition, supports human-in-the-loop review, and compiles all extracted fields into **EXACTLY ONE consolidated Excel workbook containing EXACTLY ONE worksheet (`Consolidated_Data`)**.

---

## 🌟 Key Highlights & Architectural Strengths

- **Dynamic Layout Understanding**: No brittle fixed coordinate templates. Accommodates CCMS Installation Reports, Inspection Reports, Survey Forms, Technical Reports, and unseen document formats dynamically.
- **Strict Handwriting Rules**: Zero fabrication. Preserves original spelling, avoids auto-correction, retains leading zeros, and flags low-confidence handwriting for manual verification.
- **Pluggable Multi-Model AI Engine**: Provider abstraction supporting Azure AI Document Intelligence, OpenAI GPT-4o Vision, Google Gemini 2.0 Flash, and high-fidelity local fallback heuristics for offline testing.
- **Dual-Panel Human-in-the-Loop Review Station**: Interactive zoomable viewer on the left; editable fields, confidence badges, and audit logging on the right.
- **Enterprise Asynchronous Bulk Processing**: Celery worker queue backed by Redis with configurable batching, retry backoff, and idempotent task execution.
- **Traceable Consolidated Excel**: Generates a single workbook with exactly one worksheet named `Consolidated_Data` preserving column filters, frozen headers, and leading zeros.

---

## 📁 System Folder Structure

```
AI_Document_Intelligence/
├── backend/
│   ├── app/
│   │   ├── __init__.py               # Flask application factory
│   │   ├── config.py                 # Configuration management (Dev, Test, Prod)
│   │   ├── extensions.py             # SQLAlchemy, LoginManager, CORS
│   │   ├── models/                   # Relational PostgreSQL models
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── processing_job.py
│   │   │   ├── extracted_record.py
│   │   │   ├── extracted_field.py
│   │   │   └── verification_log.py
│   │   ├── routes/                   # REST API & HTML Views (Flask Blueprints)
│   │   │   ├── auth_routes.py
│   │   │   ├── upload_routes.py
│   │   │   ├── document_routes.py
│   │   │   ├── processing_routes.py
│   │   │   ├── review_routes.py
│   │   │   ├── dashboard_routes.py
│   │   │   └── export_routes.py
│   │   ├── services/                 # Business logic & Pipeline orchestrators
│   │   │   ├── pdf_service.py
│   │   │   ├── image_service.py
│   │   │   ├── document_classifier.py
│   │   │   ├── extraction_service.py
│   │   │   ├── normalization_service.py
│   │   │   ├── validation_service.py
│   │   │   ├── confidence_service.py
│   │   │   ├── duplicate_service.py
│   │   │   └── excel_service.py
│   │   ├── ai/                       # Multi-provider OCR & Vision extraction
│   │   │   ├── base_provider.py
│   │   │   ├── azure_provider.py
│   │   │   ├── vision_provider.py
│   │   │   ├── fallback_provider.py
│   │   │   ├── provider_factory.py
│   │   │   ├── prompts.py
│   │   │   └── schemas.py
│   │   ├── tasks/                    # Celery background queue tasks
│   │   │   ├── celery_app.py
│   │   │   ├── upload_tasks.py
│   │   │   ├── processing_tasks.py
│   │   │   ├── retry_tasks.py
│   │   │   └── export_tasks.py
│   │   ├── storage/                  # AWS S3 and Local storage abstraction
│   │   │   ├── base_storage.py
│   │   │   └── s3_storage.py
│   │   └── utils/                    # PyMuPDF, OpenCV, hashing, and JSON utils
│   │       ├── file_utils.py
│   │       ├── pdf_utils.py
│   │       ├── image_utils.py
│   │       ├── json_utils.py
│   │       └── logger.py
│   ├── tests/                        # Comprehensive unit & integration tests
│   ├── requirements.txt
│   ├── run.py
│   └── wsgi.py
├── frontend/
│   ├── static/                       # CSS stylesheets and interactive JS
│   └── templates/                    # Jinja2 HTML templates
├── storage/
│   ├── uploads/
│   ├── temp/
│   └── exports/
├── deployment/                       # Docker, Compose, Nginx, AWS ECS/S3 specs
├── docs/                             # Architecture, API, and DB documentation
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start & Installation

### Option 1: Zero-Config Local Setup (SQLite / Eager Queue)

1. Clone or navigate to the project directory:
   ```bash
   cd c:/MIDHUN/SCHNELL/OCR_EXTRACTION
   ```

2. Copy environment settings:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Launch the application:
   ```bash
   python backend/run.py
   ```
   Open your browser to `http://localhost:5000`.

---

### Option 2: Docker Compose (PostgreSQL + Redis + Celery + Nginx)

Run the full multi-container stack:
```bash
docker-compose -f deployment/docker-compose.yml up --build -d
```

Services initialized:
- `http://localhost:5000`: Flask Application & Human Review Station
- `localhost:5432`: PostgreSQL 16
- `localhost:6379`: Redis 7 Broker
- `Celery Worker`: 4 concurrent document processing workers

---

## 📊 Consolidated Excel Generation Specifications

The exported Excel file conforms strictly to Section 13 requirements:
- **Exact Worksheet Title**: `Consolidated_Data`
- **One Workbook, Exactly One Sheet**: No secondary sheets created.
- **Required Columns**:
  1. `Document ID`
  2. `Source Filename`
  3. `Document Type`
  4. `Page Number`
  5. `Section`
  6. `Record Number`
  7. `Field Name`
  8. `Extracted Value`
  9. `Confidence Score`
  10. `Verification Status`
- **Formatting**:
  - Top header row frozen (`A2`).
  - Auto-filter enabled across all columns (`A1:J...`).
  - Bold headers styled with enterprise fill `#1E3A8A`.
  - Leading zeros strictly preserved via text number formatting (`@`).
  - Cap checks against Excel's maximum row limit (1,048,576 rows).

---

## 🧪 Running the Test Suite

Execute the automated test suite with pytest:
```bash
pytest backend/tests -v
```

