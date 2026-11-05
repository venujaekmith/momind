from django.http import HttpResponseForbidden, JsonResponse
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import (
    ChatSession,
    ChatMessage,
    CheckupMessage,
    CheckupQuestion,
    CheckupSession,
    MaternalCheckIn,
    MaternalCheckup,
    ProfessionalChatMessage,
    ProfessionalChatRequest,
)
from accounts.models import Family, Role
from dashboards.models import Link_notification, Notification, Pregnancy
from ai_services.services.maternal_agent import MaternalCareAgent
from .services.chat_service import (
    CHECKUP_QUESTION_LIMIT,
    checkup_question_options,
    get_ai_reply,
    next_check_in,
)
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

#### use this rate limit later

def rate_limit(user):
    key = f"chat_{user.id}"
    count = cache.get(key, 0)

    if count >= 30:  # per minute
        return False

    cache.set(key, count + 1, timeout=60)
    return True


PARENT_ROLES = {Role.MOTHER, Role.FATHER}
PROFESSIONAL_ROLES = {Role.DOCTOR, Role.MIDWIFE}


def _professional_chat_access(user):
    return user.role in PARENT_ROLES or user.role in PROFESSIONAL_ROLES


def _professional_name(user):
    return user.get_full_name() or user.username


def _family_chat_pairs(user):
    """Return parent/professional pairs from the user's existing family links."""
    if user.role in PARENT_ROLES:
        families = Family.objects.filter(
            Q(mother__user=user) | Q(father__user=user)
        ).select_related(
            "doctor__user", "midwife__user"
        )
        pairs = []
        for family in families:
            for profile in (family.doctor, family.midwife):
                if profile:
                    pairs.append((user, profile.user))
        return pairs

    if user.role in PROFESSIONAL_ROLES:
        family_filter = Q(doctor__user=user) | Q(midwife__user=user)
        families = Family.objects.filter(family_filter).select_related(
            "mother__user", "father__user"
        )
        pairs = []
        for family in families:
            for profile in (family.mother, family.father):
                if profile:
                    pairs.append((profile.user, user))
        return pairs

    return []


def _share_family(parent, professional):
    if parent.role not in PARENT_ROLES or professional.role not in PROFESSIONAL_ROLES:
        return False
    return Family.objects.filter(
        Q(mother__user=parent) | Q(father__user=parent),
        Q(doctor__user=professional) | Q(midwife__user=professional),
    ).exists()


def _get_or_create_family_chat(parent, professional):
    chat_request, _ = ProfessionalChatRequest.objects.get_or_create(
        requester=parent,
        professional=professional,
        defaults={
            "status": "accepted",
            "responded_at": timezone.now(),
        },
    )
    if chat_request.status != "accepted":
        chat_request.status = "accepted"
        chat_request.responded_at = timezone.now()
        chat_request.save(update_fields=["status", "responded_at"])
    return chat_request


def _notification_context(user):
    notifications = Notification.objects.filter(
        user=user, is_read=False
    ).order_by("-created_at")[:5]
    pending_link_requests = Link_notification.objects.filter(
        link=user, accepted=False
    ).order_by("-id")
    return {
        "notifications": notifications,
        "pending_link_requests": pending_link_requests,
        "unread_count": notifications.count() + pending_link_requests.count(),
        "care_team_unread_count": Notification.objects.filter(
            user=user,
            is_read=False,
            title="New care team chat message",
        ).count(),
    }


def _chat_unread_count(user, chat_request):
    other_user = (
        chat_request.professional
        if user == chat_request.requester
        else chat_request.requester
    )
    other_name = other_user.get_full_name() or other_user.username
    return Notification.objects.filter(
        user=user,
        is_read=False,
        title="New care team chat message",
        message=f"{other_name} sent you a new message.",
    ).count()


@login_required
def professional_chat(request):
    if not _professional_chat_access(request.user):
        return HttpResponseForbidden("Only parents, doctors, and midwives can use professional chat.")

    conversations = []
    seen = set()
    for parent, professional in _family_chat_pairs(request.user):
        pair = (parent.id, professional.id)
        if pair not in seen:
            chat_request = _get_or_create_family_chat(parent, professional)
            chat_request.unread_count = _chat_unread_count(
                request.user, chat_request
            )
            conversations.append(chat_request)
            seen.add(pair)

    context = {
        "conversations": conversations,
        "professional_name": _professional_name,
    }
    context.update(_notification_context(request.user))
    return render(request, "professional_chat.html", context)


