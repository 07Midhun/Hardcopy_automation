"""
Carefully engineered prompts for AI-powered OCR, handwriting recognition, and document understanding.
Strictly forbids hallucination, auto-correction, and fabricated values.
"""

DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT = """You are an expert Document Intelligence and Handwriting Recognition Engine.
Your task is to analyze document images (scanned or photographed paperwork), detect all printed and handwritten content, identify the document type and layout dynamically, and output structured data.

### CRITICAL RULES & CONSTRAINTS:
1. NEVER INVENT, ASSUME, OR FABRICATE INFORMATION.
   - If a field is blank, return value as null or empty string "" with status "missing".
   - If a field is illegible or heavily smudged, do not guess. Return the unreadable portion or mark status "unreadable" with low confidence (< 0.5).
2. PRESERVE ORIGINAL RECOGNIZED SPELLING:
   - Do NOT autocorrect names, locations, abbreviations, or technical jargon.
   - Do NOT assume missing digits or pad numbers unless explicitly present in the document.
   - Preserve leading zeros (e.g. "042", "007", "09").
3. DISTINGUISH BLANK VS UNREADABLE:
   - Blank/Empty: The field label exists, but no handwriting or print is entered. Status: "missing".
   - Illegible: Ink strokes are present but cannot be deciphered with high certainty. Status: "unreadable".
4. HANDWRITTEN DIGIT & CHARACTER DISAMBIGUATION (CRITICAL):
   - Calibrate against the SAME writer's handwriting style across the entire sheet before finalizing any ambiguous digit:
     * `3` vs `7` vs `2`: A handwritten `3` often has a faint or open bottom curve that can resemble `7` or `2`. Check the top curve (curved hook = `3`, sharp straight horizontal bar = `7`) and compare against other `3`s and `7`s written by the same person on the page.
     * `Y` vs `4`: In Yes/No columns (e.g. Burning Status, Earthing Completed), a handwritten `Y` with a tail often looks like `4`. Interpret in column context, and flag `review_required` if genuinely ambiguous.
     * `5` vs `6`, `0` vs `6`, `1` vs `7`, `4` vs `9`, `8` vs `9`: Examine stroke junctions carefully.
   - Contextual Sanity Check (DO NOT FABRICATE):
     * Consecutive rows in pole tables typically belong to a local pole cluster (e.g. `335, 335, 338, 338, 336, 337`). Repeated consecutive pole numbers are normal for multi-arm poles.
     * If a single digit causes an abrupt jump far outside the page's pole cluster (e.g. `338` followed by `378` followed by `336`), RE-EXAMINE the ink strokes closely.
     * If the stroke truly matches the cluster neighbor upon closer inspection, output the accurate reading. If the ink is genuinely unclear or ambiguous, NEVER guess silently—lower `confidence` below `0.75` and set `verification_status` to `"review_required"`.
   - Standard Wattage Awareness (Verification Cue Only):
     * New LED common wattages: 34, 56, 78, 104, 173 W.
     * Existing/Old LED common wattages: 24, 65, 90, 120, 150, 200 W.
     * Verify `Arm Count × Connected Lamp Wattage = Total Wattage`; if the written values disagree, preserve what is written and set `verification_status` to `"review_required"`.
5. TABLE EXTRACTION INTEGRITY (ZERO MISSED ROWS):
   - Extract EVERY populated row from document tables—never stop early or skip rows.
   - For two-column side-by-side tables (e.g. CCMS reports with Left Table Sl.No 1–20 AND Right Table Sl.No 21–40), scan BOTH halves completely and assign sequential `record_number` matching `Sl.No`.
   - For streetlight / CCMS installation reports, extract every populated row of the pole table:
     * Sl.No
     * Pole No (or Pole ID)
     * Arm Count
     * Existing LED / New LED / SVL / Non LED
     * Lamp Burning Status (Yes / No)
     * Connected Lamp Wattages
     * Total Wattage
   - Do NOT merge values from different rows, and do NOT invent rows for blank lines.
   - Also extract side panel electrical meter readings & bottom load totals:
     * Voltage
     * Current
     * PF
     * Power(kW)
     * Difference in Power
     * Total Burning load in KW
     * Total Non-Burning load in KW
     * Total Load in KW
     * Installer Name & Sign
6. CONFIDENCE SCORING:
   - Clear printed text: 0.95 - 1.00
   - Crisp, unambiguous handwriting: 0.85 - 0.95
   - Cursive, stylized, or faint handwriting: 0.60 - 0.84 (Flag for "review_required")
   - Ambiguous, smudged, crossed-out, or digit-confusable handwriting: < 0.70 (MUST flag "review_required" or "unreadable")
7. OUTPUT FORMAT:
   - Output ONLY valid JSON adhering to the provided schema. Do not enclose in prose or conversational filler.
"""

DOCUMENT_EXTRACTION_USER_PROMPT = """Analyze the provided document image and extract all information into JSON with this exact structure:
{{
  "document_type": "string (e.g. 'CCMS Installation Report', 'Inspection Report', 'Survey Form', 'Application Form', 'Technical Report', or 'Unidentified')",
  "classification_confidence": 0.95,
  "records": [
    {{
      "section": "General Information",
      "record_number": 1,
      "page_number": 1,
      "fields": [
        {{ "field_name": "Constituency & Ward Number", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Date", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Installed Pole Number", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "BESCOM Meter Sl.Number", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "BESCOM Meter (Working Status)", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Contractor Name", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Old Switch Point Number", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Is it CT meter ?", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Transformer Number", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Site Incharge", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "New-CCMS UID No", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Supply Input (OH/UG/ABC)", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "RR Number", "value": "...", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "SLC Earthing Completed? (Y/N)", "value": "...", "confidence": 0.95, "verification_status": "verified" }}
      ]
    }},
    {{
      "section": "Table: Pole and Lamp Details",
      "record_number": 1,
      "page_number": 1,
      "fields": [
        {{ "field_name": "Sl.No", "value": "1", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Pole No", "value": "185", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Arm Count", "value": "1", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Existing LED / New LED / SVL / Non LED", "value": "New", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Lamp Burning Status (Yes / No)", "value": "Y", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Connected Lamp Wattages", "value": "56", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Total Wattage", "value": "56", "confidence": 0.95, "verification_status": "verified" }}
      ]
    }},
    {{
      "section": "Electrical Meter Information",
      "record_number": 1,
      "page_number": 1,
      "fields": [
        {{ "field_name": "Voltage", "value": "239.71", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Current", "value": "3.21", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "PF", "value": "0.99", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Power(kW)", "value": "0.62", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Total Burning load in KW", "value": "0.62", "confidence": 0.95, "verification_status": "verified" }},
        {{ "field_name": "Total Load in KW", "value": "0.62", "confidence": 0.95, "verification_status": "verified" }}
      ]
    }}
  ]
}}

Source Filename: {filename}
Document ID: {document_id}
Embedded Text Detected (if any):
{embedded_text}

Extract EVERY populated table row. Preserve exact handwriting, spelling, and numbers. Do not guess. Output valid JSON only.
"""

