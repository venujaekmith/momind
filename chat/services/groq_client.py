from groq import Groq
from django.conf import settings

client = Groq(api_key=settings.GROQ_API_KEY)

def ask_groq(messages):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",  # strong model for reasoning
        messages=messages,
        temperature=0.4
    )

    return response.choices[0].message.content