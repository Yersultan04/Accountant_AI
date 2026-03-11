# Accountant_AI — Full Architecture Audit Report

## Context

**Project:** AI ESF Pre-Check Copilot — a Streamlit-based invoice validation tool for Kazakhstan's ИС ЭСФ electronic invoicing system. Designed as a 6-hour MVP for 2 parallel developers (~570 lines of Python across 3 files).

**Core Idea:** Accept CSV/XLSX invoice batches → validate against 10 business rules → classify risk (OK / Warning / Critical) → generate summaries → export results.

**Files:** `app.py` (UI), `validator.py` (validation engine), `summarizer.py` (summary builder), plus sample data and README.

---

## 1. LOOPHOLES

### 1.1 CSV Injection Vulnerability (CRITICAL)
- **File:** `app.py:156-159` — `to_csv_bytes()` writes raw cell values to CSV
- If invoice data contains Excel formulas (e.g., `=CMD|'/c calc'!A0`), they pass through unsanitized
- When a user downloads and opens the CSV in Excel, malicious formulas can execute
- **Fix:** Prefix cells starting with `=`, `+`, `-`, `@` with a single quote or tab

### 1.2 No File Size / Row Count Limits
- **File:** `app.py:187` — file uploader has no `max_upload_size` constraint
- A user can upload a multi-GB CSV, causing memory exhaustion and app crash
- No row count guard — 1M+ rows will freeze the single-threaded Streamlit process

### 1.3 No Authentication or Authorization
- Zero auth mechanism — anyone with the URL can access the tool
- No session isolation — if deployed multi-user, data could leak between sessions
- No rate limiting — trivially DoS-able

### 1.4 "AI Summary" Is Not AI
- `summarizer.py` is purely template-based (string formatting with counts)
- README and UI label it as "AI summary" — this is misleading
- No LLM/API integration exists despite the project name containing "AI"

### 1.5 Silent Validator Failover Hides Bugs
- **File:** `app.py:102-115` — if `validate_invoices()` throws ANY exception, the app silently falls back to `_mock_validate()`
- User sees a small warning but has no idea their data was validated by a simplified mock
- Real validation bugs could go unnoticed for a long time

### 1.6 Status Column Mutation Corrupts Export Data
- **File:** `app.py:138` — status becomes `"🔴 Critical"` instead of `"Critical"` after display formatting
- If the user exports after viewing, the CSV contains emoji-polluted status values
- Downstream systems parsing "Critical" will break

### 1.7 Inconsistent Error Messages Between Validators
- `_mock_validate()` and `validate_invoices()` use different issue strings for the same problem:
  - Mock: `"Invalid seller BIN"` vs Real: `"Invalid seller BIN format"`
  - Mock: `"Total mismatch"` vs Real: `"Amount + VAT does not match total"`
- Users see different messages depending on which code path runs

---

## 2. BOTTLENECKS

### 2.1 O(n²) DataFrame Access in Mock Validator
- **File:** `app.py:45-60` — for each row, creates new `pd.Series` objects via `.get()` fallback
- This is catastrophically slow for large files (thousands of rows)
- Should use `result.at[idx, col]` or vectorized operations

### 2.2 Row-by-Row Validation Loop
- **File:** `validator.py:171-252` — iterates row-by-row with `for idx in df.index`
- Pandas is designed for vectorized ops; row iteration is 10-100x slower
- For 100k rows, this will take minutes instead of seconds

### 2.3 Single-Threaded Streamlit
- Streamlit runs single-threaded by default
- Multiple concurrent users = sequential processing, everyone waits
- No background job queue for large batch processing
- No caching (`@st.cache_data`) to avoid recomputation on reruns

### 2.4 Entire File Loaded Into Memory
- No chunked processing — entire CSV/XLSX loaded at once
- For a 500MB file, this means 500MB+ RAM usage (pandas overhead ~2-5x)

### 2.5 No Database / Persistence
- All results are ephemeral — lost on page refresh
- No audit trail of past validations
- Users must re-upload and re-validate every time

---

## 3. MISSING INFRASTRUCTURE

### 3.1 Zero Tests
- No test files exist (`test_*.py`, `tests/`, etc.)
- No pytest in requirements.txt
- No CI/CD pipeline (no GitHub Actions, no Dockerfile)

### 3.2 No Logging
- Zero use of Python's `logging` module
- No structured logs, no error tracking
- When things fail silently (see 1.5), there's no way to diagnose

