# AI Document Intelligence – PostgreSQL Database Schema

The database design adheres to Section 12 specifications. Extracted content is stored in a normalized relational structure rather than a single unstructured JSON column to facilitate rapid queries, filtering, and auditability.

```
                           +----------------------+
                           |        users         |
                           +----------------------+
                           | id (PK)              |
                           | username             |
                           | email                |
                           | password_hash        |
                           | role                 |
                           | created_at           |
                           +----------+-----------+
                                      |
                                      | 1:N
                                      v
                           +----------------------+
                           |   processing_jobs    |
                           +----------------------+
                           | id (PK)              |
                           | user_id (FK)         |
                           | batch_name           |
                           | total_documents      |
                           | completed_documents  |
                           | failed_documents     |
                           | review_required_docs |
                           | status               |
                           | created_at           |
                           | completed_at         |
                           +----------+-----------+
                                      |
                                      | 1:N
                                      v
                           +----------------------+
                           |      documents       |
                           +----------------------+
                           | id (PK)              |
                           | job_id (FK)          |
                           | original_filename    |
                           | s3_key               |
                           | file_hash (SHA-256)  |
                           | file_size            |
                           | document_type        |
                           | status               |
                           | error_message        |
                           | uploaded_at          |
                           | processed_at         |
                           +----------+-----------+
                                      |
                         +------------+------------+
                         | 1:N                     | 1:N
                         v                         v
              +--------------------+    +--------------------+
              | extracted_records  |    | verification_logs  |
              +--------------------+    +--------------------+
              | id (PK)            |    | id (PK)            |
              | document_id (FK)   |    | document_id (FK)   |
              | section            |    | extracted_field_id |
              | record_number      |    | original_value     |
              | page_number        |    | corrected_value    |
              | created_at         |    | verified_by        |
              +---------+----------+    | verified_at        |
                        |               | notes              |
                        | 1:N           +--------------------+
                        v
              +--------------------+
              |  extracted_fields  |
              +--------------------+
              | id (PK)            |
              | record_id (FK)     |
              | field_name         |
              | original_value     |
              | current_value      |
              | confidence_score   |
              | verification_status|
              | source_coordinates |
              +--------------------+
```

## Indexes and Constraints
- `documents(file_hash)`: Indexed for instant duplicate detection.
- `documents(job_id)`: Foreign key index for batch lookups.
- `documents(status)`: Indexed for review queue and monitor polling.
- `extracted_records(document_id)`: Cascading delete on document removal.
- `extracted_fields(record_id)`: Cascading delete on record removal.
- `extracted_fields(verification_status)`: Indexed for fast filtering of fields needing review.

