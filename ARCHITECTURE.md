# Employee Management System — Architecture and Complete Workflow

This document is the implementation blueprint for the Employee Management System (EMS). It is grounded in the **current FastAPI + Streamlit + SQLAlchemy** codebase and describes the target architecture, data model, request flows, background jobs, AI agents, evaluation, and AWS deployment.

**Recommended build order:** Employee Management → Authentication → Attendance → Leave Management → Notifications → Reporting → AI/RAG → AI Agents → Evaluation & Security → AWS Deployment.

---

## 1. Current System Snapshot

| Layer | Today |
| --- | --- |
| API | FastAPI (`main.py`) with routers for department, role, employee, attendance, leave, salary, auth, AI chat |
| UI | Streamlit (`frontend/app.py`) calling FastAPI with Bearer JWT |
| Database | SQLite (`sqlite:///./company.db`), Alembic migrations, SQLAlchemy 2.0 |
| Auth | Login, JWT access token (30 min), password hash, `require_permission` RBAC |
| Roles | Super Admin, Admin, Human Resource, Manager, Employee (seeded permissions) |
| AI | LangChain employee assistant + tools (attendance/leave/profile), LangSmith-ready callbacks |
| Tests | Permission seed, employee password, attendance model, permission routes |

**Existing tables:** `employees`, `departments`, `roles`, `permissions`, `role_permissions`, `attendance`, `leaves`, `salary`.

**Known gaps vs the feature list:** reporting manager, designation, documents, import/export, refresh tokens, password reset, audit logs, rate limiting, WFH/late/early/corrections, leave balances by type, multi-level leave approval, payroll runs/payslips, expenses, performance/KPI, recruitment, notifications, queues, Redis, RAG chatbot, LangGraph supervisor, observability, PII/prompt-injection, Docker/CI/CD/AWS.

---

## 2. Target Architecture

### 2.1 High-level view

```text
                        ┌─────────────────────────────────────┐
                        │           Clients                    │
                        │  Streamlit UI  ·  Mobile later       │
                        └─────────────────┬───────────────────┘
                                          │ HTTPS + JWT
                                          ▼
                        ┌─────────────────────────────────────┐
                        │         API Gateway / ALB            │
                        │  TLS, WAF, rate limit, CORS          │
                        └─────────────────┬───────────────────┘
                                          ▼
                        ┌─────────────────────────────────────┐
                        │         FastAPI (ECS/Fargate)        │
                        │  Auth · RBAC · Validation · Idempotency│
                        │  Routers → Services → Repositories   │
                        └──────┬──────────┬──────────┬────────┘
                               │          │          │
               ┌───────────────┘          │          └───────────────┐
               ▼                          ▼                          ▼
        PostgreSQL                   Redis cache              Message queue
        (RDS)                        Sessions, RBAC           (Redis/SQS)
                                     Rate limit               Celery / workers
                                     Idempotency keys
                                                                          │
                                                                          ▼
                                                              ┌─────────────────────┐
                                                              │ Background workers   │
                                                              │ Email, payroll, RAG  │
                                                              │ reminders, reports   │
                                                              └──────────┬──────────┘
                                                                         ▼
                                                              S3 · SMTP · LLM · Vector DB
```

### 2.2 Request path (every authenticated API)

```text
Client
  → Rate limiter (IP + user)
  → JWT verification (access token)
  → Refresh path if expired (client uses refresh token)
  → Permission check (role → permissions, cached in Redis)
  → Pydantic validation
  → Idempotency key (mutating payroll / leave / expense)
  → Service layer (transaction)
  → Domain events
  → Audit log
  → Response
```

### 2.3 Target folder structure