### 3.3 No Configuration Management
- All thresholds hardcoded: risk score cutoffs (60/20), date range (5 years), tolerance (0.01)
- No `.env` file, no `config.py`, no `os.environ` usage

### 3.4 No Deployment Artifacts
- No Dockerfile, docker-compose.yml, `.gitignore`, `pyproject.toml`, or lock files

---

## 4. BUSINESS LOGIC GAPS

### 4.1 BIN Validation Is Format-Only
- Checks: exactly 12 digits — no checksum verification (Kazakhstan BINs have a check digit algorithm)
- Accepts fake BINs like `000000000000`

### 4.2 No VAT Rate Validation
- Kazakhstan uses specific VAT rates (12%, 0% for exempt goods)
- Current code only checks `vat >= 0` — a 50% VAT would pass

### 4.3 No Currency Validation
- Accepts any string as currency (`"BANANA"` would pass)

### 4.4 No Transaction Amount Bounds
- Accepts `amount = 0.01` and `amount = 999,999,999,999` — no sanity checks

### 4.5 Duplicate Detection Marks ALL Copies
- `duplicated(keep=False)` flags every occurrence — user doesn't know which is the "original"

### 4.6 Date Parsing Ambiguity
- `pd.to_datetime(value, errors="coerce")` guesses format — `01/02/2026` could be Jan 2 or Feb 1

### 4.7 No Cross-Invoice Validation
- No checks for: same buyer+seller+amount+date, sequential numbering gaps, batch amount reasonableness

---

## 5. CODE QUALITY ISSUES

### 5.1 Duplicated Validation Logic
- `app.py` mock reimplements ~70% of `validator.py` — different messages, different edge cases, two places to update

### 5.2 Mixed Null Handling Patterns
- `validator.py` uses `_is_empty()` helper; `app.py` uses `pd.isna()` + truthiness inconsistently

### 5.3 Hardcoded Recommended Actions
- Action text matched by exact issue substrings — if message strings change, mappings silently break

### 5.4 Minimal Docstrings
- Only `validate_invoices()` has a proper docstring — all other functions undocumented

### 5.5 No Type Checking Setup
- Type hints exist but no `mypy`/`pyright` configured — hints are decorative only

---

## 6. SCALABILITY CONCERNS

| Dimension | Current State | Practical Limit |
|-----------|--------------|-----------------|
| File size | No limit | RAM-bound (~1GB max) |
| Row count | No limit | ~50k rows before UI freezes |
| Concurrent users | 1 (Streamlit default) | Blocks on heavy files |
| Validation speed | Row-by-row loop | ~1000 rows/sec |
| Data retention | None (ephemeral) | Lost on refresh |
| Deployment | Local dev server | No production config |

---

## 7. WHAT'S DONE WELL

- **Clean separation of concerns** — validator, UI, and summarizer are independent modules
- **Column alias system** — handles multiple CSV column naming conventions gracefully
- **Risk scoring model** — composite score (0-100) with critical flag override is solid
- **Graceful degradation design** — the fallback concept is good (execution needs work)
- **README quality** — exceptionally detailed for an MVP
- **Type hints throughout** — good practice even if not enforced
- **Safe numeric coercion** — `pd.to_numeric(errors='coerce')` prevents crashes on bad data

---

## 8. RECOMMENDED FIX PRIORITIES

### Tier 1 — Security & Correctness (Must Fix)
1. Add CSV injection sanitization to export
2. Add file size limit (e.g., 50MB max)
3. Fix status column mutation (use display-only column)
4. Unify or remove mock validator
5. Add error boundaries around summary rendering

### Tier 2 — Reliability & Maintainability
6. Add pytest test suite (all 10 validation rules + edge cases)
7. Add logging framework
8. Extract hardcoded thresholds to config
9. Vectorize validation logic for performance
10. Add `.gitignore`, `Dockerfile`, basic CI

### Tier 3 — Business Logic Enhancement
11. Add VAT rate validation (12% for KZ)
12. Add currency whitelist validation
13. Improve BIN validation (checksum)
14. Add transaction amount bounds
15. Improve duplicate detection (keep=first)

### Tier 4 — Production Readiness
16. Add authentication
17. Add database for result persistence
18. Add session state caching
19. Implement chunked processing for large files
20. Add monitoring and alerting
