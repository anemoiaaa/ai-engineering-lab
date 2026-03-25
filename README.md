# Northstar Foods Internal Policy & Onboarding Copilot

An AI-powered internal assistant that helps employees find accurate information about company policies, generate onboarding checklists, get policy summaries, and analyze uploaded data files — all grounded in official company documents.

## The Problem

- Onboarding is fragmented across multiple documents and tools
- Employees waste time searching for policy information manually
- HR teams answer the same questions repeatedly
- Responses are inconsistent because policies are scattered across documents

## The Solution

A Policy Copilot that provides:

- **Policy Q&A** — Ask questions in natural language; get answers grounded in official policy documents with source citations
- **Policy Summarizer** — Get concise summaries of any company policy
- **Onboarding Checklist Generator** — Generate personalized onboarding checklists for new employees
- **Data Analysis** — Upload files (CSV, JSON, Excel, Word) and get AI-powered analysis and insights

All features include guardrails: a retrieval score threshold rejects off-topic queries before the LLM is called, and system prompts enforce topic boundaries to keep responses scoped to Northstar Foods business context.

## Architecture

```
Streamlit UI  →  FastAPI Backend  →  Policy Retrieval (TF-IDF)  →  LLM (multi-provider)
                                  →  File Parser (upload analysis)
                                  →  System Prompts (context engineering + guardrails)
                                  →  Policy Documents (markdown)
```

- **Frontend:** Streamlit with mode selector (Q&A / Summarize / Checklist / Data Analysis) and file upload
- **Backend:** FastAPI with retrieval-augmented generation pipeline (`/chat`, `/upload`, `/health`)
- **Retrieval:** TF-IDF based document search over markdown policy files with score thresholds
- **File Parsing:** Support for CSV, JSON, Excel (.xlsx), and Word (.docx) uploads
- **LLM Providers:** OpenAI, Groq, Google GenAI (switchable at runtime)
- **Guardrails:** Retrieval score filtering + prompt-level off-topic rejection across all modes
- **Data:** 10 realistic company policy documents in markdown format

## Quick Start

```bash
# Ensure Docker is running, then:
docker compose up --build

# Access the UI at http://localhost:8501
# API docs at http://localhost:8000/docs
```

## Project Structure

```
├── apps/
│   ├── api/                    # FastAPI backend
│   │   └── src/api/
│   │       ├── app.py          # Main API with /chat, /upload, /health endpoints
│   │       ├── core/config.py  # Configuration (env vars)
│   │       ├── prompts/        # System prompts with guardrails for each mode
│   │       └── retrieval/      # TF-IDF policy search + file parser (CSV, JSON, Excel, Word)
│   └── chatbot_ui/             # Streamlit frontend
│       └── src/chatbot_ui/
│           ├── app.py          # UI with modes, file upload, sources display
│           └── core/config.py  # UI configuration
├── data/
│   └── policies/               # Company policy documents (markdown)
├── notebooks/                  # Exploration notebooks
├── docker-compose.yml          # Service orchestration
└── pyproject.toml              # uv workspace configuration
```

## Environment Variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your-key
GOOGLE_API_KEY=your-key
GROQ_API_KEY=your-key
```

## Tech Stack

- Python 3.12, uv (package manager)
- FastAPI + Uvicorn
- Streamlit
- scikit-learn (TF-IDF retrieval)
- openpyxl, python-docx (file parsing for Excel and Word uploads)
- Docker + Docker Compose
- OpenAI / Groq / Google GenAI APIs