```text
employee-management/
├── main.py
├── alembic/
├── auth/                 # JWT, hashing, dependencies, RBAC
├── core/                 # config, logging, rate limit, idempotency, security
├── database/
├── models/
├── schemas/
├── crud/                 # keep thin; new logic in services/
├── services/             # business workflows (leave approval, payroll, etc.)
├── routers/
├── workers/              # Celery/RQ tasks
├── events/               # domain events + publishers
├── notifications/
├── reports/
├── rag/                  # ingest, retrieve, evaluate
├── agents/               # LangGraph graphs, tools, prompts, guardrails
├── observability/        # Langfuse/LangSmith, cost, traces
├── seed/
├── tests/
├── frontend/
├── docker/
├── .github/workflows/
└── infra/                # Terraform or CDK for AWS
```

### 2.4 Role of each backend layer

| Layer | Responsibility |
| --- | --- |
| Router | HTTP, auth dependency, status codes, pagination params |
| Schema | Request/response contracts, field validation |
| Service | Workflows, transactions, events, policy (e.g. leave multi-level approval) |
| CRUD / repository | SQLAlchemy queries, indexes, locking |
| Worker | Async jobs with retry, backoff, dead-letter |
| Agent | LLM + tools; never bypass RBAC |

---

## 3. Identity, Roles, and Permissions

### 3.1 Roles (extend seed)

| Role | Typical access |
| --- | --- |
| Super Admin | All permissions, secrets, system config |
| Admin | Org setup, employees, payroll ops, reports |
| HR | Employees, attendance corrections, leave, recruitment, expenses |
| Manager | Team attendance/leave approval, performance, team reports |
| Finance | Payroll, expenses, reimbursement, payroll reports |
| Employee | Self attendance, leave apply, own payslip, self-service AI |
| Recruiter | Job openings, candidates, and interviews |

These roles and their permission assignments are created by `seed/run_seed.py`.
The permission catalog is broader than the currently implemented routes; each
new feature must add route-level checks and enforce employee/team data scope.

### 3.2 Permission naming (`seed/permissions.py`)

Pattern: `resource:action` (already used).

The seeded catalog includes `employee:import`, `employee:export`,
`document:manage`, `attendance:correct`, `attendance:wfh`, `leave:cancel`,
`leave:balance:manage`, `payroll:generate`, `payslip:read`, expense and
reimbursement actions, `performance:review`, `recruitment:manage`,
`report:team:read`, `ai:chat`, `ai:admin`, `audit:read`,
`notification:manage`, `system:config`, and `secrets:manage`.

Every new router endpoint must use `require_permission(...)`. Manager-scoped data (team only) is enforced in the service layer using `reporting_manager_id`, not only by role name.

---

## 4. Target Data Model

### 4.1 Core HR (extend existing)

The employee foundation is implemented with the current employee model:

- `reporting_manager_id` → `employees.id` (existing; active-manager and cycle checks on assignment)
- `designation_id` → `designations.id`
- `exit_date`, `exit_reason`, and `is_active` for soft exits

**designations** — id, name, description, is_active.

**employee_documents** — employee_id, original filename, storage key, content type,
file size, and upload time. A storage protocol is implemented with local disk as
the initial adapter. Set `EMPLOYEE_DOCUMENTS_DIR` to change the storage root;
uploads accept PDF, PNG, and JPEG files up to 10 MB.

### 4.2 Employee foundation APIs

- `GET /employees` accepts pagination, search, department, designation, role,
  manager, active/status, joining-date, and allowlisted sort parameters. It
  retains the array response and returns `X-Total-Count`, `X-Page`, and
  `X-Page-Size`.
- `GET /employees/export` accepts the same filters and produces a formula-safe
  CSV file.
- `POST /employees/import/preview` validates a UTF-8 CSV without writing rows.
- `POST /employees/{id}/documents`, `GET /employees/{id}/documents`, and
  `GET /employees/documents/{id}/download` are restricted by
  `document:manage`.
- `POST /employees/{id}/exit` records exit date/reason and deactivates the
  employee without deleting the employee record.
- Designations are listed, created, and updated at `/designations`.

Apply database changes using `./myenv/bin/alembic upgrade head`.
Alembic owns schema creation and upgrades; starting the API does not create
tables automatically.

### 4.3 Auth & security

