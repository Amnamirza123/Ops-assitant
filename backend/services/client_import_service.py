# services/client_import_service.py

import csv
import io
from fastapi import UploadFile, HTTPException
import openpyxl


async def parse_client_file(file: UploadFile) -> list[dict]:
    filename = file.filename.lower()
    content = await file.read()

    if filename.endswith(".csv"):
        return _parse_csv(content)
    elif filename.endswith(".xlsx"):
        return _parse_xlsx(content)
    else:
        raise HTTPException(status_code=400, detail="File must be .csv or .xlsx")


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return _normalize_rows(reader)


def _parse_xlsx(content: bytes) -> list[dict]:
    workbook = openpyxl.load_workbook(io.BytesIO(content))
    sheet = workbook.active

    rows_iter = sheet.iter_rows(values_only=True)
    headers = [str(h).strip().lower() for h in next(rows_iter)]

    rows = []
    for row in rows_iter:
        rows.append(dict(zip(headers, row)))

    return _normalize_rows(rows)


def _normalize_rows(rows) -> list[dict]:
    # Accepts flexible column naming (Name/name, Email/email, etc.) and
    # only keeps the fields our clients table actually has. Rows missing
    # a name are skipped — name is the only required field.
    normalized = []
    for row in rows:
        row = {str(k).strip().lower(): v for k, v in row.items() if k}
        name = row.get("name")
        if not name:
            continue

        normalized.append({
            "name": str(name).strip(),
            "email": str(row["email"]).strip() if row.get("email") else None,
            "status": str(row.get("status", "active")).strip().lower() or "active",
            "notes": str(row["notes"]).strip() if row.get("notes") else None,
        })

    return normalized