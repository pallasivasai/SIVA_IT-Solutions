# SIVA IT Solutions — AI Company Control Center

A Streamlit dashboard for a role-based AI engineering workflow. It displays agent-role cards, task events, provider selection, QA/security hand-offs and GitHub PR review links.

## Included features
- **Virtual Office Floor:** a pixel-art office layout with eight agent workstations, role labels and status badges driven by recorded workflow events; includes a workflow lane and recent activity log.
- **Task Board:** timestamped activity events and run filtering.
- **AI Project Room:** Atlas dispatch plan → Mira task coordination → public web evidence collection → industry-gap research → product strategy → source generation → QA/security reviews → sales plan → human-reviewed GitHub PR.
- **OpenAI primary + Gemini fallback:** fallback for likely quota/rate-limit/transient failures when Gemini is configured.
- **GitHub review workflow:** create a dedicated feature branch and PR containing generated product source files plus role reports. No merge/deployment methods are implemented.
- **Secret-safe settings:** environment variables or Streamlit Secrets; no API keys in source.
- **Autonomous scheduled discovery:** GitHub Actions runs the market-to-product pipeline daily, even when Streamlit is closed, and opens a product PR for human review. You can also start it manually from Actions.\n- **Product-per-folder delivery:** every generated product is packaged under `products/<product-slug>/` with source files, README/run instructions and `PRODUCT_BRIEF.md`; the parent `ai-workflow/README.md` includes research evidence, product strategy, QA, security and sales plan.\n- **Automated checks:** GitHub Actions runs unit tests for feature branches and PRs.

## Run locally (Windows PowerShell)

Use Python 3.11 or 3.12 for package compatibility.

```powershell
git clone https://github.com/pallasivasai/SIVA_IT-Solutions.git
cd SIVA_IT-Solutions
git checkout main
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` locally and replace placeholders with developer API keys. Set `APP_PASSWORD` to a strong, unique password before starting the dashboard. Never commit that file. Then run:

```powershell
streamlit run app.py
```

## Deploy to Streamlit Community Cloud
1. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Select `pallasivasai/SIVA_IT-Solutions`, branch `main`, and main file `app.py`.
3. In app Settings → Secrets, add the configuration keys with real values. Never put keys in source code or chat.
4. Set a strong unique `APP_PASSWORD` in Streamlit Secrets; the app locks itself when it is missing or left at the placeholder value.
5. GitHub PR integration needs a fine-grained token with only required Contents and Pull Requests permissions. Store it as `GITHUB_TOKEN`.
6. Do not share the dashboard password casually. For a real company workflow, prefer a proper identity provider / SSO and user-specific audit trails.

## Provider fallback behaviour
OpenAI is tried first. Gemini Flash-Lite (`gemini-3.5-flash-lite`) is the default low-cost fallback when OpenAI is not configured or a likely quota, rate-limit or transient-provider failure occurs. Free-tier access and quotas depend on Google's current account/model eligibility. Authentication/model configuration failures are reported instead of being silently masked. If both providers fail or exhaust their limits, the task reports an error. API billing is separate from a ChatGPT subscription; Gemini free access has quotas and is not guaranteed unlimited.

## Human approval boundary
This app creates reviewable proposals and pull requests only. It does **not** execute model-generated code, merge pull requests or deploy to production. Configure branch protection on `main` and require PR review and passing checks where available.

## Enable the unattended product-discovery schedule\n1. Open repository Settings → Secrets and variables → Actions.\n2. Add repository secrets `OPENAI_API_KEY` and optionally `GEMINI_API_KEY` (provider fallback). Do not put keys in the repo or Streamlit Secrets expecting GitHub Actions to see them; they are separate stores.\n3. Under Actions, enable workflows if GitHub asks, then open **24x7 Product Discovery Autopilot** and choose **Run workflow** to test it. A scheduled run is configured daily at 03:17 UTC.\n4. Optional repository variables: `OPENAI_MODEL`, `GEMINI_MODEL`, `AUTOPILOT_MARKET_NICHE`.\n5. The workflow uses the repository's `GITHUB_TOKEN` for branch/PR creation; its workflow permissions are limited to contents and pull requests. It creates a draft-free review PR but never merges, executes generated code or deploys.\n\n## Queue, retries and honest runtime boundaries
- Agent steps retry transient provider errors up to three attempts and record retry events; invalid credentials and other non-transient errors fail without repeated calls.
- The office view filters statuses to the newest workflow run so old `DONE` events do not look like current work. Refreshing the page is visual refresh only; it does not start workers.
- The current Streamlit task flow runs when a user submits a task, and the GitHub Actions product-discovery job is scheduled, not an always-on 24/7 daemon. A truly durable cross-process queue requires a shared persistent database and a continuously hosted worker; local SQLite alone is not durable on Streamlit Cloud restarts. Do not describe this setup as fully autonomous until that shared storage and worker are configured and tested.

## Honest limitations
- The scheduled worker is unattended between runs, not a continuously running daemon: the market-to-product workflow runs once daily by default and can be triggered manually. Each run can consume paid model API quota; monitor provider billing and disable the workflow if needed.
- The shared-password gate is a basic safety barrier, not enterprise authentication or user-specific authorization.
- The dashboard visualizes task/event status and concise operational summaries, not hidden chain-of-thought.
- Generated source is constrained to a small allowlist of text file types and size limits, and is never executed by the Streamlit server. Product files are packaged under `products/<product-slug>/`; every PR must be reviewed and its product-specific README followed. CI tests this dashboard's own Python utilities, not every generated product's runtime behavior.
- Streamlit local SQLite history may not persist across restarts/redeployments. Use managed persistent storage if durable history is needed.

## Structure
- `app.py` — dashboard, workflow and UI
- `agents.py` — team roles and hand-offs
- `ai_providers.py` — OpenAI/Gemini routing
- `github_service.py` — safe branch/PR integration
- `storage.py` — SQLite event log
- `tests/` — automated unit tests
- `.github/workflows/tests.yml` — CI checks


## Autonomous company orchestration roadmap

The `orchestration.py` module defines 25 specialist role contracts, a dependency-linked workflow blueprint, and a SQLite ledger for tasks, hand-off messages, approvals, and audit events. Set `SIVA_WORKFLOW_DB` to a durable local path for the ledger. SQLite on Streamlit Cloud's ephemeral filesystem is not durable across restarts or shared across independent workers.

The interactive workflow currently runs the established eight-agent pipeline (Atlas, Mira, Scout, Nova, Dev, Tara, Shield, Seller). It now includes one bounded remediation pass: Dev receives QA/security findings, regenerates the product source tree, and Tara/Shield re-review it. This is not yet a fully parallel 25-worker or 24/7 system; the additional roles and dependency graph are foundational architecture.

A generated source bundle is not proof of a working product. The app does not execute generated code in a sandbox, so reports must disclose tests actually run versus proposed/not-run. GitHub branch push/PR creation remains gated by configured credentials and owner approval; merges and deployments are not automated.
