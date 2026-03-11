import pandas as pd


def build_summary(result_df: pd.DataFrame) -> str:
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
