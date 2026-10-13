# MedQuery

An agentic Text-to-SQL system that answers natural-language
questions over the MIMIC-IV clinical database.

## Key Features

- Async LangGraph agent for concurrent requests
- Guardrails: SQL allow-list (SELECT only), read-only DB connection
- Observability with LangSmith
- FastAPI service with health check
- Tests with pytest, CI with GitHub Actions

## Tech Stack

Python, LangGraph/LangChain, OpenAI, FastAPI, SQLite, Docker, pytest, GitHub Actions
