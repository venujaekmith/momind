from chat.services.groq_client import ask_groq
from chat.services.prompts import SYSTEM_PROMPT
from chat.services.context import build_context
from chat.services.safety import safety_check
from ..models import CheckupQuestion, MaternalCheckIn, MaternalCheckup

CHECKUP_QUESTION_LIMIT = 5

def get_ai_reply(user, message, history=None):

    # 🚨 safety override
    if safety_check(message):
        return """
⚠️ This may require urgent medical attention.
Please contact a doctor or go to the nearest hospital immediately.
"""

    context = build_context(user, message)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if history:
        messages.extend(history[-10:])
    messages.append({
        "role": "user",
        "content": f"""
Role: {context['role']}
Week: {context['week']}
Phase: {context['phase']}
Relevant date: {context['delivery_date']}

User message:
{context['message']}
        """
    })

    return ask_groq(messages)


def next_check_in(user, pregnancy=None, force=False, triggered_by=None, trigger_type="weekly"):
    """Return the next question for a due weekly or explicitly triggered checkup."""
    from django.utils import timezone
    from datetime import timedelta

    latest = MaternalCheckup.objects.filter(
        user=user, pregnancy=pregnancy
    ).order_by("-requested_at").first()
    if not force and latest and latest.completed_at is None:
        return latest.checkins.filter(answered_at__isnull=True).first()
    if not force and latest and latest.requested_at > timezone.now() - timedelta(days=7):
        return None
    checkup = MaternalCheckup.objects.create(
        user=user,
        pregnancy=pregnancy,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
    )
    if pregnancy:
        from ai_services.services.maternal_agent import MaternalCareAgent

        agent_run = MaternalCareAgent().run(
            pregnancy,
            triggered_by=triggered_by or user,
            execute_actions=False,
        )
        checkup.agent_run = agent_run
        checkup.save(update_fields=["agent_run"])
    question_key, question = _question_for_checkup(checkup)
    return MaternalCheckIn.objects.create(
        checkup=checkup,
        user=user,
        pregnancy=pregnancy,
        question_key=question_key,
        question=question,
    )


def _question_for_checkup(checkup):
    return checkup_question_options(checkup)[0]


def checkup_question_options(checkup):
    """Return this checkup's bounded, personalized question queue."""
    signals = (
        checkup.agent_run.result.get("context", {}).get("symptom_signals", {})
        if checkup.agent_run else {}
    )
    counts = signals.get("counts", {})
    options = []
    if counts.get("fainting"):
        options.append((
            "personalized_fainting",
            "You previously reported fainting or feeling close to fainting. Has this happened again, and did you feel injured or confused afterward?",
        ))
    if counts.get("vomiting"):
        options.append((
            "personalized_vomiting",
            "You previously reported vomiting. How often has this happened recently, and are you able to keep fluids down?",
        ))
    if counts.get("bleeding"):
        options.append((
            "personalized_bleeding",
            "Have you had any vaginal bleeding since your last checkup? If yes, when did it start and how much was there?",
        ))
    if counts.get("severe_headache"):
        options.append((
            "personalized_headache",
            "Have you had a severe or persistent headache since your last checkup, or any changes in your vision?",
        ))
    if counts.get("dizziness") or counts.get("nausea"):
        options.append((
            "personalized_wellbeing",
            "Have dizziness or nausea affected your eating, drinking, walking, or usual daily activities since your last checkup?",
        ))
    options.extend(
        (f"custom_{item.id}", item.question)
        for item in CheckupQuestion.objects.filter(
            pregnancy=checkup.pregnancy, active=True
        )
    )
    options.extend(MaternalCheckIn.QUESTIONS)
    return options[:CHECKUP_QUESTION_LIMIT]


def checkup_is_due(user, pregnancy=None):
    from django.utils import timezone
    from datetime import timedelta

    latest = MaternalCheckup.objects.filter(
        user=user, pregnancy=pregnancy
    ).order_by("-requested_at").first()
    return latest is None or (
        latest.completed_at is None
        or latest.completed_at <= timezone.now() - timedelta(days=7)
    )
