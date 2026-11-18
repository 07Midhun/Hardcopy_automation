# AI Document Intelligence – REST API Reference

All API endpoints return JSON responses and support standardized HTTP status codes.

---

## 1. Authentication Endpoints

### Register User
- **Method**: `POST`
- **Path**: `/api/auth/register`
- **Request Body**:
  ```json
  {
    "username": "operator1",
    "email": "operator1@example.com",
    "password": "SecretPassword123"
  }
  ```
- **Response** `201 Created`:
  ```json
  {
    "message": "User registered successfully",
    "user": { "id": 1, "username": "operator1", "email": "operator1@example.com", "role": "operator" }
  }
  ```

### Login User
- **Method**: `POST`
- **Path**: `/api/auth/login`
- **Request Body**:
  ```json
  {
    "username": "operator1",
    "password": "SecretPassword123"
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "message": "Login successful",
    "user": { "id": 1, "username": "operator1", "role": "operator" }
  }
  ```

---

## 2. Ingestion & Upload Endpoints

### Bulk PDF Upload
- **Method**: `POST`
- **Path**: `/api/upload/bulk`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `files`: Array of PDF files
  - `batch_name` (optional): Batch name string
- **Response** `201 Created`:
  ```json
  {
    "message": "Successfully registered 120 documents.",
    "job_id": "JOB-20261117-ABCDEF",
    "total_files": 120,
    "registered_count": 120,
    "duplicates_detected": 0
  }
  ```

### ZIP Archive Upload
- **Method**: `POST`
- **Path**: `/api/upload/zip`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file`: A single `.zip` file containing PDF files
  - `batch_name` (optional): String
- **Response** `202 Accepted`:
  ```json
  {
    "message": "ZIP archive received and processing queued.",
    "job_id": "JOB-ZIP-20261117-XYZ123",
    "status": "queued"
  }
  ```

---

## 3. Jobs & Queue Monitoring

### List Jobs
- **Method**: `GET`
- **Path**: `/api/jobs?page=1&per_page=20`

### Get Job Progress
- **Method**: `GET`
- **Path**: `/api/jobs/{job_id}/progress`
- **Response** `200 OK`:
  ```json
  {
    "job_id": "JOB-20261117-ABCDEF",
    "status": "processing",
    "total_documents": 100,
    "completed": 85,
    "failed": 2,
    "review_required": 8,
    "in_progress": 3,
    "queued": 2,
    "progress_percentage": 95.0,
    "is_finished": false
  }
  ```

### Retry Failed Documents in Batch
- **Method**: `POST`
- **Path**: `/api/jobs/{job_id}/retry-failed`

---

## 4. Document Operations & Extraction

### Search & List Documents
- **Method**: `GET`
- **Path**: `/api/documents?page=1&per_page=25&status=completed&document_type=CCMS+Installation+Report&search=report`

### Get Document Metadata
- **Method**: `GET`
- **Path**: `/api/documents/{doc_id}`

### Get Document Extraction
- **Method**: `GET`
- **Path**: `/api/documents/{doc_id}/extraction`
- **Response** `200 OK`:
  ```json
  {
    "document_id": "DOC-A1B2C3D4",
    "source_filename": "ward64_report_01.pdf",
    "document_type": "CCMS Installation Report",
    "status": "completed",
    "confidence_average": 0.94,
    "records": [
      {
        "id": 1,
        "section": "General Information",
        "record_number": 1,
        "page_number": 1,
        "fields": [
          {
            "id": 101,
            "field_name": "Ward Number",
            "original_extracted_value": "64",
            "current_value": "64",
            "confidence_score": 0.98,
            "verification_status": "verified"
          }
        ]
      }
    ]
  }
  ```

### Retry Single Document
- **Method**: `POST`
- **Path**: `/api/documents/{doc_id}/retry`

---

## 5. Verification & Human-in-the-Loop

### Get Review Queue
- **Method**: `GET`
- **Path**: `/api/review/queue?page=1&per_page=20`

### Submit Field Corrections
- **Method**: `PATCH`
- **Path**: `/api/documents/{doc_id}/corrections`
- **Request Body**:
  ```json
  {
    "document_status": "completed",
    "corrections": [
      {
        "field_id": 102,
        "corrected_value": "860",
        "verification_status": "verified",
        "notes": "Handwritten digit 0 clarified"
      }
    ]
  }
  ```

---

## 6. Consolidated Excel Export

### Download Consolidated Excel
- **Method**: `GET`
- **Path**: `/api/export/consolidated?job_id={optional_job_id}`
- **Response**: Binary Excel file (`.xlsx`) with `Content-Disposition: attachment; filename=Consolidated_Export_...xlsx`.

