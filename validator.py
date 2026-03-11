from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

REQUIRED_OUTPUT_COLUMNS = [
    "invoice_id",
    "status",
    "risk_score",
    "issues",
    "issues_count",
    "recommended_action",
]

COLUMN_ALIASES = {
    "invoice_id": ["invoice_id", "invoice_number", "inv_id", "esf_number"],
    "invoice_date": ["invoice_date", "date", "invoice_dt", "esf_date"],
    "seller_bin": ["seller_bin", "vendor_bin", "supplier_bin"],
    "buyer_bin": ["buyer_bin", "customer_bin", "client_bin"],
    "amount_without_vat": ["amount_without_vat", "amount_wo_vat", "net_amount", "subtotal"],
    "vat_amount": ["vat_amount", "vat", "nds_amount"],
    "total_amount": ["total_amount", "amount_with_vat", "gross_amount", "total"],
    "currency": ["currency", "curr"],
    "contract_number": ["contract_number", "contract_no", "agreement_number"],
    "description": ["description", "purpose", "comment", "details"],
}


def _find_existing_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    for col in aliases:
        if col in df.columns:
            return col
    return None


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    rename_map: dict[str, str] = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        existing = _find_existing_column(normalized, aliases)
        if existing is not None and existing != canonical:
            rename_map[existing] = canonical

    normalized = normalized.rename(columns=rename_map)
    return normalized


def _ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    ensured = df.copy()
    base_required = [
        "invoice_id",
        "invoice_date",
        "seller_bin",
        "buyer_bin",
        "amount_without_vat",
        "vat_amount",
        "total_amount",
        "currency",
    ]

    for col in base_required:
        if col not in ensured.columns:
            ensured[col] = pd.NA

    if "description" not in ensured.columns and "contract_number" not in ensured.columns:
        ensured["description"] = pd.NA

    return ensured


def _is_empty(value: Any) -> bool:
    if value is None or pd.isna(value):
        return True
    return str(value).strip() == ""


def _validate_bin(value: Any) -> bool:
    if _is_empty(value):
        return False
    s = str(value).strip()
    return len(s) == 12 and s.isdigit()


def _to_number(value: Any) -> float | None:
    n = pd.to_numeric(value, errors="coerce")
    if pd.isna(n):
        return None
    return float(n)


def _classify_status(score: int, has_critical_issue: bool) -> str:
    if has_critical_issue or score >= 60:
        return "Critical"
    if score >= 20:
        return "Warning"
    return "OK"


def _recommended_action(issues: list[str], status: str) -> str:
    text = " | ".join(issues)

    if status == "OK":
        return "No action needed"

    if "Missing seller BIN" in text or "Missing buyer BIN" in text or "Invalid seller BIN format" in text or "Invalid buyer BIN format" in text:
        return "Fix seller/buyer BIN before submission"

    if "Amount + VAT does not match total" in text or "VAT is negative" in text or "Amount without VAT must be > 0" in text:
        return "Review VAT and total amount calculation"

    if "Duplicate invoice_id" in text:
        return "Check duplicate invoices and keep one valid record"

    if "Invoice date is in the future" in text or "Invoice date is too old" in text:
        return "Verify invoice date against accounting period"

    if "Missing description/contract_number" in text:
        return "Fill description or contract number"

    return "Review flagged fields before submission"


def validate_invoices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate invoice rows and return result DataFrame with required UI contract columns.

    Rules:
    1) Missing invoice_id
    2) Missing invoice_date
    3) Missing seller_bin / buyer_bin
    4) BIN invalid format
    5) amount_without_vat <= 0
    6) vat_amount < 0
    7) amount_without_vat + vat_amount != total_amount (tolerance 0.01)
    8) Duplicate invoice_id
    9) invoice_date future / too old (> 5 years)
    10) Missing description and contract_number
    """
    normalized = _ensure_required_columns(_normalize_columns(df))
    result = normalized.copy()

    invoice_ids = result["invoice_id"].astype(str).str.strip().fillna("")
    duplicate_mask = invoice_ids.ne("") & invoice_ids.duplicated(keep=False)

    now = datetime.utcnow().date()
    oldest_date = now - timedelta(days=365 * 5)

    issues_list: list[list[str]] = []
    score_list: list[int] = []
    status_list: list[str] = []
    action_list: list[str] = []

    for idx, row in result.iterrows():
        issues: list[str] = []
        score = 0
        has_critical_issue = False

        invoice_id = row.get("invoice_id")
        invoice_date_raw = row.get("invoice_date")
        seller_bin = row.get("seller_bin")
        buyer_bin = row.get("buyer_bin")
        amount = _to_number(row.get("amount_without_vat"))
        vat = _to_number(row.get("vat_amount"))
        total = _to_number(row.get("total_amount"))
        description = row.get("description") if "description" in result.columns else pd.NA
        contract_number = row.get("contract_number") if "contract_number" in result.columns else pd.NA

        # 1
        if _is_empty(invoice_id):
            issues.append("Missing invoice_id")
            score += 30
            has_critical_issue = True

        # 2
        if _is_empty(invoice_date_raw):
            issues.append("Missing invoice_date")
            score += 25
            has_critical_issue = True

        # 3 and 4
        if _is_empty(seller_bin):
            issues.append("Missing seller BIN")
            score += 30
            has_critical_issue = True
        elif not _validate_bin(seller_bin):
            issues.append("Invalid seller BIN format")
            score += 25
            has_critical_issue = True

        if _is_empty(buyer_bin):
            issues.append("Missing buyer BIN")
            score += 30
            has_critical_issue = True
        elif not _validate_bin(buyer_bin):
            issues.append("Invalid buyer BIN format")
            score += 25
            has_critical_issue = True

        # 5
        if amount is None or amount <= 0:
            issues.append("Amount without VAT must be > 0")
            score += 25
            has_critical_issue = True

        # 6
        if vat is None:
            issues.append("VAT amount is missing/invalid")
            score += 20
            has_critical_issue = True
        elif vat < 0:
            issues.append("VAT is negative")
            score += 20
            has_critical_issue = True

        # 7
        if amount is not None and vat is not None and total is not None:
            if abs((amount + vat) - total) > 0.01:
                issues.append("Amount + VAT does not match total")
                score += 30
                has_critical_issue = True
        else:
            issues.append("Total amount is missing/invalid")
            score += 15

        # 8
        if bool(duplicate_mask.loc[idx]):
            issues.append("Duplicate invoice_id")
            score += 25

        # 9
        parsed_date = pd.to_datetime(invoice_date_raw, errors="coerce")
        if pd.notna(parsed_date):
            d = parsed_date.date()
            if d > now:
                issues.append("Invoice date is in the future")
                score += 20
                has_critical_issue = True
            elif d < oldest_date:
                issues.append("Invoice date is too old")
                score += 10
        elif not _is_empty(invoice_date_raw):
            issues.append("Invoice date format is invalid")
            score += 15
            has_critical_issue = True

        # 10
        if _is_empty(description) and _is_empty(contract_number):
            issues.append("Missing description/contract_number")
            score += 10

        score = min(100, score)
        status = _classify_status(score, has_critical_issue)
        action = _recommended_action(issues, status)

        issues_list.append(issues)
        score_list.append(score)
        status_list.append(status)
        action_list.append(action)

    result["issues"] = ["; ".join(issues) for issues in issues_list]
    result["issues_count"] = [len(issues) for issues in issues_list]
    result["risk_score"] = score_list
    result["status"] = status_list
    result["recommended_action"] = action_list

    # Guarantee UI contract columns exist
    for col in REQUIRED_OUTPUT_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA

    return result
