from groq import Groq
from django.conf import settings


def _offline_guidance():
    return (
        "I can still help with general maternal-care guidance, but the live AI model "
        "is not configured right now. Tell me whether your question is about pregnancy, "
        "postpartum recovery, appointments, nutrition, or using MoMind. For symptoms or "
        "medical decisions, contact your maternity care team; use emergency services for "
        "severe or rapidly worsening symptoms."
    )


def ask_groq(messages):
    if not settings.GROQ_API_KEY:
        return _offline_guidance()
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.4,
            timeout=20,
        )
        content = response.choices[0].message.content
        return content.strip() if content else _offline_guidance()
    except Exception:
        return _offline_guidance()
