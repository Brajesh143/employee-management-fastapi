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
role, permission, attendance, and leave changes record before/after snapshots; employee
snapshots exclude password hashes and other authentication secrets.

Attendance self-service is available from the Streamlit **Attendance** page.
Employees can check in and out, view their attendance history, request WFH, and
submit corrections. Managers and authorized HR/Admin users can review requests
within their reporting scope. The attendance report supports date ranges and
optional department filtering; report access requires `report:read`.
Check-in/check-out endpoints are `POST /attendance/check-in` and
`POST /attendance/check-out`; correction requests use
`POST /attendance/corrections`.

Leave self-service is available from the Streamlit **Leave Management** page.
Employees can apply for leave, view their balance and request history, and
cancel pending requests or approved requests before their start date. Leave
days are counted inclusively as calendar days. Requests for employees with an
assigned manager first require that manager's approval, then final HR approval;
employees without an assigned manager go directly to HR. HR/Admin balance
changes and all leave decisions are recorded in the audit log.

The leave API is under `/leaves`: `GET /leaves/balance/me` reads the signed-in
user's balance, `PATCH /leaves/balance/{employee_id}` adjusts a balance,
`POST /leaves/{leave_id}/cancel` cancels a request, and
`GET /leaves/reports?from=YYYY-MM-DD&to=YYYY-MM-DD` returns scoped leave history
and totals. Balance changes require `leave:balance:manage`,
leave actions use the relevant `leave:*` permissions, and reports require
`report:read` or `report:team:read` together with `leave:read`.
Apply the migration and refresh the role permissions before using the updated
workflow:

```bash
./myenv/bin/alembic upgrade head
./myenv/bin/python seed/run_seed.py
```

Payroll and expense workflows are available from the Streamlit **Payroll &
Expenses** page and the `/salaries` and `/expenses` APIs. Users with
`salary:create` can configure an employee's salary structure with an effective
date. Users with `payroll:generate` can generate monthly payroll; existing
entries and employees without an effective salary structure are skipped.
Employees with `payslip:read` can view and download their own payslips, while
`salary:read` grants broader payroll access.

Employees submit claims through `POST /expenses/` and attach PDF, PNG, or JPEG
receipts through `POST /expenses/{claim_id}/receipt` (maximum 10 MB).
`expense:approve` reviewers approve or reject claims; approved claims become
eligible for payment. Users with `reimbursement:approve` mark approved claims
as reimbursed. Expense visibility follows employee/manager scope unless the
user has organization-wide access. These changes are recorded in the audit log.

Reporting and analytics are available through the Streamlit **Reporting &
Analytics** page and `GET /reports/analytics?from=YYYY-MM-DD&to=YYYY-MM-DD`.
The dashboard and reports include in-scope employee statistics, attendance and
leave summaries, monthly payroll totals, department comparisons, and employee
attrition calculated from opening headcount and recorded exit dates. The
attrition denominator includes employees with a recorded joining date on or
before the report start and no earlier exit; employees without a joining date
are excluded because their opening-period employment cannot be determined.
Payroll, attendance, and leave sections are only returned to users with the
corresponding read permissions; employee-level details follow employee/manager
visibility scope. Download CSV or PDF reports with
`GET /reports/{employees|attendance|leaves|payroll|departments|attrition}/export`,
using the same date and optional `department_id` filters and `format=csv|pdf`.
Report endpoints require `report:read` or `report:team:read`; the relevant data
read permission is also required to export sensitive report sections.

Performance and recruitment are available from the Streamlit
**Performance & Recruitment** page and the `/performance` and `/recruitment`
APIs. Managers and HR can create draft or completed reviews for employees in
their authorized scope; employees can read their own reviews. Draft reviews
can be edited by the original reviewer and become immutable when completed.
Managers and HR assign goals with measurable KPI targets and due dates;
employees can update their own progress and status.

Users with `recruitment:manage` can create and close job openings, add
candidates to open roles, move candidates through screening, interview, offer,
hire, and rejection stages, and schedule or update interviews with active
employees. Review, goal, opening, candidate, and interview changes are recorded
in the audit log. Apply the migration and refresh role permissions before use:

```bash
./myenv/bin/alembic upgrade head
./myenv/bin/python seed/run_seed.py
```

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