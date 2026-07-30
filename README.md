# Momind

Momind is a Django-based maternal health and community support platform.
It includes user role management, family and pregnancy dashboards, community forums, AI-enabled risk assessment, lab report analysis, chat support, and postpartum care workflows.

## Key Features

- User registration, login, and role selection
- Mother, father, midwife, doctor, hospital, and hospital staff profiles
- Pregnancy dashboard with progress tracking and fetal health logs
- Family linking and member management
- Clinic and hospital scheduling with appointment management
- Community forums, groups, notifications, and hospital announcements
- AI risk assessment and lab report analysis endpoints
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

## Dependencies

This project depends on the packages listed in `req.txt`, including:

- `Django==6.0.7`
- `openai`
- `groq`
- `fastapi`
- `azure-*`
- `pdfminer.six`, `pdfplumber`
- `pandas`, `numpy`, `tensorflow`

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
