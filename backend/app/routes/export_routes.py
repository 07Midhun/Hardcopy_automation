"""
Export Routes.
Generates and serves the consolidated Excel workbook with EXACTLY ONE worksheet ('Consolidated_Data').
"""
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file
from backend.app.services.excel_service import ExcelService
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)
export_bp = Blueprint("export", __name__)


@export_bp.route("/api/export/consolidated", methods=["GET"])
def api_export_consolidated():
    """
    Generate and download the consolidated Excel workbook.
    Worksheet: 'Consolidated_Data'
    Query Params:
      - job_id (optional): Filter to a specific batch
    """
    job_id = request.args.get("job_id")
    layout = request.args.get("format", "tabular").lower()
    if layout not in ("tabular", "normalized"):
        layout = "tabular"
    try:
        excel_path = ExcelService.generate_consolidated_workbook(job_id=job_id, layout=layout).resolve()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fresh_download_name = f"{excel_path.stem}_{timestamp}.xlsx"
        response = send_file(
            str(excel_path),
            as_attachment=True,
            download_name=fresh_download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except ValueError as val_err:
        logger.warning(f"Export validation failed: {val_err}")
        return jsonify({"error": str(val_err)}), 400
    except Exception as e:
        logger.error(f"Excel export failed: {e}", exc_info=True)
        return jsonify({"error": f"Failed to generate Excel export: {str(e)}"}), 500
