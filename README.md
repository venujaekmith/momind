# Momind

Momind is a Django-based maternal health and community support platform. Its
Maternal Care Agent reviews longitudinal pregnancy records, reasons about risk,
remembers previous assessments, and takes bounded care-coordination actions.

## Key Features

- User registration, login, and role selection
- Mother, father, midwife, doctor, hospital, and hospital staff profiles
- Pregnancy dashboard with progress tracking and fetal health logs
- Family linking and member management
- Clinic and hospital scheduling with appointment management
- Community forums, groups, notifications, and hospital announcements
- Auditable Maternal Care Agent with planning, tools, memory, reasoning, and actions
- Hybrid clinical-rule/XGBoost risk assessment and lab report analysis
- Chatbot session handling and message retrieval
- Postpartum assessment workflows

## Project Structure

- `accounts/` — custom user model, authentication, and profile forms
- `dashboards/` — pregnancy tracking, family management, clinic management, and baby development
- `community/` — forums, groups, schedules, and notifications
- `chat/` — chatbot interface and messaging services
- `ai_services/` — risk assessment, lab report analysis, and postpartum AI services
- `postpartum/` — postpartum-specific models, forms, and views
- `core/` — home view and shared project utilities
- `momind/` — Django project settings and URL configuration

## Installation

1. Create and activate a virtual environment.

```bash
python3 -m venv env
source env/bin/activate
```

2. Install dependencies.

```bash
pip install -r req.txt
```

3. Configure local environment variables (the defaults are suitable for local
   development without AI):

```bash
export DJANGO_DEBUG=true
export GROQ_API_KEY="your-optional-groq-key"
export GROQ_MODEL="openai/gpt-oss-120b"
```

4. Apply database migrations.

```bash
python3 manage.py migrate
```

5. Create a superuser if needed.

```bash
python3 manage.py createsuperuser
```

6. Run the development server.

```bash
python3 manage.py runserver
```

If the virtual environment is not activated, run it directly with:

```bash
env/bin/python manage.py runserver
```

7. Open the app in your browser at `http://127.0.0.1:8000/`.

## Demo data

Create or refresh a realistic test data set with:

```bash
python3 manage.py seed_demo
```

The command is safe to run repeatedly and does not remove existing accounts. It
creates these role-specific demo logins:

- `demo_mother`
- `demo_postpartum`
- `demo_father`
- `demo_midwife`
- `demo_doctor`
- `demo_hospital`
- `demo_staff`

The default password for every demo login is `MomindDemo2026!`. Use
`python3 manage.py seed_demo --password "your-password"` to choose a different
demo password.

## Notes

- The project currently uses SQLite by default (`db.sqlite3`).
- Static files are served by Django in development mode.
- Production deployment requires `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`,
  `DJANGO_ALLOWED_HOSTS`, HTTPS, and a persistent `DJANGO_MEDIA_ROOT`.
- AI and chat functionality may require API credentials or environment configuration for external services.

## Maternal Care Agent

The primary agent is not the support chatbot. It is a bounded, tool-using
workflow implemented in `ai_services/services/maternal_agent.py`.

For every run, the agent:

1. Retrieves up to five previous risk assessments as longitudinal memory.
2. Builds a plan based on the records available for the pregnancy.
3. Inspects pregnancy progress, fetal health, lab reports, postpartum wellness,
   and the linked care team.
4. Runs hybrid risk reasoning using a deployed XGBoost model when available,
   otherwise deterministic safety rules.
5. Uses Groq to turn the evidence into a structured, supportive explanation
   when an API key is configured.
6. Selects actions using a safety policy. Every level creates in-app care-team
   notifications; high and critical levels also create an in-app emergency
   alert and require human review.
7. Persists the plan, memory snapshot, rationale, tool inputs, tool outputs,
   selected actions, and final result in `AgentRun` and `AgentStep` records.

The agent is intentionally constrained. It cannot diagnose, prescribe, modify
clinical observations, contact emergency services, or send information outside
the application. Its output is decision support for qualified humans.

### Run and inspect the agent

1. Log in as a linked mother, father, midwife, doctor, hospital, or hospital
   staff member.
2. Open a pregnancy's patient details.
3. Select **Run Maternal Care Agent**.
4. Review the result and open the risk dashboard to see the complete reasoning
   trace and actions.

The main endpoints are:

- `POST /ai/risk-assess/<pregnancy_id>/` — execute a complete agent run.
- `GET /ai/show-risk/<pregnancy_id>/` — view the assessment and reasoning trace.
- `GET /ai/agent-runs/<run_uuid>/` — retrieve the access-controlled audit JSON.

With no `GROQ_API_KEY`, the complete workflow still runs using deterministic
clinical rules and safe fallback explanations. This makes local demonstrations
repeatable without simulating agent actions.

## Dependencies

The exact Python dependencies are pinned in `req.txt`. The main runtime
dependencies are:

- `Django==6.0.7`
- `groq`
- `xgboost`
- `pandas` and `numpy`
- `pypdf`

Frontend templates also load Bootstrap, Font Awesome, FullCalendar, Chart.js,
Marked, QRCode.js, html5-qrcode, and Google Fonts from their respective CDNs.

## License and third-party software

Momind's original source code is available under the [MIT License](LICENSE).
Dependencies, hosted AI services, models, icons, and fonts remain subject to
their own licenses and service terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
for the applicable acknowledgements and redistribution notes. Uploaded or
user-provided files are not automatically covered by the project's MIT License.

## Future enhancement roadmap

The items below are planned enhancements, not claims about the current
prototype. Development will remain human-supervised, privacy-conscious, and
clinically reviewed.

