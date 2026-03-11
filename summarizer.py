import json
import os
from typing import Any

import pandas as pd
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _rule_based_summary(result_df: pd.DataFrame) -> str:
    total = len(result_df)
    critical = int((result_df["status"] == "Critical").sum())
    warning = int((result_df["status"] == "Warning").sum())
    ok = int((result_df["status"] == "OK").sum())

    issues = (
        result_df.get("issues", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )
    issues = issues[issues != ""]

    if len(issues) > 0:
        top = issues.value_counts().head(3)
        top_lines = "\n".join([f"- {issue}: {count}" for issue, count in top.items()])
    else:
        top_lines = "- No recurring issues detected"

    priority_df = result_df[result_df["status"].isin(["Critical", "Warning"])]
    priority_df = priority_df.sort_values(by=["risk_score"], ascending=False).head(5)

    if len(priority_df) > 0:
        priority_lines = "\n".join(
            [
                f"- `{row.invoice_id}` ({row.status}, score {int(row.risk_score)}): {row.recommended_action}"
                for row in priority_df.itertuples()
            ]
        )
    else:
        priority_lines = "- No priority documents"

    return f"""
**Batch summary**
- Invoices checked: **{total}**
- Critical: **{critical}**
- Warning: **{warning}**
- OK: **{ok}**

**Top issues**
{top_lines}

**Priority actions**
{priority_lines}
""".strip()


def _payload_from_df(result_df: pd.DataFrame) -> dict[str, Any]:
    issues = (
        result_df.get("issues", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )
    issues = issues[issues != ""]

    top_issues = issues.value_counts().head(5).to_dict() if len(issues) > 0 else {}

    priority_df = result_df[result_df["status"].isin(["Critical", "Warning"])]
    priority_df = priority_df.sort_values(by=["risk_score"], ascending=False).head(10)

    priority_docs = []
    for row in priority_df.itertuples():
        priority_docs.append(
            {
                "invoice_id": str(row.invoice_id),
                "status": str(row.status),
                "risk_score": int(row.risk_score),
                "issues": str(row.issues),
                "recommended_action": str(row.recommended_action),
            }
        )

    return {
        "totals": {
            "total": int(len(result_df)),
            "critical": int((result_df["status"] == "Critical").sum()),
            "warning": int((result_df["status"] == "Warning").sum()),
            "ok": int((result_df["status"] == "OK").sum()),
        },
        "top_issues": top_issues,
        "priority_documents": priority_docs,
    }


def _build_summary_with_groq(result_df: pd.DataFrame, api_key: str) -> str:
    payload = _payload_from_df(result_df)
    prompt = (
        "You are an accounting copilot for Kazakhstan ESF pre-check. "
        "Write a concise markdown summary in English with sections: Batch summary, Top issues, Priority actions. "
        "Use practical language for accountants and CFOs. Keep it under 180 words."
    )

    body = {
        "model": DEFAULT_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def build_summary(result_df: pd.DataFrame) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return _rule_based_summary(result_df)

    try:
        return _build_summary_with_groq(result_df, api_key)
    except Exception:
        return _rule_based_summary(result_df)
