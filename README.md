# Autonomous Incident Triage Agent

A production-ready, autonomous incident triage backend built with **FastAPI**, **LangGraph**, **PostgreSQL with pgvector**, and **Google Gemini**.

The system investigates incidents, collects telemetry evidence, queries internal runbooks via RAG, diagnoses root causes using LLM structured reasoning, enforces safety policies, pauses for human approval before executing sensitive operations, and verifies post-remediation service health.

---

## 1. System Architecture

```text
                           [ External Alert / On-Call Engineer ]
                                             │
                                     POST /incidents
                                             ▼
                             ┌───────────────────────────────┐
                             │       FastAPI REST API        │
                             │  (/incidents, /events,        │
                             │   /approve, /reject, /health) │
                             └───────────────┬───────────────┘
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │   LangGraph State Machine     │
                             │ (PostgreSQL Checkpointer)     │
                             └───────────────┬───────────────┘
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      │                                      │                                      │
      ▼                                      ▼                                      ▼
┌──────────────┐                       ┌──────────────┐                       ┌──────────────┐
│  Health &    │                       │  RAG Engine  │                       │ Gemini LLM   │
│  Log Tools   │                       │ (pgvector)   │                       │ (Structured  │
│ (Simulated)  │                       │  Runbooks    │                       │  Reasoning)  │
└──────────────┘                       └──────────────┘                       └──────────────┘
      │                                      │                                      │
      └──────────────────────────────────────┼──────────────────────────────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │      Safety & Risk Gate       │
                             └───────────────┬───────────────┘
                                             │
                        ┌────────────────────┴────────────────────┐
                        │ LOW RISK                                │ HIGH / CRITICAL RISK
                        ▼                                         ▼
              ┌──────────────────┐                      ┌──────────────────┐
              │   Auto-Execute   │                      │  HITL Interrupt  │
              │     Action       │                      │(AWAITING_APPROVAL│
              └─────────┬────────┘                      └─────────┬────────┘
                        │                                         │ Approve / Reject
                        │                                         ▼
                        │                               ┌──────────────────┐
                        │                               │  Execute Action  │
                        │                               │   (if approved)  │
                        │                               └─────────┬────────┘
                        └───────────────────┬─────────────────────┘
                                            ▼
                                ┌────────────────────────┐
                                │ Verify Health Check   │
                                └───────────┬────────────┘
                                            │
                               ┌────────────┴────────────┐
                               │ Healthy                 │ Unhealthy
                               ▼                         ▼
                         [ RESOLVED ]              [ ESCALATED ]
```

---

## 2. Core Features

- **Autonomous Investigation Workflow**: Multi-stage LangGraph state machine coordinating telemetry collection, logs, RAG retrieval, and verification.
- **RAG Knowledge Base**: Semantic vector search with pgvector over markdown runbooks (`auth`, `database`, `payments`).
- **Structured LLM Reasoning**: Leverages Google Gemini Flash (`GEMINI_MODEL`) with Pydantic structured output models for deterministic, verifiable diagnosis.
- **Strict Safety Registry**: LLM cannot execute shell commands or invent actions. Pre-approved registry categorizes actions by risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Human-in-the-Loop (HITL)**: High-risk and critical actions trigger an explicit LangGraph `interrupt()`, persisting state to PostgreSQL until an operator approves or rejects via the REST API.
- **Audit Logging**: Every state transition and investigation step is recorded in `incident_events` for full operational transparency.
- **Post-Remediation Verification**: Re-checks service telemetry after executing an action to ensure stability before marking `RESOLVED`.
- **Database Compatibility**: Supports standard PostgreSQL + pgvector as well as Supabase PostgreSQL via connection string.
- **Production Deployment**: Containerized with Docker and ready for 1-click deployment on Render Web Services.

---

## 3. Action Registry & Safety Policy

| Action Name | Risk Level | Requires Approval | Description |
| :--- | :--- | :--- | :--- |
| `read_health` | LOW | No | Inspect health telemetry metrics |
| `search_runbook` | LOW | No | Semantic vector search across internal runbooks |
| `clear_cache` | LOW | No | Purge expired cache keys from Redis |
| `create_escalation_ticket` | MEDIUM | No | Open escalation ticket to on-call engineers |
| `restart_service` | HIGH | **Yes** | Rolling restart of degraded service replicas |
| `terminate_idle_transaction`| HIGH | **Yes** | Terminate blocking idle database connections |
| `failover_database` | CRITICAL | **Yes** | Promote read replica to primary database |
| `switch_payment_provider` | CRITICAL | **Yes** | Shift live financial traffic to backup provider |

---

## 4. Local Setup Guide

### Prerequisites
- Python 3.10+ (Python 3.11+ recommended)
- Git
- (Optional) Docker or PostgreSQL 16 with pgvector

### Step 1: Clone and Create Virtual Environment

```bash
git clone <repository-url>
cd incident-triage-agent

# Create virtual environment
python -m venv .venv
```

