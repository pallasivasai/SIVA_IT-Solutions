# Deployment checklist

## Secrets and first run
- [ ] Configure a strong, unique APP_PASSWORD; never keep the example placeholder.
- [ ] Add OPENAI_API_KEY and OPENAI_MODEL to Streamlit Secrets.
- [ ] Add GEMINI_API_KEY and GEMINI_MODEL to Streamlit Secrets.
- [ ] Add GITHUB_TOKEN only if PR integration is needed.
- [ ] Use a fine-grained GitHub token scoped to this repository with the minimum Contents and Pull Requests permissions for branch/PR creation.
- [ ] Confirm .env and .streamlit/secrets.toml are not tracked.
- [ ] Smoke-test OpenAI success, Gemini fallback, and both-providers-failed scenarios.
- [ ] Test a documentation-only task and verify no automatic merge/deploy occurs.

## GitHub protection
- [ ] Configure branch protection or rulesets on main.
- [ ] Require a pull request before merging.
- [ ] Require CI checks to pass.
- [ ] Require human approval where your GitHub plan supports it.
- [ ] Avoid bypass permissions where practical.

## Before real company use
- [ ] Replace the shared-password gate with proper authentication/SSO and per-user authorization for company use.
- [ ] Add authentication and role-based access before publishing confidential work.
- [ ] Move event history to persistent managed storage if it must survive Streamlit restarts.
- [ ] Add task-size limits, rate limiting, quotas, secret redaction and audit retention.
- [ ] If generated-code execution is ever added, use an isolated permission-limited sandbox and explicit approval gates.
