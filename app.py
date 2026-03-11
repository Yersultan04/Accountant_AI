import io
from typing import Optional

import pandas as pd
import streamlit as st

from summarizer import build_summary


STATUS_ORDER = {"Critical": 0, "Warning": 1, "OK": 2}
REQUIRED_OUTPUT_COLUMNS = [
    "invoice_id",
    "status",
    "risk_score",
    "issues",
    "issues_count",
    "recommended_action",
]


def _read_input_file(uploaded_file) -> pd.DataFrame:
    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported file type. Please upload CSV or XLSX.")


def _mock_validate(df: pd.DataFrame) -> pd.DataFrame:
    """Temporary fallback validator so UI works before backend integration."""
    result = df.copy()
    if "invoice_id" not in result.columns:
        result["invoice_id"] = [f"ROW-{idx+1}" for idx in range(len(result))]

    # Light UI-safe fallback: if required contract is missing, generate demo outputs.
    result["issues"] = ""
    result["issues_count"] = 0
    result["risk_score"] = 0
    result["status"] = "OK"
    result["recommended_action"] = "No action needed"

    for idx in result.index:
        issues = []
        score = 0

        seller = str(result.get("seller_bin", pd.Series(index=result.index, dtype=str)).get(idx, "") or "").strip()
        buyer = str(result.get("buyer_bin", pd.Series(index=result.index, dtype=str)).get(idx, "") or "").strip()
        description = str(result.get("description", pd.Series(index=result.index, dtype=str)).get(idx, "") or "").strip()

        amount = pd.to_numeric(result.get("amount_without_vat", pd.Series(index=result.index, dtype=float)).get(idx, 0), errors="coerce")
        vat = pd.to_numeric(result.get("vat_amount", pd.Series(index=result.index, dtype=float)).get(idx, 0), errors="coerce")
        total = pd.to_numeric(result.get("total_amount", pd.Series(index=result.index, dtype=float)).get(idx, 0), errors="coerce")

        if len(seller) != 12 or not seller.isdigit():
            issues.append("Invalid seller BIN")
            score += 35
        if len(buyer) != 12 or not buyer.isdigit():
            issues.append("Invalid buyer BIN")
            score += 35
        if pd.isna(amount) or amount <= 0:
            issues.append("amount_without_vat must be > 0")
            score += 25
        if pd.isna(vat) or vat < 0:
            issues.append("vat_amount must be >= 0")
            score += 20
        if not pd.isna(amount) and not pd.isna(vat) and not pd.isna(total):
            if abs((amount + vat) - total) > 0.01:
                issues.append("Total mismatch")
                score += 30
        if not description:
            issues.append("Missing description")
            score += 10

        score = min(100, score)
        if score >= 60:
            status = "Critical"
            action = "Fix mandatory identifiers and amounts before submission"
        elif score >= 20:
            status = "Warning"
            action = "Review and correct suspicious fields"
        else:
            status = "OK"
            action = "No action needed"

        result.at[idx, "issues"] = "; ".join(issues)
        result.at[idx, "issues_count"] = len(issues)
        result.at[idx, "risk_score"] = int(score)
        result.at[idx, "status"] = status
        result.at[idx, "recommended_action"] = action

    return result


def run_validation(df: pd.DataFrame) -> pd.DataFrame:
    try:
        from validator import validate_invoices  # type: ignore

        validated = validate_invoices(df)
        missing = [col for col in REQUIRED_OUTPUT_COLUMNS if col not in validated.columns]
        if missing:
            st.warning(
                "Validator returned missing contract columns: " + ", ".join(missing) + ". Using UI fallback."
            )
            return _mock_validate(df)
        return validated
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Using fallback validator. Backend validator is not available yet ({exc}).")
        return _mock_validate(df)


def render_kpis(result_df: pd.DataFrame) -> None:
    total = len(result_df)
    critical = int((result_df["status"] == "Critical").sum())
    warning = int((result_df["status"] == "Warning").sum())
    ok = int((result_df["status"] == "OK").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total documents", total)
    c2.metric("Critical", critical)
    c3.metric("Warning", warning)
    c4.metric("OK", ok)


def apply_filters(result_df: pd.DataFrame, only_problematic: bool) -> pd.DataFrame:
    filtered = result_df.copy()
    if only_problematic:
        filtered = filtered[filtered["status"].isin(["Critical", "Warning"])]

    filtered["_status_order"] = filtered["status"].map(STATUS_ORDER).fillna(99)
    filtered = filtered.sort_values(by=["_status_order", "risk_score"], ascending=[True, False])
    return filtered.drop(columns=["_status_order"])


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    with io.StringIO() as buffer:
        df.to_csv(buffer, index=False)
        return buffer.getvalue().encode("utf-8")


def main() -> None:
    st.set_page_config(page_title="AI ESF Pre-Check Copilot", layout="wide")
    st.title("AI ESF Pre-Check Copilot (Kazakhstan MVP)")
    st.caption("Pre-check tool. Final validation happens in official systems.")

    uploaded = st.file_uploader("Upload invoices (CSV/XLSX)", type=["csv", "xlsx", "xls"])
    if uploaded is None:
        st.info("Upload a file to start validation.")
        return

    try:
        input_df = _read_input_file(uploaded)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to read file: {exc}")
        return

    st.subheader("Preview")
    st.dataframe(input_df.head(20), use_container_width=True)

    if st.button("Check invoices", type="primary"):
        result_df = run_validation(input_df)

        st.subheader("Results")
        render_kpis(result_df)

        only_problematic = st.checkbox("Show only problematic", value=False)
        display_df = apply_filters(result_df, only_problematic)

        st.dataframe(display_df, use_container_width=True)

        st.subheader("Top 3 issues")
        issues = (
            result_df["issues"]
            .fillna("")
            .astype(str)
            .str.split(";")
            .explode()
            .str.strip()
        )
        issues = issues[issues != ""]
        if len(issues):
            top_issues = issues.value_counts().head(3)
            st.table(top_issues.rename_axis("Issue").reset_index(name="Count"))
        else:
            st.write("No issues found.")

        st.subheader("AI Summary")
        st.markdown(build_summary(result_df))

        st.download_button(
            label="Download checked CSV",
            data=to_csv_bytes(result_df),
            file_name="checked_results.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
