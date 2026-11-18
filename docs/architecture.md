# AI Document Intelligence – System Architecture

## 1. High-Level Architecture Overview

The **AI Document Intelligence Bulk PDF to Excel Automation System** is an enterprise-grade, cloud-ready document extraction and consolidation platform. It automates the extraction of both printed and handwritten content from thousands of physical paper scans/photographs and compiles the results into a single consolidated Excel workbook.

```
                           +-------------------------------------+
                           |            Web Client               |
                           |  (Drag & Drop Bulk Upload / Review) |
                           +------------------+------------------+
                                              |
                                              v
                           +-------------------------------------+
                           |       Reverse Proxy (Nginx)         |
                           +------------------+------------------+
                                              |
                                              v
                           +-------------------------------------+
                           |       Flask Web API Application     |
                           |  (Authentication, Upload, Routes)   |
                           +--------+-------------------+--------+
                                    |                   |
                     S3 Storage /   |                   | Enqueue Tasks
                     Local Storage  |                   |
                                    v                   v
                     +----------------------+   +-------------------+
                     | AWS S3 Bucket        |   | Redis Message     |
                     | (PDFs, Images)       |   | Broker            |
                     +----------------------+   +---------+---------+
                                                          |
                                                          v
                                                +-------------------+
                                                | Celery Background |
                                                | Workers (Cluster) |
                                                +---------+---------+
                                                          |
             +--------------------+-----------------------+
             |                    |                       |
             v                    v                       v
     +---------------+    +----------------+    +-------------------+
     | PyMuPDF       |    | OpenCV Image   |    | Multi-Model AI    |
     | (Text / Dpi)  |    | (Deskew/CLAHE) |    | (Azure/Vision LLM)|
     +---------------+    +----------------+    +---------+---------+
                                                          |
                                                          v
                                                +-------------------+
                                                | PostgreSQL DB     |
                                                | (Relational Data) |
                                                +---------+---------+
                                                          |
                                                          v
                                                +-------------------+
                                                | OpenPyXL Stream   |
                                                | Consolidated Excel|
                                                +-------------------+
```

---

## 2. Core Processing Pipeline Stages

1. **Ingestion & Cryptographic Hashing**:
   - Accepts multi-PDF or ZIP uploads.
   - Calculates SHA-256 hash immediately to prevent duplicate processing.
   - Streams files directly to AWS S3 (or local storage) without loading all files into application memory.
   - Registers a `ProcessingJob` and individual `Document` records in PostgreSQL.

2. **PDF Inspection & Page Rendering**:
   - PyMuPDF opens each document to inspect page count and detects embedded digital text.
   - If selectable digital text is found, it is extracted directly to save compute/API costs.
   - Renders page to a 300 DPI high-resolution PNG image for handwriting recognition.

3. **Computer Vision Enhancement (OpenCV)**:
   - **Deskewing**: Hough line transform and minimum area rectangle detection correct rotation.
   - **CLAHE Contrast Enhancement**: Equalizes contrast on faint ballpoint and gel pen strokes.
   - **Bilateral Filtering**: Cleans scanner noise while strictly preserving sharp handwriting edges.
   - Original document is strictly preserved; enhanced images are written to a temporary cache.

4. **Dynamic AI Extraction & Layout Classification**:
   - Does NOT rely on fixed templates.
   - AI Provider Abstraction supports Azure Document Intelligence, OpenAI GPT-4o Vision, Google Gemini Vision, and local fallback heuristics.
   - Categorizes document type (CCMS Installation Report, Inspection Report, Survey Form, Technical Report, or Unidentified).
   - Extracts sections, key-value fields, and table rows with column associations.

5. **Normalization & Validation**:
   - Field names are cleaned of trailing delimiters.
   - Leading zeros and original spelling are strictly preserved.
   - Assigns confidence scores (0.00 to 1.00). Any field below the threshold (0.75) is flagged as `review_required`.

6. **Human-in-the-Loop Review Station**:
   - Side-by-side interface: Document preview on left, editable values on right.
   - Full audit logging in `verification_logs`.

7. **Consolidated Excel Generation**:
   - Consolidates all records into **EXACTLY ONE Excel workbook containing EXACTLY ONE worksheet** named `Consolidated_Data`.