**Activate Virtual Environment:**
- **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **macOS / Linux:**
  ```bash
  source .venv/bin/activate
  ```

### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=models/text-embedding-004

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/incident_db
APP_ENV=development
LOG_LEVEL=INFO
PORT=8000
```

> **Note**: If `DATABASE_URL` is omitted, the service will run in in-memory fallback mode for local testing.

### Step 4: Initialize Database and Ingest Runbooks

```bash
# Initialize PostgreSQL schema, tables, and extensions
python scripts/init_db.py

# Ingest and embed runbooks into pgvector
python scripts/seed_rag.py
```

### Step 5: Start Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open API docs at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 5. Docker & Docker Compose Setup

Run the full stack (FastAPI app + PostgreSQL with pgvector) locally with a single command:

```bash
docker compose up --build
```

- FastAPI service available at: `http://localhost:8000`
- PostgreSQL pgvector available at: `localhost:5432`

---

## 6. REST API Examples

### 1. Submit an Incident

```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Authentication timeout",
    "description": "Users are receiving 504 errors during login and token refresh requests are timing out.",
    "service": "auth",
    "source": "manual"
  }'
```

**Response (HTTP 201 Created):**
```json
{
  "incident_id": "7bf394e1-2c0b-4861-8409-5a8a11ea897a",
  "status": "AWAITING_APPROVAL"
}
```

### 2. Inspect Incident Details & Pending Action

```bash
curl -X GET http://localhost:8000/api/v1/incidents/7bf394e1-2c0b-4861-8409-5a8a11ea897a
```

**Response (HTTP 200 OK):**
```json
{
  "id": "7bf394e1-2c0b-4861-8409-5a8a11ea897a",
  "title": "Authentication timeout",
  "service": "auth",
  "severity": "HIGH",
  "status": "AWAITING_APPROVAL",
  "root_cause_hypothesis": "Auth replicas are experiencing thread contention, garbage collection pauses, and Redis read lock wait timeouts.",
  "confidence": 0.88,
  "recommended_action": "restart_service",
  "action_risk": "HIGH",
  "approval_required": true,
  "pending_action": {
    "name": "restart_service",
    "service": "auth",
    "risk": "HIGH",
    "reason": "Auth replicas are experiencing thread contention, garbage collection pauses, and Redis read lock wait timeouts."
  }
}
```

### 3. Approve Action

```bash
curl -X POST http://localhost:8000/api/v1/incidents/7bf394e1-2c0b-4861-8409-5a8a11ea897a/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "reason": "Approved by on-call SRE engineer"
  }'
```

**Response (HTTP 200 OK):**
```json
{
  "id": "7bf394e1-2c0b-4861-8409-5a8a11ea897a",
  "status": "RESOLVED",
  "recommended_action": "restart_service",
  "resolved_at": "2026-09-23T12:00:00Z"
}
```

### 4. Reject Action (Alternative Flow)

```bash
curl -X POST http://localhost:8000/api/v1/incidents/7bf394e1-2c0b-4861-8409-5a8a11ea897a/reject \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Postpone remediation until traffic decreases"
  }'
```

**Response (HTTP 200 OK):**
```json
{
  "id": "7bf394e1-2c0b-4861-8409-5a8a11ea897a",
  "status": "REJECTED"
}
```

### 5. Fetch Complete Audit Trail

```bash
curl -X GET http://localhost:8000/api/v1/incidents/7bf394e1-2c0b-4861-8409-5a8a11ea897a/events
```

---

## 7. Render Deployment Guide

Deploy this service as a **Dockerized Web Service** on Render.

### Step 1: Push Repository to GitHub
```bash
git add .
git commit -m "feat: complete autonomous incident triage agent"
git push origin main
```

### Step 2: Create Web Service on Render
1. Navigate to the [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. Select **Docker** as the Environment.
5. Render will automatically detect the `Dockerfile` and `render.yaml`.

### Step 3: Configure Environment Variables in Render Dashboard
Add the following Environment Variables under the service's **Environment** tab:

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API Key | `AIzaSy...` |
| `GEMINI_MODEL` | Gemini LLM Model | `gemini-2.5-flash` |
| `GEMINI_EMBEDDING_MODEL`| Gemini Embedding Model | `models/text-embedding-004` |
| `DATABASE_URL` | Supabase or Render PostgreSQL URI | `postgresql://user:pass@host:5432/db` |
| `APP_ENV` | Application Environment | `production` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Step 4: Verify Deployment
1. Once deployed, check the health endpoint:
   ```bash
   curl https://<your-render-app>.onrender.com/health
   ```
2. Explore OpenAPI documentation:
   `https://<your-render-app>.onrender.com/docs`
3. Test submitting an incident and executing HITL approval!

---

## 8. Running Automated Tests

Run the test suite with `pytest`:

```bash
pytest -v
```

All 24 unit, agent, API, and acceptance scenario tests run in isolation with 100% pass rate.
