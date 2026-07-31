# Voice AI Lead-Qualification & Booking Agent

A production-oriented Twilio voice workflow for service businesses. It answers an inbound call, collects lead details, confirms a booking, stores a durable call record, creates a CRM lead, and escalates to a human on request.

## What is included

- Twilio webhook signature validation (enabled outside development)
- Durable call state in SQLAlchemy; use Postgres via `DATABASE_URL` in production
- Consent-free lead qualification flow: name, service, location, preferred time, phone, confirmation
- Calendar and HubSpot adapters isolated from call control
- Explicit human escalation and no-input retry path
- Docker deployment config and flow tests

## Local run

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Expose port 8000 using a trusted HTTPS tunnel for testing. Configure the Twilio phone-number voice webhook as `POST https://YOUR-DOMAIN/voice/incoming`.

Open `http://127.0.0.1:8000` to view the dashboard. The API documentation is at `/docs`.

## OpenRouter model routing

Set `OPENROUTER_API_KEY` in `.env` locally, or as a Vercel environment variable in production. The key is never exposed to the browser. Each spoken reply uses a primary model and two ordered fallbacks:

1. `~openai/gpt-latest`
2. `~anthropic/claude-sonnet-latest`
3. `openai/gpt-oss-120b`

OpenRouter performs the automatic failover. The core qualification, confirmation, and booking logic remains deterministic; if the AI provider is unavailable, the agent continues with its safe built-in prompt.

## Vercel deployment

Vercel supports this FastAPI entry point directly. Before deployment, change `DATABASE_URL` to a managed Postgres connection string: SQLite files are not durable on Vercel serverless functions.

1. Push this folder to a Git repository and import it into Vercel, or install the Vercel CLI and run `vercel` from this directory.
2. Add production environment variables: `ENVIRONMENT=production`, `DATABASE_URL`, `PUBLIC_BASE_URL`, `TWILIO_AUTH_TOKEN`, `OPENROUTER_API_KEY`, `HUBSPOT_PRIVATE_APP_TOKEN` (if used), `ESCALATION_PHONE_NUMBER`, and the business settings.
3. Deploy. Copy the production URL into `PUBLIC_BASE_URL` and redeploy once so TwiML actions use the correct URL.
4. In Twilio, set the number's Voice webhook to `POST https://YOUR-VERCEL-DOMAIN/voice/incoming`.
5. Make a test call and verify the CRM record, calendar write, and escalation path before going live.

## Production checklist

1. Set `ENVIRONMENT=production`, a Postgres `DATABASE_URL`, and a stable HTTPS `PUBLIC_BASE_URL`.
2. Set `TWILIO_AUTH_TOKEN` and leave `TWILIO_VALIDATE_SIGNATURES=true`.
3. Replace `CalendarAdapter.book` with the client’s Google/Microsoft Calendar implementation; preserve idempotency with Twilio Call SID.
4. Configure HubSpot (or replace `HubSpotAdapter`) and `ESCALATION_PHONE_NUMBER`.
5. Add database migrations, monitoring/alerting, encrypted backups, retention policy, and consent language appropriate to the client’s jurisdiction.
6. Run behind a TLS-terminating reverse proxy; restrict database access and rotate all provider credentials.

## Limitations deliberately left configurable

Calendar writes use a deterministic demo adapter so this repository cannot accidentally book a real appointment. The phone-number parser and intent extraction are intentionally conservative. For an LLM-driven conversational agent, add an extraction layer with strict JSON schema validation and preserve the confirmation step before any external write.