- **refresh_tokens** — jti, employee_id, hashed_token, expires_at, revoked_at, user_agent, ip
- **password_reset_tokens** — employee_id, hashed_token, expires_at, used_at
- **audit_logs** — actor_id, action, resource_type, resource_id, ip, user_agent, before/after JSON, created_at
- **idempotency_keys** — key, employee_id, request_hash, response_code, response_body, created_at

### 4.4 Attendance (extend `attendance`)

Add: `source` (web/mobile/import), `work_mode` (office/wfh), `late_minutes`, `early_leave_minutes`, `shift_id`, `notes`.

New:

- **shifts** — start_time, end_time, grace_minutes, working_hours
- **attendance_corrections** — original_attendance_id, requested_check_in/out, reason, status, reviewed_by, reviewed_at
- **holidays** — date, name, region

Unique constraint: `(employee_id, attendance_date)`.

### 4.5 Leave (extend `leaves`)

Add: `policy_id`, `current_approver_id`, `approval_level`, `cancelled_at`, `cancelled_by`.

New:

- **leave_policies** — leave_type, annual_quota, carry_forward, max_consecutive, gender_restriction
- **leave_balances** — employee_id, policy_id, year, entitled, used, pending, remaining
- **leave_approval_steps** — leave_id, level, approver_id, status, comment, acted_at

### 4.6 Payroll & expenses

Extend **salary** or split:

- **salary_structures** — employee_id, effective_from, basic, hra, allowances JSON, tax_regime
- **payroll_runs** — month, year, status (draft/processing/locked/paid), generated_by, idempotency_key
- **payslips** — payroll_run_id, employee_id, components JSON, net, pdf_key
- **expense_claims** — employee_id, amount, category, description, status, paid_at
- **expense_receipts** — claim_id, s3_key
- **expense_approvals** — claim_id, approver_id, status, comment

### 4.6 Performance & recruitment

- **goals** — employee_id, cycle, title, kpi, target, weight, status
- **performance_reviews** — employee_id, reviewer_id, cycle, ratings JSON, comments, ai_summary
- **job_openings** — title, department_id, status, jd_text (AI-generated allowed)
- **candidates** — opening_id, name, email, resume_key, stage, ai_screen_score
- **interviews** — candidate_id, interviewer_id, scheduled_at, feedback, status

### 4.7 Notifications, jobs, AI

- **notifications** — employee_id, channel (in_app/email), title, body, read_at, related_type/id
- **job_runs** — job_name, payload, status, attempts, last_error, next_retry_at
- **policy_documents** — title, version, s3_key, chunk_count, ingested_at
- **llm_traces** — request_id, employee_id, agent_name, tokens_in/out, latency_ms, cost, status
- **human_approvals** — agent_action, payload, requested_by, approved_by, status (for sensitive AI actions)

---

## 5. Feature Workflows

### 5.1 Employee Management

#### Employee CRUD

```text
HR/Admin (permission employee:create)
  → POST /employees
  → Validate unique email + employee_code
  → Hash initial password (or send invite)
  → Assign department, designation, role, reporting_manager
  → Allocate default leave balances for current year
  → Emit EmployeeCreated
  → Audit log
```

Update/delete follow `employee:update` / `employee:delete`. Soft-delete via `is_active=false` + `exit_date` for attrition reporting. Hard delete only Super Admin and blocked if payroll/leave history exists.

#### Department and designation

- Departments: existing CRUD.
- Designations nested under department: `GET/POST /designations`, unique `(department_id, name)`.
- Deactivating a department fails if active employees remain (unless reassigned).

#### Reporting manager

```text
PATCH /employees/{id}  { reporting_manager_id }
  → Manager must be active employee
  → Reject self-reporting and cycles (A→B→A)
  → Manager's team queries use recursive/reporting_manager_id filter
```

#### Profile and documents

```text
Employee/HR uploads file
  → Virus/mime size check
  → Store in S3 under employees/{id}/docs/{uuid}
  → Persist employee_documents metadata
  → Sensitive docs (ID, bank) require extra permission to read
```

Profile image already exists as `profile_image`; migrate path from local disk to S3.

