# Acme Corp — Automated Invoice Processing System

> A production-grade multi-agent AI pipeline that ingests invoices from any format, validates against inventory, detects fraud, and processes payments automatically.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-green)
![Claude](https://img.shields.io/badge/Claude-Haiku%20%2B%20Sonnet-orange)
![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red)

---

## The Problem

Acme Corp loses **$2,000,000/year** from manual invoice processing:

| Pain Point | Impact |
|---|---|
| 30% error rate | Re-keying, disputes, wrong payments |
| 5-day processing time | Late penalties, strained vendors |
| No fraud detection | Fraudulent invoices approved |
| No audit trail | Compliance failures |

---

## The Solution

A **4-agent AI pipeline** that processes invoices from ingestion to payment in under 30 seconds:
Invoice File (PDF/TXT/JSON/CSV/XML)
↓
[Ingestion Agent]    → Extract structured data (Claude Haiku)
↓
[Validation Agent]   → Stock check + math verify (Pure Python, $0 LLM cost)
↓
[Approval Agent]     → Business rules + LLM reasoning + critique loop (Claude Sonnet)
↓
[Payment Agent]      → Execute payment or log rejection (Deterministic, $0 LLM cost)
↓
JSON Audit Log + Streamlit Dashboard

**Cost: ~$0.01 per invoice. ROI: 10,000x vs manual processing.**

---

## Architecture

### Why LangGraph?
LangGraph provides a stateful graph with conditional routing — invoices with fraud signals
skip to rejection without running unnecessary LLM calls. Each node is independently testable.
Used in production at Uber, JP Morgan, Klarna.

### Why Two Different Models?
| Agent | Model | Reason |
|---|---|---|
| Ingestion | Claude Haiku | Fast, cheap, accurate for extraction |
| Validation | None (Python) | Deterministic SQL + math — no LLM needed |
| Approval | Claude Sonnet | Multi-factor judgment, critique loop |
| Payment | None (Python) | Function call — no LLM needed |

**Right-sizing intelligence to the task** keeps costs under $0.01/invoice.

### LLM Factory Pattern
Switch LLM provider without changing code:
```bash
# .env
LLM_PROVIDER=anthropic   # Claude (default)
LLM_PROVIDER=openai      # GPT-4o
LLM_PROVIDER=grok        # xAI Grok
```

---

## Key Features

### Intelligent Ingestion
- Handles **PDF, TXT, JSON, CSV/TSV, XML** formats
- OCR artifact correction (`$3,500.O0` → `$3,500.00`)
- Item name normalization (`Widget A` → `WidgetA`)
- Revision detection (uses latest version of duplicate invoices)
- Email-embedded invoice extraction
- Confidence scoring with fallback flagging

### Multi-Layer Validation (Zero LLM Cost)
- Real-time stock availability check
- Independent math recomputation from line items
- Phantom charge detection (stated total vs computed)
- 7-signal fraud scoring (urgency language, wire transfer, suspicious vendors)
- Currency mismatch detection
- Duplicate invoice detection
- Negative quantity/amount detection

### Tiered Approval Logic
- **Auto-reject** (no LLM): fraud score ≥ 0.75, negative totals, missing vendors
- **Auto-flag** (no LLM): non-USD currency, low confidence
- **LLM decision**: Claude Sonnet with full context
- **Critique loop**: Second LLM call reviews reasoning (max 2 rounds)
- **Safety validator**: Reasoning text cross-checks JSON decision field

### Complete Audit Trail
Every invoice generates a JSON audit log:
```json
{
  "invoice_number": "INV-1003",
  "timestamp": "2026-05-31T...",
  "llm_cost_usd": 0.0013,
  "pipeline": {
    "extraction": { "vendor": "Fraudster LLC", "confidence": 0.6 },
    "validation": { "fraud_score": 0.80, "flags": ["urgency", "wire transfer"] },
    "approval":   { "decision": "reject", "reasoning": "..." },
    "payment":    { "status": "rejected" }
  }
}
```

---

## Test Results

16 invoices processed across 5 formats. **16/16 correct decisions.**

| Invoice | Format | Scenario | Decision | Correct |
|---|---|---|---|---|
| INV-1001 | TXT | Clean standard | APPROVE | ✅ |
| INV-1002 | TXT | Stock shortfall | REJECT | ✅ |
| INV-1003 | TXT | Fraud (urgency + wire) | REJECT | ✅ |
| INV-1004 R1 | JSON | Revised invoice | APPROVE | ✅ |
| INV-1005 | JSON | GadgetX shortfall | REJECT | ✅ |
| INV-1006 | CSV | Flat TSV format | APPROVE | ✅ |
| INV-1007 | CSV | Multiple shortfalls | REJECT | ✅ |
| INV-1008 | TXT | Unknown items | REJECT | ✅ |
| INV-1009 | JSON | Negative quantity | REJECT | ✅ |
| INV-1010 | TXT | Rush order annotation | APPROVE | ✅ |
| INV-1011 | PDF | Clean PDF | APPROVE | ✅ |
| INV-1012 | PDF | OCR corrupted | FLAG | ✅ |
| INV-1013 | PDF | All stock exceeded + phantom $50 | REJECT | ✅ |
| INV-1014 | XML | EUR currency | FLAG | ✅ |
| INV-1015 | CSV | Clean multi-row | APPROVE | ✅ |
| INV-1016 | JSON | Unknown item WidgetC | REJECT | ✅ |

**Batch stats:** $30,375 approved · $181,195 blocked · $0.1480 total LLM cost · $0.0093/invoice

---

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/acme-invoice-processor
cd acme-invoice-processor

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API key

# Setup database
python database/setup.py
```

---

## Usage

### CLI — Single Invoice
```bash
python main.py --invoice data/invoices/invoice_1001.txt
```

### CLI — Batch (all invoices)
```bash
python main.py --batch
```

### Streamlit Dashboard
```bash
streamlit run app.py
```
Open `http://localhost:8501`

---

## Project Structure
acme-invoice-processor/
├── agents/
│   ├── ingestion_agent.py   # Format detection + LLM extraction
│   ├── validation_agent.py  # Stock + math + fraud (no LLM)
│   ├── approval_agent.py    # Rules + LLM + critique loop
│   └── payment_agent.py     # Mock payment execution
├── graph/
│   └── pipeline.py          # LangGraph StateGraph
├── models/
│   └── schemas.py           # All Pydantic schemas
├── tools/
│   ├── normalizer.py        # OCR cleanup, item normalization
│   ├── format_router.py     # File type detection + reading
│   └── pdf_parser.py        # pdfplumber extraction
├── database/
│   ├── setup.py             # DB creation + seeding
│   └── queries.py           # All SQL operations
├── utils/
│   ├── logger.py            # JSON audit logging
│   └── cost_tracker.py      # Token cost calculation
├── data/invoices/           # 20 test invoice files
├── logs/                    # Audit trail JSON files
├── app.py                   # Streamlit dashboard
├── main.py                  # CLI entry point
└── requirements.txt

---

## Cost Analysis

| Component | Cost | Notes |
|---|---|---|
| Ingestion (Haiku) | ~$0.001/invoice | ~500 input + 200 output tokens |
| Approval (Sonnet) | ~$0.009/invoice | ~800 input + 300 output tokens |
| Critique round | ~$0.004/invoice | Only when needed |
| **Total** | **~$0.01/invoice** | Maximum per invoice |

**At 1,000 invoices/month:**
- AI cost: ~$10/month
- Manual cost: ~$100,000/month (1,000 × 4h × $25/hr)
- **ROI: 10,000x**

---

## Bugs Encountered & Fixed

Real engineering means debugging. Here's what we hit and how we fixed it:

| Bug | Root Cause | Fix |
|---|---|---|
| State not passing between nodes | LangGraph dict state doesn't auto-merge | Wrapped nodes with `{**state, **result}` |
| Math failing on taxed invoices | Comparing subtotal to total | Allow 0-15% implied tax rate |
| LLM decision contradicted reasoning | Reasoning-output mismatch | Post-decision validator cross-checks text |
| INV-1010 rush order rejected | Parenthetical notes not stripped | Strip `(rush order)` before normalization |
| PowerShell emoji truncation | CP1252 can't render Unicode | Replaced emoji with ASCII text |
| `__init__.py` BOM corruption | PowerShell writes UTF-16 | Use `python -c "open().close()"` |

---

## Production Roadmap

This prototype demonstrates the full architecture. For production deployment:

- **Database**: PostgreSQL + SQLAlchemy + Alembic migrations
- **Async processing**: Celery + Redis for parallel invoice processing
- **Containerization**: Docker + docker-compose for consistent deployment
- **CI/CD**: GitHub Actions running tests on every push
- **Observability**: LangSmith for LLM call tracing, Datadog for system metrics
- **Human review queue**: UI for flagged invoices requiring human decision
- **Secrets management**: AWS Secrets Manager or HashiCorp Vault
- **Stock updates**: Real-time inventory deduction after approval
- **Vendor management**: Vendor registry with payment history and trust scores

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph 1.2 |
| LLM Extraction | Claude Haiku 4.5 |
| LLM Reasoning | Claude Sonnet 4.5 |
| Schema Validation | Pydantic 2.x |
| PDF Parsing | pdfplumber 0.11 |
| Database | SQLite 3 |
| Dashboard | Streamlit 1.58 |
| Multi-LLM | Factory pattern (Anthropic/OpenAI/Grok) |