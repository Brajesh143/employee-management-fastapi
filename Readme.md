Features
    Login
    JWT Authentication
    Employee CRUD
    Department CRUD
    Role CRUD
    Attendance
    Leave Management
    Salary Management
    Search Employees
    Pagination
    Sorting
    File Upload (Resume/Profile Image)

Tables:
    Employee
    Department
    Role
    Attendance
    Leave
    Salary

Phase 2: Add AI Features

For example:

    Feature 1: Employee Profile Summary ⭐⭐⭐⭐⭐

        Input
            Name:
            Experience:
            Skills:
            Projects:
            Department:

        AI Output

        Brajesh is a Senior MERN Developer with 8 years of experience.
        He specializes in React, Node.js, FastAPI, LangChain and AI applications.

    Feature 2: Job Description Generator

        Input

            Role = Python Developer
            Experience = 4 Years

        Output

            Generate professional Job Description

    Feature 3: Email Generator
        
        Input

            Leave Approved

        Output

            Generate approval email

    Feature 4: Performance Review
        
        Input

            Projects Completed
            Attendance
            Rating

        Output

            Generate professional performance review.

AI Models: ollama pull gemma3:4b


Employee:

    Permissions: Able to see dahboard, with (attendance, leave balance, salary and profile), Able to see the attendenc and create attendance, able to see all leaves and create leaves


HR:

    Permission and action:
    Able to see leaves, approve leaves, leave request

## Streamlit employee management

Start the FastAPI backend, apply the database migrations, and seed roles and
permissions before launching the Streamlit frontend:

```bash
# Run once. Append to an existing .env rather than replacing its other settings.
printf '\nJWT_SECRET_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
./myenv/bin/alembic upgrade head
./myenv/bin/python seed/run_seed.py
./myenv/bin/uvicorn main:app --reload
```

Keep the generated `JWT_SECRET_KEY` private and stable across backend restarts
and workers. The API rejects missing or shorter-than-32-byte signing keys.
Access tokens expire after 30 minutes. Logging out revokes the active token;
changing a password invalidates all previously issued tokens for that account.
Existing access tokens must be refreshed by signing in again after this update.
New passwords are stored with bcrypt. Existing salted SHA-256 password hashes
for passwords up to 72 UTF-8 bytes are upgraded to bcrypt on successful login;
longer legacy passwords remain verifiable until changed.

SMTP-based password reset is disabled until SMTP is configured. Signed-in users
can change their password from the **Change password** page; the current
password is required and all existing sessions are invalidated after a
successful change. Users who cannot sign in must contact an administrator.

In another terminal:

```bash
./myenv/bin/streamlit run frontend/app.py
```

Set `API_BASE_URL` in the frontend environment when FastAPI is not running at
`http://127.0.0.1:8000`. The Employee Management workspace provides a filtered
employee directory and CSV export, employee hire/manager/designation assignment,
document upload and download, CSV import dry-run preview, designation
management, and soft-exit recording. Access to each action is enforced by the
backend role permissions.

Permission catalog administration is available under `/permissions` and
requires `permission:manage`. Role permission assignments can be inspected with
`GET /permissions/roles/{role_id}/permissions` and replaced with
`PUT /permissions/roles/{role_id}/permissions` by users with `role:assign`.
Super Admin always retains every permission; newly created permission
definitions are automatically assigned to Super Admin roles.

Audit history is available in the Streamlit **Audit logs** page and through
`GET /audit-logs/`. Access requires `audit:read`. The endpoint supports
pagination and filtering by actor, action, resource, and date range. Employee,
role, permission, and attendance changes record before/after snapshots; employee
snapshots exclude password hashes and other authentication secrets.

Attendance self-service is available from the Streamlit **Attendance** page.
Employees can check in and out, view their attendance history, request WFH, and
submit corrections. Managers and authorized HR/Admin users can review requests
within their reporting scope. The attendance report supports date ranges and
optional department filtering; report access requires `report:read`.
Check-in/check-out endpoints are `POST /attendance/check-in` and
`POST /attendance/check-out`; correction requests use
`POST /attendance/corrections`.

Agentic AI — LangGraph, LangChain, Multi-Agent Systems, Agent Memory
MCP — Tools, Resources, MCP servers/clients
AI Security — Prompt Injection, Guardrails, PII, Permissions
LLM Evaluation — RAG/Agent evaluation, LangSmith/Langfuse/Ragas

| Step  | Focus            | What to implement                                  |
| ----- | ---------------- | -------------------------------------------------- |
| **1** | 🔐 AI Security   | Prompt injection, RBAC, tool permissions, PII      |
| **2** | 🛡️ Guardrails   | Input/output validation, restricted tool calls     |
| **3** | 📊 Observability | LangSmith/Langfuse, logs, token/cost/latency       |
| **4** | 🧪 Evaluation    | Agent tests, RAG evaluation, hallucination testing |
| **5** | 🔄 Reliability   | Retry, timeout, fallback, error handling           |
| **6** | 🚀 Production    | Docker, CI/CD, AWS deployment                      |
| **7** | 📈 Scaling       | Redis, queues, async workers, Kafka/SQS            |


                         User
                           │
                           ▼
                     Streamlit UI
                           │
                           ▼
                       FastAPI
                           │
                    Authentication
                           │
                    ┌──────▼──────┐
                    │ Agent Router│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         HR Agent     Attendance     Leave Agent
              │            │            │
              └────────────┼────────────┘
                           ▼
                    Permission Check
                           │
                    ┌──────▼──────┐
                    │    Tools    │
                    └──────┬──────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
         PostgreSQL      Redis          RAG
                                           │
                                      Vector DB
                                           │
                                           ▼
                                          LLM
                           │
                           ▼
                    Guardrail / Validation
                           │
                           ▼
                       Response
                           │
                           ▼
                    LangSmith/Langfuse




                  AI Agent
                     │
                  MCP Client
                     │
             ┌───────┴───────┐
             │   MCP Server  │
             └───────┬───────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      Tools       Resources     Prompts
        │            │
        ▼            ▼
   APIs / DB      Files / Data


Build these into your existing application:

Tool-level RBAC
Prompt-injection protection
PII detection/masking
Input validation
Output validation
Human approval for sensitive operations
Audit logging of every agent/tool call

After that, move to Agent Evaluation → Observability → Production Deployment.