#### Search, filter, sort, pagination

Standard list contract for employees (and later attendance/leave/payroll):

```text
GET /employees?q=&department_id=&status=&manager_id=&page=1&page_size=20&sort=last_name&order=asc
```

Response: `{ items, total, page, page_size }`. Indexes on `email`, `employee_code`, `department_id`, `status`, `reporting_manager_id`.

#### Excel/CSV import and export

```text
Import:
  Upload CSV → validate rows (schema + FK) → dry-run report of errors
  → Confirm → batch insert in transaction (chunks of 100)
  → Job status via notifications

Export:
  Apply same filters as list → stream CSV/XLSX
  → Audit employee:export
```

---

### 5.2 Authentication & Security

#### Login / logout

```text
POST /auth/login  { email, password }
  → Verify hash, is_active
  → Issue access JWT (15–30 min) + refresh JWT (7–30 days, stored hashed)
  → Update last_login
  → Audit AuthLoginSuccess / AuthLoginFailed

POST /auth/logout
  → Revoke refresh token (jti)
  → Client discards access token
```

#### JWT + refresh

```text
Access expired
  → POST /auth/refresh { refresh_token }
  → Rotate refresh token (invalidate old jti)
  → Return new access + refresh
```

Access token claims: `sub` (employee_id), `role_id`, `jti`, `type=access`. Never put permissions in a long-lived token; load from Redis cache keyed by `role_id`.

#### RBAC and permissions management

- Seed remains source of default map.
- Admin UI: `GET/POST /roles`, `PUT /roles/{id}/permissions`.
- Changing permissions invalidates Redis key `rbac:role:{id}`.
- Super Admin `*` stays seed-only; do not grant from UI without confirmation.

#### Password reset

```text
POST /auth/forgot-password { email }
  → Always return 202 (no email enumeration)
  → If user exists, store hashed token (15 min) and enqueue email

POST /auth/reset-password { token, new_password }
  → Validate strength, mark token used, rotate password, revoke all refresh tokens
```

Change-password already exists; keep it for authenticated users.

#### Audit logs

Write asynchronously (queue) for: auth, employee PII changes, leave/payroll/expense decisions, permission changes, AI tool calls, document access.

`GET /audit-logs` with filters; `audit:read` only.

#### Rate limiting and validation

| Limit | Default |
| --- | --- |
| Login | 5 / 15 min / IP+email |
| Password reset | 3 / hour / email |
| General API | 120 / min / user |
| AI chat | 20 / min / user |
| Import | 5 / hour / user |

Validation: Pydantic on all bodies; file type allow-list; max upload size; SQL parameterized only (SQLAlchemy). Secrets from env / AWS Secrets Manager, never hardcoded (`SECRET_KEY` today must move).

---

### 5.3 Attendance Management

#### Check-in / check-out

```text
POST /attendance/check-in
  → One open record per employee per day (unique constraint)
  → Set check_in, work_mode (office|wfh)
  → Compare shift start + grace → late_minutes, status Late/Present

POST /attendance/check-out
  → Require open check-in
  → working_hours = check_out - check_in (minus unpaid break if configured)
  → overtime if > shift length
  → early_leave_minutes if before shift end
```

#### WFH

Employee may check in with `work_mode=wfh` if policy allows, or submit WFH request that manager approves. Reports separate Office vs WFH days.

#### Corrections

```text
Employee POST /attendance/corrections
  → Pending
  → Notify manager
  → Manager approve/reject (attendance:correct)
  → On approve: update attendance row in a transaction + audit
```

#### Reports

`GET /reports/attendance?from&to&department_id` — present/absent/late/WFH/overtime. Used by dashboard and payroll (unpaid days).

---

### 5.4 Leave Management

#### Apply

```text
POST /leaves
  → Validate dates, overlap, holidays, balance (remaining - pending)
  → total_days = business days - holidays
  → Deduct into pending balance (not used yet)
  → Create approval_steps from policy (Manager L1, HR L2 if days > N)
  → Notify current_approver
  → Status = Pending
```

