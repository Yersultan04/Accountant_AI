import io

import pandas as pd
import streamlit as st

from summarizer import build_summary

STATUS_ORDER = {"Critical": 0, "Warning": 1, "OK": 2}
STATUS_EMOJI = {"Critical": "🔴", "Warning": "🟠", "OK": "🟢"}


def _read_input_file(uploaded_file) -> pd.DataFrame:
    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported file type. Please upload CSV or XLSX.")


def run_validation(df: pd.DataFrame) -> pd.DataFrame:
    from validator import validate_invoices

    return validate_invoices(df)


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
    filtered["_display_status"] = filtered["status"].map(lambda s: f"{STATUS_EMOJI.get(s, '⚪')} {s}")
    return filtered.drop(columns=["_status_order"])


def style_rows_by_status(df: pd.DataFrame):
    def _row_style(row: pd.Series):
        value = str(row.get("status", ""))
        if "Critical" in value:
            return ["background-color: #ffe6e6"] * len(row)
        if "Warning" in value:
            return ["background-color: #fff4e6"] * len(row)
        if "OK" in value:
            return ["background-color: #e9f9ef"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    with io.StringIO() as buffer:
        df.to_csv(buffer, index=False)
        return buffer.getvalue().encode("utf-8")


def render_capabilities() -> None:
    st.markdown(
        """
### Что MVP уже делает сейчас
- Проверяет инвойсы до отправки (CSV/XLSX).
- Возвращает статусы **OK / Warning / Critical** и риск-скоринг.
- Показывает список проблем по каждому документу и рекомендацию к действию.
- Строит сводку по батчу (Top issues + priority actions).
- Экспортирует итоговый файл в CSV для передачи бухгалтеру.

### KZ 2026 (НК РК)
- Проверяет ставку НДС (16% базовая, 10%, 5%, 0%).
- Валидирует валюту (KZT, USD, EUR, RUB, GBP, CNY).
- Проверяет наличие кода НТИН/ХТИН (обязательно с 2026).
- Флагирует суммы выше порога НДС-регистрации (43.25M KZT).
"""
    )


def main() -> None:
    st.set_page_config(page_title="AI ESF Pre-Check Copilot", layout="wide")
    st.title("AI ESF Pre-Check Copilot (Kazakhstan MVP)")
    st.caption("Pre-check на основе НК РК 2026 (НДС 16%). Финальная проверка — в ИС ЭСФ.")

    with st.sidebar:
        st.header("Demo mode")
        st.markdown("- 🔴 Critical: likely rejection risk\n- 🟠 Warning: needs manual review\n- 🟢 OK: baseline checks passed")
        render_capabilities()

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

        st.dataframe(style_rows_by_status(display_df), use_container_width=True)

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
