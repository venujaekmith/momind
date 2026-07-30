from groq import Groq
from django.conf import settings

def ask_groq(messages):
    if not settings.GROQ_API_KEY:
        return (
            "I’m unable to reach the AI service right now. For urgent symptoms, "
            "please contact your maternity care team or local emergency services."
        )
    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",  # strong model for reasoning
        messages=messages,
        temperature=0.4
    )

    return response.choices[0].message.content
