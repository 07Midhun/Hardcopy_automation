# AI Document Intelligence – Extraction & Validation Rules

## 1. Zero-Hallucination & Handwriting Preservation Rules

1. **Never Invent Information**:
   - If a field is blank on the physical document, the extracted value must be `null` or empty string `""` with `verification_status: "missing"`.
   - Never fabricate missing digits, phone numbers, or dates.
2. **Preserve Recognized Spelling**:
   - Autocorrect is disabled. Never autocorrect names of people, places, or technical codes.
   - Example: If handwritten "Sri Laxmi", do not correct to "Sri Lakshmi".
3. **Preserve Leading Zeros**:
   - Numbers such as `"042"` or `"00860"` must retain leading zeros and be formatted as text (`@`) in the consolidated Excel worksheet to prevent truncation.
4. **Distinguish Blank vs Unreadable**:
   - **Blank**: The field was left unfilled by the author -> status `missing`.
   - **Unreadable**: Ink strokes or smudges exist but cannot be recognized with confidence -> status `unreadable`.
5. **Confidence Scoring Thresholds**:
   - **High (>= 0.85)**: Clear printed text or crisp, legible handwriting -> `verified`.
   - **Medium (0.60 - 0.84)**: Cursive, stylized, or faint ink -> `review_required`.
   - **Low (< 0.60)**: Ambiguous, overlapping, or damaged text -> `review_required` or `unreadable`.

---

## 2. Dynamic Table Structure Rules

1. **Row Independence**:
   - Each row of an extracted table is a distinct record with its own `record_number`.
   - Never merge values from different rows.
2. **Column Association**:
   - Table columns are dynamically matched to their respective headers.
   - Empty cells within a row are preserved as empty strings rather than shifting subsequent columns left.
3. **Multi-Table Support**:
   - Multiple tables on the same page are preserved under distinct section titles (e.g. `Table 1: Lamp Details`, `Table 2: Earthing Resistance`).