### 1. Independent doctors and broader care networks

- Allow verified independent doctors to join without requiring employment by a
  registered hospital.
- Add credential verification, specialty, service area, availability, referral
  acceptance, and professional-status workflows.
- Support consent-based links between independent clinicians, mothers,
  midwives, laboratories, and hospitals, with time-limited access where needed.
- Add referral, second-opinion, handover, and clinician substitution workflows
  while preserving a complete audit history.

### 2. Shared doctor-midwife care workspace

- Introduce a shared dashboard for care plans, observations, appointments,
  tasks, referrals, and follow-up ownership.
- Add structured handover notes, secure team messaging, mentions, and read
  receipts so important updates are not lost between visits.
- Show which professional is responsible for each next action and when it is
  due, with escalation for overdue reviews.
- Require human acknowledgement and resolution notes for high-risk agent
  alerts; the AI remains decision support rather than an autonomous clinician.

### 3. A richer mother experience

- Add a personalized daily and weekly care plan, appointment preparation,
  symptom journaling, medicine and supplement reminders, and easier access to
  personal health details.
- Provide pregnancy and postpartum education reviewed by clinicians and adapted
  to pregnancy stage, language, and recorded needs.
- Add consent controls that clearly show who can access each part of the record,
  plus self-service export, correction, and access-revocation requests.
- Expand postpartum recovery, mental-wellness, breastfeeding, newborn-care,
  and family-support workflows without replacing professional care.

### 4. Secure and encrypted lab-report handling

- Encrypt uploaded reports in transit and at rest using envelope encryption,
  with keys held outside application storage by a managed key service.
- Use role- and relationship-based authorization, short-lived signed download
  links, access logs, key rotation, secure backups, and configurable retention
  and deletion policies.
- Add malware scanning, file-type validation, integrity hashes, upload limits,
  and protection against unsafe document parsing.
- Keep AI processing consent-based, minimize the information sent to external
  providers, and support private or locally hosted analysis where required.

### 5. Stronger hospital alignment and interoperability

- Integrate with authorized hospital registration, laboratory, appointment,
  referral, pharmacy, and discharge workflows.
- Use documented healthcare interoperability approaches such as HL7 FHIR where
  appropriate instead of creating irreversible vendor-specific integrations.
- Add hospital-configurable roles, departments, clinic rules, escalation paths,
  approval queues, and service-level reporting.
- Preserve data provenance so clinicians can distinguish patient-entered,
  device-generated, imported, and professionally verified observations.

### 6. Hospital-scale data and operations

- Move production workloads from SQLite to PostgreSQL and use background jobs,
  caching, object storage, pagination, and indexed search for large datasets.
- Add tenant isolation, rate limits, idempotent imports, bulk scheduling,
  duplicate detection, and safe retry handling.
- Introduce monitoring, audit-event pipelines, encrypted backups, disaster
  recovery, performance testing, and capacity planning.
- Give hospitals privacy-preserving operational dashboards for clinic demand,
  waiting times, workload, missed follow-ups, and resource planning.

### 7. Smart midwife matching and route planning

- Recommend midwives using consented location, availability, workload,
  language, verified skills, care continuity, risk needs, and travel time.
- Explain why a match was recommended, monitor fairness, and always allow the
  mother or authorized coordinator to choose or override the recommendation.
- Create optimized visit routes with time windows, priority, transport limits,
  and emergency constraints while revealing precise locations only to
  authorized users.
- Add offline visit lists, safe check-in, navigation handoff, route changes, and
  workload balancing for community care teams.

### 8. Wearables and connected health data

- Integrate consented sources such as Apple Health, Android Health Connect, and
  supported clinical devices for activity, sleep, heart rate, blood pressure,
  glucose, and other relevant observations.
- Normalize units, record device provenance and quality, detect missing or
  implausible readings, and let users pause or revoke synchronization.
- Summarize trends for clinicians without treating consumer-device readings as
  diagnoses; safety alerts will use clinically reviewed thresholds and human
  confirmation.

### 9. Accessibility, inclusion, and continuity of care

- Add Sinhala and Tamil interfaces, locally reviewed safety language, accessible
  forms, screen-reader support, and low-literacy presentation modes.
- Build an offline-friendly progressive web experience with queued sync for
  communities with intermittent connectivity.
- Add teleconsultation, referral tracking, emergency contact guidance, and
  continuity plans when a clinician becomes unavailable.

### 10. Responsible AI and measurable outcomes

- Validate thresholds and model performance with clinicians and representative,
  consented datasets before clinical deployment.
- Add versioned models and tools, evaluation datasets, bias and drift checks,
  false-positive monitoring, and rollback controls.
- Measure useful outcomes such as earlier reviewed warning signs, completed
  follow-ups, reduced coordination delays, and clinic waiting-time improvements.
- Support de-identified research and public-health analysis only with suitable
  governance, consent or legal authority, and re-identification safeguards.

## Prototype evolution

The prototype keeps the original maternal-care coordination direction while
making the AI component safer and more explicit. The conversational assistant
is treated as a support feature; the central AI capability is now an auditable
Maternal Care Agent with tool use, persistent memory, multi-step decisions, and
bounded application actions.

## URL Routes

- `/` — home
- `/accounts/` — authentication and profile details
- `/dashboards/` — pregnancy and clinic dashboards
- `/community/` — forums, groups, notifications
- `/chat/` — chatbot endpoints
- `/ai/` — AI services endpoints
- `/postpartum/` — postpartum workflows


## Verification

Run the project checks and test suite with:

```bash
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
python3 manage.py test
```
