"""
Consolidated Excel Export Service.
Generates EXACTLY ONE workbook containing EXACTLY ONE worksheet named 'Consolidated_Data'.
Employs memory-efficient streaming, freeze panes, bold styled headers, auto-filters,
and strict text-formatting to prevent stripping leading zeros or converting numbers to scientific notation.
"""
import re
from pathlib import Path
from typing import Optional, List, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from backend.app.extensions import db
from backend.app.models.document import Document
from backend.app.models.extracted_record import ExtractedRecord
from backend.app.models.extracted_field import ExtractedField
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

EXCEL_MAX_ROW_LIMIT = 1048576
WORKSHEET_NAME = "Consolidated_Data"

COLUMNS = [
    "Document ID",
    "Source Filename",
    "Document Type",
    "Page Number",
    "Section",
    "Record Number",
    "Field Name",
    "Extracted Value",
    "Confidence Score",
    "Verification Status"
]


class ExcelService:
    """Consolidated Excel Workbook Generation."""

    # Canonical aliases so minor label variations merge cleanly into one column
    FIELD_ALIASES = {
        "sl.no": "Sl.No",
        "sl no": "Sl.No",
        "s.no": "Sl.No",
        "pole no": "Pole No",
        "pole number": "Pole No",
        "pole id": "Pole No",
        "arm count": "Arm Count",
        "existing led / new led / svl / non led": "Existing LED / New LED / Non LED",
        "existing led / new led / non led": "Existing LED / New LED / Non LED",
        "existing led / new led /svl / non led": "Existing LED / New LED / Non LED",
        "lamp type": "Existing LED / New LED / Non LED",
        "lamp burning status (yes / no)": "Lamp Burning Status (Yes/No)",
        "lamp burning status (yes/no)": "Lamp Burning Status (Yes/No)",
        "burning status": "Lamp Burning Status (Yes/No)",
        "connected lamp wattages": "Connected Lamp Wattages",
        "connected lamp wattage": "Connected Lamp Wattages",
        "total wattage": "Total Wattage",
        "total non - burning load in kw": "Total Non-Burning load in KW",
        "total non-burning load in kw": "Total Non-Burning load in KW",
        "voltage (v)": "Voltage",
        "voltage": "Voltage",
        "current (a)": "Current",
        "current": "Current",
        "power factor (pf)": "PF",
        "pf": "PF",
        "power (kw)": "Power(kW)",
        "power(kw)": "Power(kW)",
    }

    PREFERRED_FIELD_ORDER = [
        # Primary Table Columns (first for immediate readability)
        "Sl.No",
        "Pole No",
        "Arm Count",
        "Existing LED / New LED / Non LED",
        "Lamp Burning Status (Yes/No)",
        "Connected Lamp Wattages",
        "Total Wattage",
        # Page General Information
        "Constituency & Ward Number",
        "Constituency",
        "Ward Number",
        "Date",
        "Installed Pole Number",
        "Old Switch Point Number",
        "New-CCMS UID No",
        "BESCOM Meter Sl.Number",
        "BESCOM Meter (Working Status)",
        "Is it CT meter ?",
        "Supply Input (OH/UG/ABC)",
        "Transformer Number",
        "RR Number",
        "Contractor Name",
        "Site Incharge",
        "SLC Earthing Completed? (Y/N)",
        # Electrical Meter & Load Summary
        "Voltage",
        "Current",
        "PF",
        "Power(kW)",
        "Total Burning load in KW",
        "Total Non-Burning load in KW",
        "Total Load in KW",
        "Difference in Power",
        "Installer Name & Sign",
    ]

    EXCLUDED_TABULAR_FIELDS = {
        "contractor name",
        "site incharge",
    }

    @classmethod
    def format_ward(cls, val: Any) -> str:
        if not val:
            return ""
        s = str(val).strip()
        m = re.search(r'\b(?:W(?:ard)?\s*[-_.]?\s*(\d+)|\b(\d+)\s*Ward|No\.?\s*(\d+))\b', s, re.IGNORECASE)
        if m:
            num = m.group(1) or m.group(2) or m.group(3)
            return f"W{int(num)}"
        m2 = re.search(r'\b0*(\d+)\b', s)
        if m2:
            return f"W{int(m2.group(1))}"
        return s.upper()

    @classmethod
    def format_sp_no(cls, val: Any) -> str:
        if not val:
            return "SP001"
        clean = str(val).strip()
        m = re.search(r'\b(?:SP)?0*(\d+)\b', clean, re.IGNORECASE)
        if m:
            return f"SP{int(m.group(1)):03d}"
        return clean.upper()

    @classmethod
    def format_pole_id(cls, val: Any) -> str:
        if not val or str(val).strip() in ('-', '', 'None', 'null'):
            return "-"
        clean = str(val).strip()
        # If entry indicates missing/blank pole (e.g. "P - 33", "- SP-31", "-")
        if re.match(r'^(?:P\s*[-–/]|[-–/])', clean):
            return "-"
        # Match leading pole number (e.g. "P 514 - 33", "663 SP- 39", "P0185", "507", "P 736 SP-41")
        m = re.search(r'(?:P\s*|Pole\s*)?0*(\d+)', clean, re.IGNORECASE)
        if m:
            return f"P{int(m.group(1)):04d}"
        if clean.upper().startswith('P'):
            return clean.upper()
        return f"P{clean.upper()}"

    @classmethod
    def format_existing_new(cls, val: Any) -> str:
        if not val:
            return "NEW"
        clean = str(val).strip().upper()
        if "NEW" in clean:
            return "NEW"
        if "OLD" in clean or "EXISTING" in clean:
            return "EXISTING"
        if "NON" in clean:
            return "NON LED"
        return clean

    @classmethod
    def format_burning_status(cls, val: Any) -> str:
        if not val:
            return "YES"
        clean = str(val).strip().upper()
        if clean in ('Y', 'YES', '1', 'TRUE'):
            return "YES"
        if clean in ('N', 'NO', '0', 'FALSE'):
            return "NO"
        return clean

    @classmethod
    def format_wattage(cls, val: Any) -> str:
        if not val:
            return ""
        clean = str(val).strip()
        m = re.match(r'^(\d+)\s*[Ww]$', clean)
        if m:
            return m.group(1)
        return clean

    @classmethod
    def _canonical_field_name(cls, name: str) -> str:
        clean = " ".join(str(name).strip().split())
        return cls.FIELD_ALIASES.get(clean.lower(), clean)

    @classmethod
    def generate_consolidated_workbook(
        cls,
        job_id: Optional[str] = None,
        target_path: Optional[Path] = None,
        include_failed_placeholders: bool = True,
        layout: str = "tabular"
    ) -> Path:
        """
        Generate consolidated workbook containing exactly ONE worksheet named 'Consolidated_Data'.
        Supports:
          - layout='tabular' / 'survey' : The exact 9-column Survey Sheet format with merged PANEL UID.
          - layout='extended'           : Wide horizontal table with all columns side-by-side.
          - layout='normalized'         : Vertical 10-column key-value audit format (one row per field).
        """
        # Default to the latest active/completed job if no job_id is specified
        # This guarantees that exporting only produces the current uploaded batch, not all historical wards
        if not job_id or str(job_id).strip() == "" or str(job_id).lower() == "latest":
            from backend.app.models.processing_job import ProcessingJob
            latest_job = (
                ProcessingJob.query
                .filter(ProcessingJob.total_documents > 0)
                .order_by(ProcessingJob.created_at.desc())
                .first()
            )
            if latest_job:
                job_id = latest_job.id
            else:
                job_id = None
        elif str(job_id).lower() == "all":
            job_id = None

        if layout in ("tabular", "survey"):
            return cls.generate_tabular_workbook(
                job_id=job_id,
                target_path=target_path
            )
        elif layout == "extended":
            return cls.generate_extended_tabular_workbook(
                job_id=job_id,
                target_path=target_path,
                include_failed_placeholders=include_failed_placeholders
            )
        if target_path is None:
            from flask import current_app
            from backend.app.config import Config
            configured_dir = current_app.config.get("EXPORTS_DIR", Config.EXPORTS_DIR) if current_app else Config.EXPORTS_DIR
            export_dir = Path(configured_dir).resolve()
            export_dir.mkdir(parents=True, exist_ok=True)
            filename = f"Consolidated_Export_{job_id or 'All'}.xlsx"
            target_path = export_dir / filename
        else:
            target_path = Path(target_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating consolidated Excel report to {target_path}...")

        # 1. Query extracted records
        query = db.session.query(
            Document.id.label("doc_id"),
            Document.original_filename,
            Document.document_type,
            Document.status.label("doc_status"),
            Document.error_message,
            ExtractedRecord.page_number,
            ExtractedRecord.section,
            ExtractedRecord.record_number,
            ExtractedField.field_name,
            ExtractedField.current_value,
            ExtractedField.confidence_score,
            ExtractedField.verification_status
        ).join(
            ExtractedRecord, Document.id == ExtractedRecord.document_id, isouter=True
        ).join(
            ExtractedField, ExtractedRecord.id == ExtractedField.record_id, isouter=True
        )

        if job_id:
            query = query.filter(Document.job_id == job_id)

        # Order for strict traceability:
        # Document ID -> Page Number -> Section Hierarchy (General Info -> Tables -> Meter Panels) -> Record Number -> Field ID
        from sqlalchemy import case
        section_priority = case(
            (ExtractedRecord.section == "General Information", 1),
            (ExtractedRecord.section.ilike("%Table%"), 2),
            else_=3
        )
        query = query.order_by(
            Document.id,
            ExtractedRecord.page_number,
            section_priority,
            ExtractedRecord.record_number,
            ExtractedField.id
        )

        rows_data = query.all()

        # Check total rows against Excel row limit
        total_data_rows = len(rows_data)
        if total_data_rows + 1 > EXCEL_MAX_ROW_LIMIT:
            raise ValueError(
                f"Export exceeds Excel's maximum worksheet limit of {EXCEL_MAX_ROW_LIMIT:,} rows "
                f"(Attempted: {total_data_rows + 1:,}). Please filter by job batch."
            )

        # 2. Build OpenPyXL Workbook with EXACTLY ONE worksheet
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = WORKSHEET_NAME

        # Style definitions
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Enterprise Blue
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        thin_border = Border(
            left=Side(style="thin", color="E5E7EB"),
            right=Side(style="thin", color="E5E7EB"),
            top=Side(style="thin", color="E5E7EB"),
            bottom=Side(style="thin", color="E5E7EB")
        )

        # Write Headers
        ws.append(COLUMNS)
        for col_idx, col_name in enumerate(COLUMNS, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Track column maximum widths for auto-sizing
        col_widths = {col_idx: len(col_name) + 3 for col_idx, col_name in enumerate(COLUMNS, 1)}

        current_row = 2
        for r in rows_data:
            doc_id = str(r.doc_id)
            orig_filename = str(r.original_filename)
            doc_type = str(r.document_type or "Unidentified")

            if r.field_name is not None:
                # Document has extracted records
                page_num = r.page_number or 1
                section = str(r.section or "General Information")
                record_num = r.record_number or 1
                field_name = str(r.field_name)
                extracted_val = str(r.current_value) if r.current_value is not None else ""
                conf_score = round(float(r.confidence_score), 2) if r.confidence_score is not None else 0.0
                ver_status = str(r.verification_status or "pending")
            elif include_failed_placeholders:
                # Document failed or had 0 fields extracted - maintain traceability without discarding
                page_num = 1
                section = "System Status"
                record_num = 1
                field_name = "Processing Note"
                extracted_val = f"Document Status: {r.doc_status} ({r.error_message or 'No fields extracted'})"
                conf_score = 0.0
                ver_status = r.doc_status
            else:
                continue

            row_values = [
                doc_id,
                orig_filename,
                doc_type,
                page_num,
                section,
                record_num,
                field_name,
                extracted_val,
                conf_score,
                ver_status
            ]

            ws.append(row_values)

            # Format cells: Ensure text formatting for identifiers & extracted values
            for c_idx, val in enumerate(row_values, 1):
                cell = ws.cell(row=current_row, column=c_idx)
                cell.border = thin_border

                # Text format for Document ID, Record Number, and Extracted Value to preserve leading zeros
                if c_idx in (1, 6, 8):
                    cell.number_format = "@"

                # Numeric format for confidence score
                if c_idx == 9:
                    cell.number_format = "0.00"
                    cell.alignment = Alignment(horizontal="right")

                val_len = len(str(val)) if val is not None else 0
                if val_len + 3 > col_widths[c_idx]:
                    col_widths[c_idx] = min(60, val_len + 3)  # Cap width at 60

            current_row += 1

        # Freeze Header Row (Row 1)
        ws.freeze_panes = "A2"

        # Enable AutoFilter across all columns
        max_row = max(1, current_row - 1)
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{max_row}"

        # Apply Column Widths
        for col_idx, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = max(12, width)

        # Set row height for header
        ws.row_dimensions[1].height = 26

        wb.save(str(target_path))
        wb.close()
        logger.info(f"Consolidated Excel workbook successfully created: {target_path} ({max_row} rows)")
        return target_path

    @classmethod
    def generate_tabular_workbook(
        cls,
        job_id: Optional[str] = None,
        target_path: Optional[Path] = None,
        include_failed_placeholders: bool = True
    ) -> Path:
        """
        Generate consolidated CCMS Survey tabular workbook (EXACTLY ONE worksheet named 'Consolidated_Data').
        Matches the 10-column format:
        [WARD, PANEL UID, POLE ID, SP NO, ARM COUNT, EXISTING / NEW, BURNING STATUS, CONNECTED WATTAGE, TOTAL WATTAGE, VERIFIED STATUS]
        with PANEL UID vertically merged across all pole rows for each survey panel,
        individual cells with low confidence scores highlighted in soft yellow (FFF2CC),
        and VERIFIED STATUS marked as 'Review Required' or 'Verified'.
        """
        from collections import OrderedDict

        # Default to latest job with documents if none provided or "latest"
        if not job_id or str(job_id).strip() == "" or str(job_id).lower() == "latest":
            from backend.app.models.processing_job import ProcessingJob
            latest_job = (
                ProcessingJob.query
                .filter(ProcessingJob.total_documents > 0)
                .order_by(ProcessingJob.created_at.desc())
                .first()
            )
            if latest_job:
                job_id = latest_job.id
            else:
                job_id = None
        elif str(job_id).lower() == "all":
            job_id = None

        if target_path is None:
            from flask import current_app
            from backend.app.config import Config
            configured_dir = current_app.config.get("EXPORTS_DIR", Config.EXPORTS_DIR) if current_app else Config.EXPORTS_DIR
            export_dir = Path(configured_dir).resolve()
            export_dir.mkdir(parents=True, exist_ok=True)
            filename = f"Consolidated_Export_{job_id or 'All'}.xlsx"
            target_path = export_dir / filename
        else:
            target_path = Path(target_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating Survey consolidated Excel report to {target_path} (job_id={job_id})...")

        query = db.session.query(
            Document.id.label("doc_id"),
            Document.original_filename,
            ExtractedRecord.id.label("record_id"),
            ExtractedRecord.page_number,
            ExtractedRecord.section,
            ExtractedRecord.record_number,
            ExtractedField.field_name,
            ExtractedField.current_value,
            ExtractedField.confidence_score,
            ExtractedField.verification_status
        ).join(
            ExtractedRecord, Document.id == ExtractedRecord.document_id, isouter=True
        ).join(
            ExtractedField, ExtractedRecord.id == ExtractedField.record_id, isouter=True
        )

        if job_id:
            query = query.filter(Document.job_id == job_id)

        query = query.order_by(
            Document.id,
            ExtractedRecord.page_number,
            ExtractedRecord.record_number,
            ExtractedField.id
        )

        rows = query.all()

        pages = OrderedDict()
        for r in rows:
            page_key = (r.doc_id, r.page_number or 1)
            if page_key not in pages:
                pages[page_key] = {"context": {}, "tables": OrderedDict()}
            if not r.field_name:
                continue
            sec = str(r.section or "").lower()
            f_entry = {
                "val": r.current_value,
                "conf": r.confidence_score,
                "status": r.verification_status
            }
            if "table" in sec:
                pages[page_key]["tables"].setdefault(r.record_number, {})[r.field_name] = f_entry
            else:
                pages[page_key]["context"][r.field_name] = f_entry

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = WORKSHEET_NAME

        headers = [
            "WARD",
            "PANEL UID",
            "POLE ID",
            "SP NO",
            "ARM COUNT",
            "EXISTING / NEW",
            "BURNING STATUS",
            "CONNECTED WATTAGE",
            "TOTAL WATTAGE",
            "VERIFIED STATUS"
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="000000")
        header_alignment = Alignment(horizontal="center", vertical="center")

        thick_black_side = Side(style="medium", color="000000")
        thin_black_side = Side(style="thin", color="000000")

        header_border = Border(left=thin_black_side, right=thin_black_side, top=thick_black_side, bottom=thick_black_side)
        cell_border = Border(left=thin_black_side, right=thin_black_side, top=thin_black_side, bottom=thin_black_side)

        data_font = Font(name="Calibri", size=10, color="000000")
        review_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

        def is_low_conf(f_dict: Optional[dict]) -> bool:
            if not f_dict:
                return False
            status = str(f_dict.get("status") or "").lower()
            if status in ("review_required", "unreadable", "failed", "low_confidence"):
                return True
            conf = f_dict.get("conf")
            if conf is not None and conf < 0.80:
                return True
            return False

        ws.append(headers)
        ws.row_dimensions[1].height = 24
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = header_border

        current_row = 2
        for page_key, pdata in pages.items():
            ctx = pdata["context"]
            tbl = pdata["tables"]
            if not tbl:
                continue

            ward_f = ctx.get("Ward Number") or ctx.get("Constituency & Ward Number") or ctx.get("Ward")
            ward = cls.format_ward(ward_f.get("val") if ward_f else None)

            panel_f = ctx.get("New-CCMS UID No") or ctx.get("New CCMS UID No") or ctx.get("Panel UID") or ctx.get("CCMS UID")
            panel_uid = str(panel_f.get("val") if panel_f else "").strip()

            sp_f = ctx.get("Old Switch Point Number") or ctx.get("SP NO") or ctx.get("Switch Point No")
            sp_no = cls.format_sp_no(sp_f.get("val") if sp_f else None)

            start_row_for_page = current_row

            for r_num in sorted(tbl.keys()):
                r_fields = tbl[r_num]
                pole_f = r_fields.get("Pole No") or r_fields.get("Pole ID")
                pole_id = cls.format_pole_id(pole_f.get("val") if pole_f else None)

                arm_f = r_fields.get("Arm Count")
                arm_count = str(arm_f.get("val") if arm_f else "1").strip() or "1"

                ex_new_f = r_fields.get("Existing LED / New LED / Non LED") or r_fields.get("Lamp Type")
                ex_new = cls.format_existing_new(ex_new_f.get("val") if ex_new_f else None)

                burn_f = r_fields.get("Lamp Burning Status (Yes/No)") or r_fields.get("Lamp Burning Status (Yes / No)")
                burn_status = cls.format_burning_status(burn_f.get("val") if burn_f else None)

                conn_f = r_fields.get("Connected Lamp Wattages") or r_fields.get("Connected Lamp Wattage")
                conn_w = cls.format_wattage(conn_f.get("val") if conn_f else "56")

                tot_f = r_fields.get("Total Wattage")
                tot_w = cls.format_wattage(tot_f.get("val") if tot_f else conn_w)

                # Check if any field in this row is low confidence
                row_fields_conf = [
                    is_low_conf(pole_f),
                    is_low_conf(arm_f),
                    is_low_conf(ex_new_f),
                    is_low_conf(burn_f),
                    is_low_conf(conn_f),
                    is_low_conf(tot_f)
                ]
                has_low_conf = any(row_fields_conf) or is_low_conf(ward_f) or is_low_conf(panel_f) or is_low_conf(sp_f)

                verified_status = "Review Required" if has_low_conf else "Verified"

                row_vals = [
                    ward,
                    panel_uid,
                    pole_id,
                    sp_no,
                    arm_count,
                    ex_new,
                    burn_status,
                    conn_w,
                    tot_w,
                    verified_status
                ]
                ws.append(row_vals)

                for col_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.font = data_font
                    cell.border = cell_border

                    # Alignment and number formats
                    if col_idx in (1, 3, 4, 6, 7):
                        cell.alignment = Alignment(horizontal="left", vertical="center")
                        cell.number_format = "@"
                    elif col_idx in (5, 8, 9):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if str(cell.value).isdigit():
                            cell.number_format = "0"
                    elif col_idx in (2, 10):
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        cell.number_format = "@"

                    # Low confidence values highlighted in yellow (FFF2CC)
                    if col_idx == 1 and is_low_conf(ward_f):
                        cell.fill = review_fill
                    elif col_idx == 3 and is_low_conf(pole_f):
                        cell.fill = review_fill
                    elif col_idx == 4 and is_low_conf(sp_f):
                        cell.fill = review_fill
                    elif col_idx == 5 and is_low_conf(arm_f):
                        cell.fill = review_fill
                    elif col_idx == 6 and is_low_conf(ex_new_f):
                        cell.fill = review_fill
                    elif col_idx == 7 and is_low_conf(burn_f):
                        cell.fill = review_fill
                    elif col_idx == 8 and is_low_conf(conn_f):
                        cell.fill = review_fill
                    elif col_idx == 9 and is_low_conf(tot_f):
                        cell.fill = review_fill
                    elif col_idx == 10 and has_low_conf:
                        cell.fill = review_fill

                current_row += 1

            end_row_for_page = current_row - 1
            if end_row_for_page > start_row_for_page:
                ws.merge_cells(start_row=start_row_for_page, end_row=end_row_for_page, start_column=2, end_column=2)
                for r in range(start_row_for_page, end_row_for_page + 1):
                    c = ws.cell(row=r, column=2)
                    c.border = cell_border
                    c.alignment = Alignment(horizontal="center", vertical="center")
                    if is_low_conf(panel_f):
                        c.fill = review_fill

        col_widths = [10, 20, 14, 12, 14, 18, 18, 20, 16, 18]
        for col_idx, width in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        wb.save(str(target_path))
        wb.close()
        logger.info(f"Survey format consolidated Excel workbook created: {target_path} ({current_row - 2} records)")
        return target_path

    @classmethod
    def generate_extended_tabular_workbook(
        cls,
        job_id: Optional[str] = None,
        target_path: Optional[Path] = None,
        include_failed_placeholders: bool = True
    ) -> Path:
        """
        Generate wide horizontal tabular workbook (EXACTLY ONE worksheet named 'Consolidated_Data').
        Outputs ONE row per table record (e.g. one row per Pole with Sl.No, Pole No, Arm Count,
        Existing LED / New LED / Non LED, Lamp Burning Status, Wattages side-by-side) enriched
        with that page's General Information and Electrical Meter readings.
        Dynamically adapts columns to any document layout without requiring fixed templates.
        """
        from collections import OrderedDict
        from sqlalchemy import case

        if target_path is None:
            from flask import current_app
            from backend.app.config import Config
            configured_dir = current_app.config.get("EXPORTS_DIR", Config.EXPORTS_DIR) if current_app else Config.EXPORTS_DIR
            export_dir = Path(configured_dir).resolve()
            export_dir.mkdir(parents=True, exist_ok=True)
            filename = f"Consolidated_Export_{job_id or 'All'}.xlsx"
            target_path = export_dir / filename
        else:
            target_path = Path(target_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating tabular consolidated Excel report to {target_path}...")

        section_priority = case(
            (ExtractedRecord.section == "General Information", 1),
            (ExtractedRecord.section.ilike("%Table%"), 2),
            else_=3
        )
        query = db.session.query(
            Document.id.label("doc_id"),
            Document.original_filename,
            Document.document_type,
            Document.status.label("doc_status"),
            Document.error_message,
            ExtractedRecord.id.label("record_id"),
            ExtractedRecord.page_number,
            ExtractedRecord.section,
            ExtractedRecord.record_number,
            ExtractedField.field_name,
            ExtractedField.current_value,
            ExtractedField.confidence_score,
            ExtractedField.verification_status
        ).join(
            ExtractedRecord, Document.id == ExtractedRecord.document_id, isouter=True
        ).join(
            ExtractedField, ExtractedRecord.id == ExtractedField.record_id, isouter=True
        )

        if job_id:
            query = query.filter(Document.job_id == job_id)

        query = query.order_by(
            Document.id,
            ExtractedRecord.page_number,
            section_priority,
            ExtractedRecord.record_number,
            ExtractedField.id
        )

        rows_data = query.all()

        # Group fields by (doc_id, page_number) separating page-level context from table rows
        pages_map: OrderedDict = OrderedDict()
        discovered_fields: set = set()

        for r in rows_data:
            doc_id = str(r.doc_id)
            page_num = r.page_number or 1
            page_key = (doc_id, page_num)

            if page_key not in pages_map:
                pages_map[page_key] = {
                    "doc_id": doc_id,
                    "filename": str(r.original_filename),
                    "doc_type": str(r.document_type or "Unidentified"),
                    "doc_status": str(r.doc_status or "pending"),
                    "error_message": r.error_message,
                    "page_number": page_num,
                    "context": {},  # field_name -> (val, conf, status)
                    "table_records": OrderedDict()  # (record_number, record_id) -> {field_name -> (val, conf, status)}
                }

            if r.field_name is None:
                continue

            canon_name = cls._canonical_field_name(r.field_name)
            if canon_name.lower() in cls.EXCLUDED_TABULAR_FIELDS:
                continue
            val = str(r.current_value) if r.current_value is not None else ""
            conf = float(r.confidence_score) if r.confidence_score is not None else 0.0
            status = str(r.verification_status or "pending")
            discovered_fields.add(canon_name)

            sec_lower = str(r.section or "").lower()
            if "table" in sec_lower:
                rec_key = (r.record_number or 1, r.record_id)
                if rec_key not in pages_map[page_key]["table_records"]:
                    pages_map[page_key]["table_records"][rec_key] = {}
                pages_map[page_key]["table_records"][rec_key][canon_name] = (val, conf, status)
            else:
                pages_map[page_key]["context"][canon_name] = (val, conf, status)

        # Build ordered dynamic column list
        ordered_dynamic_cols: List[str] = [
            f for f in cls.PREFERRED_FIELD_ORDER if f in discovered_fields
        ]
        remaining_cols = sorted(discovered_fields - set(ordered_dynamic_cols))
        ordered_dynamic_cols.extend(remaining_cols)

        meta_prefix = ["Source Filename", "Page Number"]
        meta_suffix = ["Confidence Score", "Verification Status"]
        all_headers = meta_prefix + ordered_dynamic_cols + meta_suffix

        # Assemble tabular output rows
        output_rows = []
        for page_entry in pages_map.values():
            ctx = page_entry["context"]
            t_recs = page_entry["table_records"]

            if t_recs:
                for rec_idx, (_, rec_fields) in enumerate(t_recs.items(), 1):
                    merged = dict(ctx)
                    merged.update(rec_fields)
                    if "Sl.No" in ordered_dynamic_cols and not merged.get("Sl.No", ("",))[0]:
                        merged["Sl.No"] = (str(rec_idx), 1.0, "verified")
                    output_rows.append((page_entry, merged))
            elif ctx:
                output_rows.append((page_entry, ctx))
            elif include_failed_placeholders:
                placeholder = {
                    "Processing Note": (
                        f"Document Status: {page_entry['doc_status']} ({page_entry['error_message'] or 'No fields extracted'})",
                        0.0,
                        page_entry["doc_status"]
                    )
                }
                if "Processing Note" not in ordered_dynamic_cols:
                    ordered_dynamic_cols.append("Processing Note")
                    all_headers = meta_prefix + ordered_dynamic_cols + meta_suffix
                output_rows.append((page_entry, placeholder))

        if len(output_rows) + 1 > EXCEL_MAX_ROW_LIMIT:
            raise ValueError(
                f"Export exceeds Excel's maximum worksheet limit of {EXCEL_MAX_ROW_LIMIT:,} rows."
            )

        # Build Excel workbook with EXACTLY ONE worksheet named 'Consolidated_Data'
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = WORKSHEET_NAME

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        review_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
        error_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

        thin_border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB")
        )

        # Write headers
        ws.append(all_headers)
        for col_idx in range(1, len(all_headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        col_widths = {idx: min(35, len(name) + 4) for idx, name in enumerate(all_headers, 1)}

        current_row = 2
        for page_entry, merged_fields in output_rows:
            # Compute row-level confidence & verification status
            confs = [v[1] for v in merged_fields.values() if v[0] != ""]
            statuses = [v[2] for v in merged_fields.values() if v[0] != ""]
            row_conf = round(min(confs), 2) if confs else 0.0
            if "unreadable" in statuses:
                row_status = "unreadable"
            elif "review_required" in statuses:
                row_status = "review_required"
            elif statuses:
                row_status = "verified"
            else:
                row_status = page_entry["doc_status"]

            row_values = [
                page_entry["filename"],
                page_entry["page_number"],
            ]
            for col_name in ordered_dynamic_cols:
                entry = merged_fields.get(col_name)
                row_values.append(entry[0] if entry else "")
            row_values.extend([row_conf, row_status])

            ws.append(row_values)

            is_zebra = (current_row % 2 == 1)
            for c_idx, val in enumerate(row_values, 1):
                cell = ws.cell(row=current_row, column=c_idx)
                cell.border = thin_border
                if is_zebra:
                    cell.fill = zebra_fill

                # Preserve leading zeros on all extracted value columns
                if len(meta_prefix) < c_idx <= len(meta_prefix) + len(ordered_dynamic_cols):
                    cell.number_format = "@"
                    col_name = ordered_dynamic_cols[c_idx - len(meta_prefix) - 1]
                    f_entry = merged_fields.get(col_name)
                    if f_entry:
                        if f_entry[2] == "unreadable":
                            cell.fill = error_fill
                        elif f_entry[2] == "review_required":
                            cell.fill = review_fill

                # Center narrow table columns (Page Number, Sl.No, Pole No, Arm Count, Burning Status, Wattages)
                header_label = all_headers[c_idx - 1]
                if header_label in ("Page Number", "Sl.No", "Pole No", "Arm Count", "Lamp Burning Status (Yes/No)", "Connected Lamp Wattages", "Total Wattage"):
                    cell.alignment = Alignment(horizontal="center")

                # Confidence column formatting
                if c_idx == len(all_headers) - 1:
                    cell.number_format = "0.00"
                    cell.alignment = Alignment(horizontal="right")

                # Highlight overall status cell if flagged
                if c_idx == len(all_headers):
                    cell.alignment = Alignment(horizontal="center")
                    if row_status == "review_required":
                        cell.fill = review_fill
                    elif row_status in ("unreadable", "failed"):
                        cell.fill = error_fill

                val_len = len(str(val)) if val is not None else 0
                if val_len + 3 > col_widths[c_idx]:
                    col_widths[c_idx] = min(45, val_len + 3)

            current_row += 1

        ws.freeze_panes = "A2"
        max_row = max(1, current_row - 1)
        ws.auto_filter.ref = f"A1:{get_column_letter(len(all_headers))}{max_row}"

        for col_idx, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = max(10, width)

        ws.row_dimensions[1].height = 30

        wb.save(str(target_path))
        wb.close()
        logger.info(
            f"Tabular consolidated Excel workbook created: {target_path} "
            f"({max_row - 1} records x {len(all_headers)} columns)"
        )
        return target_path
