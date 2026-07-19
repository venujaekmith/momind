from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import render
from .models import ChatSession, ChatMessage
from .services.chat_service import get_ai_reply
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

#### use this rate limit later

def rate_limit(user):
    key = f"chat_{user.id}"
    count = cache.get(key, 0)

    if count > 30:  # per minute
        return False

    cache.set(key, count + 1, timeout=60)
    return True


@csrf_exempt
def start_session(request):
    if request.method == "POST":
        user = request.user

        session, created = ChatSession.objects.get_or_create(user=user)

        return JsonResponse({
            "session_id": session.id,
            "created": created
        })
    


@csrf_exempt
def send_message(request):
    if request.method == "POST":

        data = json.loads(request.body)
        message = data.get("message")
        session_id = data.get("session_id")

        user = request.user

        # Get session
        session = ChatSession.objects.get(id=session_id, user=user)

        # Save user message
        ChatMessage.objects.create(
            session=session,
            sender="user",
            message=message
        )

        # 🤖 Get AI response (Groq)
        ai_reply = get_ai_reply(user, message)

        # Save AI message
        ChatMessage.objects.create(
            session=session,
            sender="ai",
            message=ai_reply
        )

        return JsonResponse({
            "reply": ai_reply,
            "session_id": session.id
        })
    
def get_messages(request, session_id):
    user = request.user

    session = ChatSession.objects.get(id=session_id, user=user)

    messages = ChatMessage.objects.filter(session=session).order_by("timestamp")

    data = [
        {
            "sender": m.sender,
            "message": m.message,
            "time": m.timestamp
        }
        for m in messages
    ]

    return JsonResponse({
        "messages": data
    })

@login_required
def chatbot(request):
    return render(request,"chatbot.html")