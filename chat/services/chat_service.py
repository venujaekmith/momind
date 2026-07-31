from chat.services.groq_client import ask_groq
from chat.services.prompts import SYSTEM_PROMPT
from chat.services.context import build_context
from chat.services.safety import safety_check

def get_ai_reply(user, message):

    # 🚨 safety override
    if safety_check(message):
        return """
⚠️ This may require urgent medical attention.
Please contact a doctor or go to the nearest hospital immediately.
"""

    context = build_context(user, message)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""
Role: {context['role']}
Week: {context['week']}
Phase: {context['phase']}
Relevant date: {context['delivery_date']}

User message:
{context['message']}
        """}
    ]

    return ask_groq(messages)