@login_required
def professional_conversation(request, request_id):
    if not _professional_chat_access(request.user):
        return HttpResponseForbidden("Only parents, doctors, and midwives can use professional chat.")

    chat_request = get_object_or_404(
        ProfessionalChatRequest.objects.select_related("requester", "professional"),
        id=request_id,
        status="accepted",
    )
    if request.user == chat_request.requester:
        parent, professional = request.user, chat_request.professional
    elif request.user == chat_request.professional:
        parent, professional = chat_request.requester, request.user
    else:
        return HttpResponseForbidden("You are not a participant in this conversation.")
    if not _share_family(parent, professional):
        return HttpResponseForbidden("You are not a participant in this conversation.")
    Notification.objects.filter(
        user=request.user,
        is_read=False,
        title="New care team chat message",
    ).update(is_read=True)

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        if not message:
            messages.error(request, "Message cannot be empty.")
        elif len(message) > 4000:
            messages.error(request, "Messages must be 4,000 characters or fewer.")
        else:
            ProfessionalChatMessage.objects.create(
                request=chat_request,
                sender=request.user,
                message=message,
            )
            Notification.objects.create(
                user=(
                    chat_request.professional
                    if request.user == chat_request.requester
                    else chat_request.requester
                ),
                title="New care team chat message",
                message=(
                    f"{request.user.get_full_name() or request.user.username} "
                    "sent you a new message."
                ),
            )
            return redirect("chat:professional_conversation", request_id=request_id)

    context = {
        "chat_request": chat_request,
        "chat_messages": chat_request.messages.select_related("sender"),
    }
    context.update(_notification_context(request.user))
    return render(request, "professional_conversation.html", context)


@login_required
@require_POST
def start_session(request):
    user = request.user
    session = ChatSession.objects.filter(user=user).order_by("-created_at").first()
    created = session is None
    if created:
        session = ChatSession.objects.create(user=user)
    return JsonResponse({
        "session_id": session.id,
        "created": created,
    })
    


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


def _active_pregnancy(user):
    mother = getattr(user, "user_mother", None)
    return (
        mother.pregnancies.filter(is_active=True).order_by("-created_at").first()
        if mother else None
    )


def _checkup_question(checkup):
    return checkup.checkins.filter(answered_at__isnull=True).order_by("asked_at").first()


@login_required
@require_POST
def start_checkup_session(request):
    if request.user.role != Role.MOTHER:
        return HttpResponseForbidden("Only mothers can use Checkup Bot.")
    pregnancy = _active_pregnancy(request.user)
    # An explicit button press always starts an independent checkup.
    check_in = next_check_in(
        request.user,
        pregnancy,
        force=True,
        trigger_type="mother",
    )
    checkup = check_in.checkup
    total_questions = len(checkup_question_options(checkup))
    session = CheckupSession.objects.filter(
        user=request.user, checkup=checkup
    ).order_by("-created_at").first()
    created = session is None
    if created:
        session = CheckupSession.objects.create(user=request.user, checkup=checkup)
    return JsonResponse({
        "session_id": session.id,
        "created": created,
        "checkup_id": checkup.id,
        "question": check_in.question,
        "question_id": check_in.id,
        "answered_questions": 0,
        "total_questions": total_questions,
        "remaining_questions": max(total_questions - 1, 0),
    })


@login_required
@require_POST
def send_checkup_message(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)
    message = str(data.get("message", "")).strip()
    if not message:
        return JsonResponse({"error": "Answer cannot be empty."}, status=400)
    session = get_object_or_404(
        CheckupSession, id=data.get("session_id"), user=request.user
    )
    check_in = get_object_or_404(
        MaternalCheckIn,
        id=data.get("question_id"),
        checkup=session.checkup,
        user=request.user,
        answered_at__isnull=True,
    )
    check_in.answer = message
    check_in.answered_at = timezone.now()
    check_in.save(update_fields=["answer", "answered_at"])
    CheckupMessage.objects.create(session=session, sender="user", message=message)
    answered_keys = set(session.checkup.checkins.values_list("question_key", flat=True))
    next_question = next(
        (item for item in checkup_question_options(session.checkup)
         if item[0] not in answered_keys),
        None,
    )
    if next_question:
        next_check_in_record = MaternalCheckIn.objects.create(
            checkup=session.checkup,
            user=request.user,
            pregnancy=check_in.pregnancy,
            question_key=next_question[0],
            question=next_question[1],
        )
        session.checkup.completed_at = None
        session.checkup.save(update_fields=["completed_at"])
    else:
        next_check_in_record = None
        session.checkup.completed_at = timezone.now()
        session.checkup.save(update_fields=["completed_at"])
        if check_in.pregnancy:
            session.checkup.agent_run = MaternalCareAgent().run(
                check_in.pregnancy,
                triggered_by=request.user,
                execute_actions=False,
            )
            session.checkup.save(update_fields=["agent_run"])
    answered_questions = session.checkup.checkins.filter(
        answered_at__isnull=False
    ).count()
    total_questions = len(checkup_question_options(session.checkup))
    return JsonResponse({
        "session_id": session.id,
        "question": next_check_in_record.question if next_check_in_record else None,
        "question_id": next_check_in_record.id if next_check_in_record else None,
        "complete": next_check_in_record is None,
        "answered_questions": answered_questions,
        "total_questions": total_questions,
        "remaining_questions": max(total_questions - answered_questions, 0),
    })


