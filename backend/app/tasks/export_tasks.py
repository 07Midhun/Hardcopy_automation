"""
Celery tasks for asynchronous consolidated Excel report generation.
"""
from backend.app.tasks.celery_app import celery_app
from backend.app.services.excel_service import ExcelService
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task
def generate_consolidated_excel_task(job_id=None):
    """Asynchronously compile consolidated workbook."""
    logger.info(f"Starting Excel compilation task (Job: {job_id or 'All'})...")
    path = ExcelService.generate_consolidated_workbook(job_id=job_id)
    return {"status": "success", "file_path": str(path)}

