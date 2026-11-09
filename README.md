# FINTECT

### Secure, Governed & Transparent Agentic Banking Platform

FINTECT is an engineering project exploring how AI agents can interact with banking systems under deterministic runtime security, data governance, and human oversight.

## Overview

FINTECT combines an agentic banking assistant with **AEGIS**, an independent runtime security and governance layer.

The platform is designed to support:

- Natural-language banking interactions
- Account and transaction information retrieval
- Payment preparation and controlled execution
- Runtime authorization and policy enforcement
- Human-in-the-loop transaction approvals
- Security auditing and execution observability
- Automated security and functional evaluation

## Architecture

FINTECT is planned around the following components:

- **Banking Backend:** Simulated banking APIs and business logic.
- **Agent System:** LangGraph-based agent workflows and banking tools.
- **AEGIS:** Runtime authorization, security enforcement, and data governance.
- **Approval System:** Human approval for sensitive operations.
- **Observability:** Execution traces, policy decisions, and audit events.
- **Frontend:** Banking dashboard, agent interface, and approval workflows.

> This repository is under active development. Architecture and implementation details will evolve as modules are built and validated.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Agent Framework | LangGraph |
| LLM | Qwen via Ollama |
| Database | PostgreSQL |
| Frontend | React, TypeScript, Vite |
| Security | Custom Python policy engine |
| Testing | pytest |
| Containerization | Docker |
| CI/CD | GitHub Actions |

## Engineering Principles

- Modular architecture
- Separation of concerns
- Test-driven and test-oriented development
- Deterministic security enforcement
- Fail-closed authorization
- Reproducible evaluation
- Transparent execution
- Incremental development

## Project Status

**Status:** Foundation setup

Modules will be implemented incrementally, with tests, documentation, and version-controlled changes.

## Local Infrastructure

FINTECT uses Docker Compose to run PostgreSQL locally.

### Prerequisites
- Docker Desktop with WSL integration enabled
- Docker Compose

### Setup

1. Copy `.env.example` to `.env`.
2. Configure your local environment variables.
3. Start PostgreSQL:

   ```bash
   docker compose up -d postgres
   ```

4. Verify the database:

   ```bash
   docker compose ps
   docker compose exec postgres pg_isready -U fintect -d fintect
   ```

### Database Configuration

- Database: `fintect`
- User: `fintect`
- Port: `5432`
- PostgreSQL: `16`
- Persistent volume: `fintect_postgres_data`

### Stop PostgreSQL

```bash
docker compose down
```

To remove the database volume and all stored database data:

```bash
docker compose down -v
```

**Warning:** `docker compose down -v` permanently deletes the local PostgreSQL data volume.