@login_required
@require_POST
def trigger_checkup(request, pregnancy_id):
    pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
    mother = pregnancy.mother
    family = Family.objects.filter(mother=mother, pregnancy=pregnancy).select_related(
        "father__user", "doctor__user", "midwife__user"
    ).first()
    allowed = request.user == mother.user
    trigger_type = "mother"
    if family:
        role_users = {
            "partner": getattr(getattr(family.father, "user", None), "id", None),
            "doctor": getattr(getattr(family.doctor, "user", None), "id", None),
            "midwife": getattr(getattr(family.midwife, "user", None), "id", None),
        }
        for role, user_id in role_users.items():
            if user_id == request.user.id:
                allowed = True
                trigger_type = role
                break
    if not allowed:
        return HttpResponseForbidden("Only the mother or her linked care team can trigger a checkup.")
    check_in = next_check_in(
        mother.user,
        pregnancy,
        force=True,
        triggered_by=request.user,
        trigger_type=trigger_type,
    )
    if request.user != mother.user:
        Notification.objects.create(
            user=mother.user,
            title="Checkup Bot checkup requested",
            message="Your care team asked you to complete a maternal checkup.",
        )
    return JsonResponse({"checkup_id": check_in.checkup_id, "question": check_in.question})


@login_required
@require_POST
def add_checkup_question(request, pregnancy_id):
    pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
    if request.user.role not in {Role.DOCTOR, Role.MIDWIFE}:
        return HttpResponseForbidden("Only doctors and midwives can add checkup questions.")
    family = Family.objects.filter(
        mother=pregnancy.mother,
        pregnancy=pregnancy,
    ).select_related("doctor__user", "midwife__user").first()
    linked_users = {
        getattr(getattr(family, "doctor", None), "user_id", None),
        getattr(getattr(family, "midwife", None), "user_id", None),
    } if family else set()
    if request.user.id not in linked_users:
        return HttpResponseForbidden("Only the linked doctor or midwife can add questions.")
    question = str(request.POST.get("question", "")).strip()
    if not question or len(question) > 2000:
        return JsonResponse({"error": "Enter a question up to 2000 characters."}, status=400)
    created = CheckupQuestion.objects.create(
        pregnancy=pregnancy,
        created_by=request.user,
        question=question,
    )
    return JsonResponse({"id": created.id, "question": created.question}, status=201)

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


@login_required
def checkup_bot(request):
    return render(request, "checkup_bot.html")


@login_required
def checkup_summary(request, pregnancy_id):
    pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
    mother = pregnancy.mother
    family = Family.objects.filter(mother=mother, pregnancy=pregnancy).first()
    allowed = request.user == mother.user
    if family:
        allowed = allowed or any([
            getattr(getattr(family.father, "user", None), "id", None) == request.user.id,
            getattr(getattr(family.doctor, "user", None), "id", None) == request.user.id,
            getattr(getattr(family.midwife, "user", None), "id", None) == request.user.id,
        ])
    if not allowed:
        return HttpResponseForbidden("Only the mother or linked care team can view this summary.")
    checkup = MaternalCheckup.objects.filter(
        user=mother.user,
        pregnancy=pregnancy,
        completed_at__isnull=False,
    ).select_related("agent_run").order_by("-completed_at").first()
    return render(request, "checkup_summary.html", {
        "pregnancy": pregnancy,
        "mother": mother,
        "checkup": checkup,
        "agent_run": checkup.agent_run if checkup else None,
    })
