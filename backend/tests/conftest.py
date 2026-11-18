"""
Pytest fixtures for AI Document Intelligence tests.
"""
import pytest
from pathlib import Path
import pymupdf as fitz
from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        # Seed test admin user
        if not User.query.filter_by(username="testadmin").first():
            u = User(username="testadmin", email="admin@test.com", role="admin")
            u.set_password("AdminPass123")
            db.session.add(u)
            db.session.commit()

        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    """Create a realistic single-page test PDF document."""
    pdf_path = tmp_path / "sample_ccms_report.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size

    # Insert sample text
    text = (
        "CCMS INSTALLATION REPORT\n"
        "Ward Number: 64\n"
        "Installed Pole Number: 0860\n"
        "Contractor Name: Sri Lakshmi Electricals\n"
        "Installation Date: 14/11/2026\n"
        "Phase Connection: 3 Phase 415V\n"
        "CCMS Box Serial No: CX-9028-B\n"
        "Supervisor Signature: Verified by K. Rao\n"
    )
    page.insert_text((50, 72), text, fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path