#### Multi-level approval

```text
POST /leaves/{id}/approve | /reject
  → Caller must be current_approver or hold leave:approve for that level
  → Reject: restore pending balance, notify employee, stop workflow
  → Approve: mark step; if more levels, advance current_approver
  → Final approve: pending → used, status Approved, notify, optional calendar block
```

#### Balance

Yearly accrual job (Jan 1 or join-date prorate). Carry-forward per policy. HR can adjust with `leave:balance:manage` + reason (audit).

#### Cancel

Employee cancel if still Pending (or Approved but start_date in future per policy). Restore balances. Notify approvers.

#### History and reports

`GET /leaves?employee_id&status&type&from&to` plus department aggregates for analytics.

---

### 5.5 Payroll & Expenses

#### Salary structure

HR/Finance sets `salary_structures` with effective dates. Employee `salary` column becomes derived/display-only.

#### Monthly payroll

```text
POST /payroll/runs  { month, year }  + Idempotency-Key
  → Lock run (status processing)
  → For each active employee:
        base from structure
        + attendance overtime / unpaid absences
        - statutory tax/deduction
        = net
  → Create payslip rows
  → Status locked
  → Enqueue PDF generation + email
```

Idempotency: same key + same body returns original run; different body with same key → 409.

#### Payslip

Employee `payslip:read` only own; Finance all. PDF stored on S3; signed URL for download.

#### Expenses

```text
Employee creates claim + uploads receipts to S3
  → Manager/Finance approve
  → Status Approved → Reimbursed (payment_date)
  → Appear in next payroll as reimbursement or separate payout
```

Sensitive AI must not auto-approve expense or payroll; human approval required.

---

### 5.6 Performance & Recruitment

#### Goals / KPI

Employee + manager set goals for a review cycle. Progress updates. Dashboard: on-track / at-risk.

#### Reviews

```text
Cycle opens
  → Self review + manager review
  → Optional 360
  → AI drafts summary from goals + attendance + completed projects (human edits)
  → Finalize and lock
```

#### Job openings and candidates

```text
HR creates opening → optional AI JD generator
  → Candidates + resume (S3) → AI parse/screen (score is advisory)
  → Stage pipeline: applied → screen → interview → offer → hired/rejected
  → Interview scheduling: conflict check vs interviewer calendar
  → Hired: create employee from candidate (reuse employee:create)
```

---

### 5.7 Notifications & Background Jobs

#### Channels

| Event | In-app | Email |
| --- | --- | --- |
| Leave pending approval | Yes | Yes |
| Leave approved/rejected | Yes | Yes |
| Attendance correction | Yes | Yes |
| Payslip available | Yes | Yes |
| Expense decision | Yes | Yes |
| Interview scheduled | Yes | Yes |
| Password reset | No | Yes |
| Scheduled reminders (check-out missing, leave starting tomorrow) | Yes | Optional |

#### Job processing

```text
API/service emits domain event
  → Queue (Redis list / SQS)
  → Worker picks job
  → Success → mark complete
  → Fail → exponential backoff (1m, 5m, 30m, 2h)
  → Max attempts → dead-letter + alert (CloudWatch)
```

Workers: `send_email`, `generate_payslip_pdf`, `ingest_policy_document`, `accrue_leave`, `attendance_reminder`, `export_report`, `ai_eval_batch`.

---

### 5.8 Reporting & Analytics

Dashboard widgets (RBAC-scoped: employee self, manager team, HR org):

- Headcount by department/status
- Attendance % , late trend, WFH share
- Leave utilization by type
- Payroll cost by department
- Attrition: exits / average headcount, reason breakdown
- Open jobs and pipeline conversion

Exports: CSV stream from API; PDF via worker (WeasyPrint or ReportLab) uploaded to S3.

All report queries go through indexed aggregates or materialized daily snapshots if lists exceed ~100k rows.

---

### 5.9 AI-Powered Features

#### Shared AI request flow

