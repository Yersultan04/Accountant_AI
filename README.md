# Accountant AI

AI-powered accounting assistant that automates financial document processing — invoices, receipts, and transaction categorization via natural language.

## What it does

- **Invoice & receipt parsing** — extracts vendor, amount, date, and line items from PDFs and images (OCR + Claude API)
- **Transaction categorization** — automatically maps transactions to accounting categories
- **Natural language queries** — ask questions like *"What did we spend on SaaS last month?"*
- **Report generation** — produces structured financial summaries

## Architecture

```
Document Upload (PDF / Image)
         │
         ▼
    OCR Extraction
    (text from image)
         │
         ▼
   Claude API ──── Structured extraction
   (parse fields:    (vendor, amount,
    date, items)      category, tax)
         │
         ▼
    PostgreSQL
    (store transactions)
         │
         ▼
   FastAPI Endpoints
   (query, reports, export)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI |
| AI | Claude API (Anthropic) |
| OCR | PDF/image text extraction |
| Database | PostgreSQL |
| Output | JSON, CSV export |

## API Endpoints

```
POST /upload          — upload invoice/receipt
GET  /transactions    — list all parsed transactions
POST /query           — natural language financial query
GET  /report/monthly  — generate monthly summary
```

## Getting Started

```bash
git clone https://github.com/Yersultan04/Accountant_AI
cd Accountant_AI
pip install -r requirements.txt
cp .env.example .env  # add ANTHROPIC_API_KEY + DATABASE_URL
uvicorn main:app --reload
```

## Author

[Yersultan Akhmer](https://github.com/Yersultan04) — AI/LLM Engineer  
[LinkedIn](https://linkedin.com/in/yersultan-akhmer-20b766228)
