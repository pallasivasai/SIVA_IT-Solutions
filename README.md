# SIVA IT Solutions — AI Company Control Center

A Streamlit dashboard for a role-based AI engineering workflow. It displays agent-role cards, task events, provider selection, QA/security hand-offs and GitHub PR review links.

## Included features
- **Office Floor:** Product Manager, Software Engineer, QA Engineer and Security Reviewer cards.
- **Task Board:** timestamped activity events and run filtering.
- **AI Project Room:** submit a requirement and see role-based work reports.
- **OpenAI primary + Gemini fallback:** fallback for likely quota/rate-limit/transient failures when Gemini is configured.
- **GitHub review workflow:** create a dedicated feature branch and PR containing a review artifact. No merge/deployment methods are implemented.
- **Secret-safe settings:** environment variables or Streamlit Secrets; no API keys in source.
- **Automated checks:** GitHub Actions runs unit tests for feature branches and PRs.

## Run locally (Windows PowerShell)

Use Python 3.11 or 3.12 for package compatibility.

```powershell
git clone https://github.com/pallasivasai/SIVA_IT-Solutions.git
cd SIVA_IT-Solutions
git checkout feat/ai-company-control-center
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
2. Select `pallasivasai/SIVA_IT-Solutions`, branch `feat/ai-company-control-center`, and main file `app.py`.
3. In app Settings → Secrets, add the configuration keys with real values. Never put keys in source code or chat.
4. Set a strong unique `APP_PASSWORD` in Streamlit Secrets; the app locks itself when it is missing or left at the placeholder value.
5. GitHub PR integration needs a fine-grained token with only required Contents and Pull Requests permissions. Store it as `GITHUB_TOKEN`.
6. Do not share the dashboard password casually. For a real company workflow, prefer a proper identity provider / SSO and user-specific audit trails.

## Provider fallback behaviour
OpenAI is tried first. Gemini is used when OpenAI is not configured or a likely quota, rate-limit or transient-provider failure occurs. Authentication/model configuration failures are reported instead of being silently masked. If both providers fail or exhaust their limits, the task reports an error. API billing is separate from a ChatGPT subscription; Gemini free access has quotas and is not guaranteed unlimited.

## Human approval boundary
This app creates reviewable proposals and pull requests only. It does **not** execute model-generated code, merge pull requests or deploy to production. Configure branch protection on `main` and require PR review and passing checks where available.

## Honest limitations
- This is a user-triggered workflow, not an always-on workforce.
- The shared-password gate is a basic safety barrier, not enterprise authentication or user-specific authorization.
- The dashboard visualizes task/event status and concise operational summaries, not hidden chain-of-thought.
- Initial PR integration packages role reports as Markdown; it does not automatically apply arbitrary multi-file code changes.
- Streamlit local SQLite history may not persist across restarts/redeployments. Use managed persistent storage if durable history is needed.

## Structure
- `app.py` — dashboard, workflow and UI
- `agents.py` — team roles and hand-offs
- `ai_providers.py` — OpenAI/Gemini routing
- `github_service.py` — safe branch/PR integration
- `storage.py` — SQLite event log
- `tests/` — automated unit tests
- `.github/workflows/tests.yml` — CI checks