```text
User message
  → Auth + ai:chat permission
  → Rate limit
  → Prompt-injection + PII scan (input)
  → Router / LangGraph supervisor
  → Retrieve context (RAG and/or DB tools)
  → Tool calls always pass employee_id from JWT, never from the prompt
  → Output validation + PII mask
  → Trace (tokens, latency, cost)
  → Response + optional human-approval ticket
```

#### HR Policy Chatbot (RAG)

```text
Ingest: HR uploads PDF/MD → S3 → chunk → embed → Chroma/pgvector
Query: retrieve top-k → answer only from context → cite document+section
Eval: faithfulness, context precision (Ragas) on a golden set
```

If retrieval is empty: refuse rather than guess.

#### Employee Self-Service Assistant (exists; extend)

Current: `POST /api/v1/ai/chat` with tools scoped to `current_user.id`. Extend tools: leave balance, apply leave (draft only), attendance summary, payslip list, policy RAG. Apply-leave and check-in as **draft + confirm** in UI, not silent writes, until human-approval framework is live.

#### AI Leave Management Agent

- Draft application from natural language (“sick tomorrow”)
- Check balance and overlapping dates via tools
- For managers: summarize pending requests and policy risks
- Approve/reject only after `human_approvals` record is confirmed

#### AI Attendance Analysis

Batch job + on-demand: late patterns, absenteeism risk, department outliers. Output is a report, not a disciplinary action.

#### AI Document Processing

Resumes and KYC: extract fields → employee/candidate draft → HR confirms. Mask ID numbers in logs.

#### Multi-agent HR workflow (LangGraph)

```text
                    ┌─────────────┐
                    │ Supervisor  │  (intent classify + RBAC)
                    └──────┬──────┘
           ┌─────────┬─────┴──────┬──────────┬──────────┐
           ▼         ▼            ▼          ▼          ▼
        Policy     Employee    Leave      Attendance   Recruiter
        RAG        Self-svc    Agent      Analyst      Agent
           │         │            │          │          │
           └─────────┴────────────┴──────────┴──────────┘
                                 ▼
                         Shared tool layer
                    (RBAC, DB, S3, notifications)
                                 ▼
                         Guardrail + tracer
```

Supervisor never forwards a tool the user's role cannot call. Cross-agent state lives in LangGraph checkpointer (Postgres/Redis).

#### AI-generated reports

Scheduled or on-demand summaries (weekly team attendance, monthly HR digest). Stored as report artifacts with model/version for audit.

---

### 5.10 AI Evaluation & Security

| Control | How |
| --- | --- |
| Tracing | LangSmith or Langfuse; `request_id` already logged in `routers/ai_chat.py` |
| Cost/latency | Callback records tokens_in/out, ms, estimated USD per model |
| RAG eval | Golden Q&A; Ragas faithfulness / answer relevancy; fail CI if below threshold |
| Agent eval | Tool-choice tests, hallucination tests, permission-denial tests |
| Prompt injection | Deny patterns (“ignore previous”, “dump system prompt”); treat user text as untrusted; tools ignore instruction-like args |
| PII | Detect email/phone/Aadhaar/PAN/bank in prompts and traces; redact before LangSmith |
| Access control | Tools closed over `employee_id` from JWT; managers get `team_ids` from DB |
| Human approval | Payroll change, leave approve, offer send, bulk delete require `human_approvals` |

Sensitive actions: never auto-execute from LLM. Agent creates an approval row; HR/manager clicks Approve in UI.

---

### 5.11 Advanced Backend & System Design

| Concern | Design |
| --- | --- |
| Redis cache | RBAC permissions, employee profile, holiday calendar, dashboard counts (TTL 60–300s) |
| Indexing | See §4 unique/list keys; composite `(employee_id, attendance_date)`, `(status, current_approver_id)` on leaves |
| Transactions | Leave approve + balance update in one `db.begin()`; payroll run per employee savepoint |
| Concurrency | `SELECT ... FOR UPDATE` on leave_balance and open attendance row |
| Idempotency | Header `Idempotency-Key` on payroll, payments, leave apply retries |
| Events | `EmployeeCreated`, `LeaveSubmitted`, `LeaveDecided`, `AttendanceClosed`, `PayrollLocked`, `ExpenseSubmitted` |
| Rate limiting | Redis sliding window (see §5.2) |
| Load testing | Locust/k6 on login, check-in, list employees, AI chat; p95 targets documented in CI |

