"""
Validation Service.
Detects low-confidence handwriting, unreadable fields, missing values, and formatting anomalies.
Flags suspicious records for human review rather than fabricating or silently changing data.
"""
import re
import statistics
from typing import Optional, Tuple, List, Dict, Any
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationService:
    """Validates extracted field values and flags verification requirements."""

    DATE_PATTERNS = [
        re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$"),
        re.compile(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$")
    ]

    # Common single-digit OCR/handwriting confusion pairs
    DIGIT_CONFUSION_PAIRS = {
        ("3", "7"), ("7", "3"),
        ("3", "2"), ("2", "3"),
        ("3", "8"), ("8", "3"),
        ("5", "6"), ("6", "5"),
        ("5", "8"), ("8", "5"),
        ("0", "6"), ("6", "0"),
        ("0", "8"), ("8", "0"),
        ("1", "7"), ("7", "1"),
        ("4", "9"), ("9", "4"),
        ("8", "9"), ("9", "8"),
    }

    @classmethod
    def validate_field(
        cls,
        field_name: str,
        value: Optional[str],
        confidence: float,
        confidence_threshold: float = 0.75
    ) -> Tuple[str, Optional[str]]:
        """
        Validate single field value and return (verification_status, flag_reason).
        Statuses: 'verified', 'review_required', 'unreadable', 'missing'
        """
        if value is None or str(value).strip() == "":
            return "missing", "Field is empty or not provided in document"

        val_str = str(value).strip()

        # Check for unreadable flags
        if any(marker in val_str.lower() for marker in ["[unreadable]", "[illegible]", "???", "unreadable"]):
            return "unreadable", "Handwriting is illegible or severely degraded"

        # Check confidence score
        if confidence < confidence_threshold:
            return "review_required", f"Low confidence handwriting recognition ({confidence:.2f} < {confidence_threshold})"

        # Check Yes/No fields for common Y <-> 4 handwriting confusion
        fname_lower = field_name.lower()
        if any(kw in fname_lower for kw in ["y/n", "yes / no", "yes/no", "burning status", "earthing completed", "ct meter"]):
            if val_str.upper() not in ("Y", "N", "YES", "NO", "-"):
                return "review_required", f"Unexpected value '{val_str}' in Yes/No field (possible handwritten Y/4 confusion)"

        # Check date fields
        if "date" in fname_lower:
            if not any(pat.match(val_str) for pat in cls.DATE_PATTERNS):
                return "review_required", f"Non-standard date format: '{val_str}'"

        # Check numeric fields
        if any(kw in fname_lower for kw in ["number", "no.", "serial", "ward", "pole", "qty", "count", "measurement"]):
            # If expected numeric but contains letters mixed with digits in unusual way
            if re.search(r"[0-9]", val_str) and re.search(r"[a-z]", val_str, re.IGNORECASE):
                # Could be valid alphanumeric code (like '860/1' or 'CX-902'), check for odd characters
                if re.search(r"[\?~!@$%^&*]", val_str):
                    return "review_required", f"Suspicious special characters in numeric field: '{val_str}'"

        return "verified", None

    @classmethod
    def _is_single_digit_confusion(cls, a: str, b: str) -> bool:
        """Return True if two same-length numeric strings differ by exactly one commonly confused digit pair."""
        if len(a) != len(b) or not (a.isdigit() and b.isdigit()):
            return False
        diffs = [(ca, cb) for ca, cb in zip(a, b) if ca != cb]
        return len(diffs) == 1 and diffs[0] in cls.DIGIT_CONFUSION_PAIRS

    @classmethod
    def validate_page_table_consistency(
        cls,
        table_field_rows: List[List[Any]],
        confidence_threshold: float = 0.75
    ) -> List[Dict[str, Any]]:
        """
        Cross-row validation across all table rows on a single page.
        Detects:
          1. Pole Number sequence outliers & single-digit handwriting confusions (e.g. '338' misread as '378').
          2. Row wattage math mismatches (Arm Count * Connected Lamp Wattage != Total Wattage).
        NEVER silently overwrites values — flags anomalies as 'review_required' for human verification.
        """
        anomalies: List[Dict[str, Any]] = []

        # 1. Collect numeric pole fields across all rows on this page
        pole_entries: List[Tuple[int, Any, int, str]] = []  # (row_idx, field_obj, int_val, str_val)
        for row_idx, fields in enumerate(table_field_rows):
            field_map: Dict[str, Any] = {}
            for f in fields:
                fname = f.field_name.lower()
                if "pole" in fname and "installed" not in fname:
                    field_map["pole"] = f
                    raw = (f.current_value or "").strip()
                    if raw.isdigit():
                        pole_entries.append((row_idx, f, int(raw), raw))
                elif "arm" in fname and "count" in fname:
                    field_map["arm"] = f
                elif "connected" in fname and "watt" in fname:
                    field_map["connected_w"] = f
                elif "total" in fname and "watt" in fname:
                    field_map["total_w"] = f

            # 2. Row-level wattage arithmetic check: Arm Count * Connected Wattage == Total Wattage
            if all(k in field_map for k in ("arm", "connected_w", "total_w")):
                arm_v = (field_map["arm"].current_value or "").strip()
                conn_v = (field_map["connected_w"].current_value or "").strip()
                tot_v = (field_map["total_w"].current_value or "").strip()
                try:
                    arm_n = float(arm_v)
                    conn_n = float(conn_v)
                    tot_n = float(tot_v)
                    if abs((arm_n * conn_n) - tot_n) > 1.0:
                        for target_f in (field_map["connected_w"], field_map["total_w"]):
                            target_f.verification_status = "review_required"
                            target_f.confidence_score = min(target_f.confidence_score or 0.65, round(confidence_threshold - 0.15, 2))
                        anomalies.append({
                            "row_index": row_idx + 1,
                            "field": "Total Wattage",
                            "value": tot_v,
                            "reason": f"Wattage mismatch: {arm_v} x {conn_v} != {tot_v}"
                        })
                except ValueError:
                    pass

        # 3. Pole cluster outlier + single-digit handwriting confusion check
        if len(pole_entries) >= 4:
            nums = [e[2] for e in pole_entries]
            median_val = statistics.median(nums)
            abs_devs = [abs(n - median_val) for n in nums]
            mad = statistics.median(abs_devs)
            # Threshold: at least 20 away from median AND > 3x MAD
            outlier_threshold = max(20.0, 3.0 * max(mad, 5.0))

            for idx, (row_idx, field_obj, num_val, str_val) in enumerate(pole_entries):
                dist_from_median = abs(num_val - median_val)
                if dist_from_median >= outlier_threshold:
                    # Check if immediate neighbors are inside the cluster and differ by 1 confusable digit
                    neighbor_hint = None
                    for offset in (-1, 1):
                        n_idx = idx + offset
                        if 0 <= n_idx < len(pole_entries):
                            _, _, n_num, n_str = pole_entries[n_idx]
                            if abs(n_num - median_val) < outlier_threshold and cls._is_single_digit_confusion(str_val, n_str):
                                neighbor_hint = n_str
                                break

                    field_obj.verification_status = "review_required"
                    field_obj.confidence_score = min(field_obj.confidence_score or 0.65, round(confidence_threshold - 0.15, 2))
                    reason = (
                        f"Pole '{str_val}' is an outlier vs page median {median_val:.0f}"
                        + (f" and differs by 1 confusable handwritten digit from adjacent pole '{neighbor_hint}'" if neighbor_hint else "")
                    )
                    logger.warning(f"[Cross-Row Anomaly] Row {row_idx + 1}: {reason}")
                    anomalies.append({
                        "row_index": row_idx + 1,
                        "field": field_obj.field_name,
                        "value": str_val,
                        "reason": reason
                    })

        return anomalies

