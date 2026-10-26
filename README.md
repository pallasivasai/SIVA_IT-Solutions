# SIVA IT Solutions — AI Company Control Center

A Streamlit-based operations dashboard for a role-based AI engineering workflow. It visualizes role cards, tasks, timestamps, provider usage, QA/security reports and human-reviewed GitHub pull requests.

## Initial delivery scope
- Office Floor dashboard for Product Manager, Developer, QA Engineer and Security Reviewer roles.
- Task Board / operational event timeline.
- AI Project Room to submit a task and view role hand-offs.
- OpenAI primary, Gemini fallback for quota/rate-limit/transient failures.
- GitHub feature branch + Pull Request workflow; no automated merge or production deploy.
- Secrets through Streamlit Secrets or environment variables, never hard-coded.

## Status
The first commit initializes the repository. App source files and setup instructions will be added in the feature branch / PR for review.

## Safety
Generated proposals require human review. Do not put API keys in source code or commit history. API free tiers and usage limits are subject to provider policies and may change.