Event flow:

```text
Service commit
  → outbox table (same transaction)
  → publisher worker
  → queue
  → notification / search / analytics consumers
```

---

### 5.12 DevOps & AWS

```text
GitHub Actions
  → lint + pytest + RAG eval (optional nightly)
  → build Docker images (api, worker, frontend)
  → push ECR
  → migrate RDS (Alembic)
  → deploy ECS Fargate (API + worker services)
  → health checks, rollback on fail
```

| Service | Use |
| --- | --- |
| ECS/Fargate | FastAPI API, Celery worker, optional Streamlit |
| ALB | HTTPS, path routing |
| RDS PostgreSQL | Primary data (replace SQLite) |
| ElastiCache Redis | Cache, rate limit, broker (or SQS) |
| SQS | Job queue (production) |
| S3 | Documents, payslips, reports, RAG source files |
| Secrets Manager | `DATABASE_URL`, `JWT_SECRET`, SMTP, LLM keys |
| CloudWatch | Logs, metrics, alarms (5xx, queue depth, CPU) |
| CloudFront | Optional for Streamlit/static |

Docker: multi-stage images; non-root user; `DATABASE_URL` injected at runtime. Local compose: api, worker, postgres, redis, ollama/chroma.

---

## 6. End-to-End User Journeys

### 6.1 New joiner

```text
HR creates employee → invite email → set password
  → documents uploaded → leave balances accrued
  → manager assigned → appears in team dashboard
```

### 6.2 Typical workday

```text
Login → check-in (office/WFH)
  → optional AI: “how many leaves left?”
  → check-out → hours computed
  → missing check-out reminder at 8pm
```

### 6.3 Leave request

```text
Apply (UI or AI draft)
  → balance reserved
  → manager notified
  → optional HR second level
  → calendar + attendance marked Leave
  → payroll uses unpaid leave only
```

### 6.4 Month-end payroll

```text
Finance reviews attendance exceptions
  → generate payroll run (idempotent)
  → lock → PDFs → email payslips
  → expense reimbursements included
```

### 6.5 Policy question

```text
Employee asks chatbot “how many casual leaves can I carry?”
  → RAG cites Policy v3 §4
  → if they ask “apply 3 days next week” → Leave Agent drafts, waits for confirm
```

---

## 7. Phased Implementation Plan

Build in this order. Each phase is shippable with tests and permissions updated.

### Phase 1 — Employee Management (foundation)

1. Reporting manager + designations  
2. Pagination/filter/sort on all list APIs  
3. Documents + S3 interface (local disk adapter first)  
4. CSV import (dry-run) and export  
5. Soft exit fields for attrition  

**Exit criteria:** HR can hire, assign manager, attach docs, export a filtered list.

### Phase 2 — Authentication hardening

1. Refresh tokens + logout revoke  
2. Forgot/reset password  
3. Permission admin API + Redis cache  
4. Audit log writer  
5. Rate limits on auth and AI  
6. Move secrets to environment  

**Exit criteria:** stolen access token expires; refresh rotation works; login brute-force limited.

### Phase 3 — Attendance

1. Check-in/out with shift, late/early, WFH  
2. Unique per day + concurrency lock  
3. Correction workflow  
4. Attendance report API  

**Exit criteria:** one open punch per day; manager can correct; report matches punches.

### Phase 4 — Leave

1. Policies + balances table (migrate `employees.leave_balance`)  
2. Overlap/holiday calculation  
3. Multi-level approval steps  
4. Cancel + reports  

**Exit criteria:** cannot overbook; two-level path works; balances consistent after reject/cancel.

### Phase 5 — Notifications & jobs

1. Outbox + Redis/SQS worker  
2. In-app notification inbox  
3. Email templates (leave, payslip, reset)  
4. Retry + DLQ  
5. Scheduled reminders  

