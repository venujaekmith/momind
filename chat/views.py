from django.http import JsonResponse
import json
from django.shortcuts import get_object_or_404, render
from .models import ChatSession, ChatMessage
from .services.chat_service import get_ai_reply
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.views.decorators.http import require_GET, require_POST

#### use this rate limit later

def rate_limit(user):
    key = f"chat_{user.id}"
    count = cache.get(key, 0)

    if count >= 30:  # per minute
        return False

    cache.set(key, count + 1, timeout=60)
    return True


@login_required
@require_POST
def start_session(request):
    user = request.user
    session = ChatSession.objects.filter(user=user).order_by("-created_at").first()
    created = session is None
    if created:
        session = ChatSession.objects.create(user=user)
    return JsonResponse({"session_id": session.id, "created": created})
    


@login_required
@require_POST
def send_message(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)
    message = str(data.get("message", "")).strip()
    session_id = data.get("session_id")
    if not message:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)
    if len(message) > 2000:
        return JsonResponse({"error": "Message is too long."}, status=400)
    if not rate_limit(request.user):
        return JsonResponse({"error": "Too many messages. Please wait a minute."}, status=429)

    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    ChatMessage.objects.create(session=session, sender="user", message=message)
    try:
        ai_reply = get_ai_reply(request.user, message)
    except Exception:
        ai_reply = (
            "I’m unable to reach the AI service right now. For urgent symptoms, "
            "please contact your maternity care team or local emergency services."
        )
    ChatMessage.objects.create(session=session, sender="ai", message=ai_reply)
    return JsonResponse({"reply": ai_reply, "session_id": session.id})

@login_required
@require_GET
def get_messages(request, session_id):
    user = request.user

    session = get_object_or_404(ChatSession, id=session_id, user=user)

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