**Exit criteria:** leave apply produces in-app + email; failed email retries then DLQ.

### Phase 6 — Payroll, expenses, performance, recruitment

1. Salary structures + payroll run + payslip PDF  
2. Expense claims  
3. Goals + reviews  
4. Jobs, candidates, interviews  

Can be split as 6a Payroll, 6b Talent if needed. Payroll should not start before attendance + leave are trustworthy.

### Phase 7 — Reporting

1. Dashboard aggregates  
2. Attrition, department, payroll reports  
3. CSV/PDF export jobs  

### Phase 8 — AI/RAG

1. Policy ingest pipeline + vector store  
2. Policy chatbot with citations  
3. Extend current employee assistant tools  
4. Input/output guardrails  

### Phase 9 — AI agents (LangGraph)

1. Supervisor graph  
2. Leave agent + attendance analyst  
3. Document processing  
4. Human-approval gate for writes  

### Phase 10 — Evaluation & security

1. Langfuse/LangSmith dashboards  
2. Token/cost in `llm_traces`  
3. Ragas + agent pytest suite in CI  
4. PII redaction, injection tests  

### Phase 11 — AWS deployment

1. Dockerfile + compose for local prod-parity  
2. GitHub Actions  
3. RDS Postgres migration from SQLite  
4. ECS, S3, Secrets, CloudWatch  
5. Load test against staging  

---

## 8. API Surface (target)

Prefix existing routers; version public AI already under `/api/v1`.

| Area | Examples |
| --- | --- |
| Auth | `POST /auth/login`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `/change-password`, `GET /auth/me` |
| Employees | `CRUD /employees`, `/employees/import`, `/employees/export`, `/employees/{id}/documents` |
| Org | `/departments`, `/designations`, `/roles`, `/roles/{id}/permissions` |
| Attendance | `/attendance/check-in`, `/check-out`, `/corrections`, reports |
| Leave | `/leaves`, `/leaves/{id}/approve`, `/reject`, `/cancel`, `/balances` |
| Payroll | `/salary-structures`, `/payroll/runs`, `/payslips` |
| Expenses | `/expenses`, `/expenses/{id}/approve` |
| Talent | `/goals`, `/reviews`, `/jobs`, `/candidates`, `/interviews` |
| Notify | `GET /notifications`, `POST /notifications/{id}/read` |
| Reports | `/reports/dashboard`, `/attendance`, `/leave`, `/payroll`, `/attrition` |
| AI | `POST /api/v1/ai/chat`, `/ai/policy`, `/ai/approvals/{id}` |
| Admin | `/audit-logs`, `/admin/jobs` |

---

## 9. Consistency Rules (non-negotiable)

1. **JWT identity is the only identity tools may use.** Models cannot choose `employee_id`.  
2. **Every mutating HR action writes an audit log.**  
3. **Leave and payroll mutations are transactional and idempotent.**  
4. **LLM output is never the source of truth** for balances, salary, or approvals.  
5. **Files live in object storage;** DB stores keys and metadata only.  
6. **SQLite is local-dev only;** production is PostgreSQL.  
7. **New endpoints ship with permission seed + at least one test.**  

---

## 10. Mapping: feature list → this repo

| Feature list item | Start from |
| --- | --- |
| Employee CRUD, dept, search | `routers/employee.py`, `department.py`, `crud/employee.py` |
| Auth JWT, RBAC | `auth/`, `routers/auth.py`, `seed/permissions.py` |
| Attendance | `models/attendence.py`, `routers/attendence.py` |
| Leave | `models/leave.py`, `routers/leave.py`, `tools/leave_tools.py` |
| Salary | `models/salary.py`, `routers/salary.py` |
| AI assistant | `agents/`, `routers/ai_chat.py`, `tools/` |
| Observability seed | `agents/callbacks.py`, `core/logging_config.py` |
| UI | `frontend/app.py` |

Use this document as the contract while implementing each phase. Update it when a workflow changes in code.
