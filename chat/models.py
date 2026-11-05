from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="chat_session",on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    sender = models.CharField(max_length=10)  # user / ai
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)


class CheckupSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkup_sessions")
    checkup = models.ForeignKey("chat.MaternalCheckup", on_delete=models.CASCADE, related_name="sessions")
    created_at = models.DateTimeField(auto_now_add=True)


class CheckupMessage(models.Model):
    session = models.ForeignKey(CheckupSession, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=10)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)


class ProfessionalChatRequest(models.Model):
    """A conversation between family members and a linked professional."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="professional_chat_requests_sent",
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="professional_chat_requests_received",
    )
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "professional"],
                condition=models.Q(status__in=["pending", "accepted"]),
                name="unique_active_professional_chat_request",
            )
        ]


class ProfessionalChatMessage(models.Model):
    request = models.ForeignKey(
        ProfessionalChatRequest,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class MaternalCheckup(models.Model):
    """A weekly or care-team-triggered structured maternal checkup."""

    TRIGGER_CHOICES = [
        ("weekly", "Weekly checkup"),
        ("mother", "Mother requested"),
        ("doctor", "Doctor requested"),
        ("midwife", "Midwife requested"),
        ("partner", "Partner requested"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="maternal_checkups")
    pregnancy = models.ForeignKey("dashboards.Pregnancy", null=True, blank=True, on_delete=models.SET_NULL, related_name="maternal_checkups")
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="triggered_maternal_checkups")
    agent_run = models.ForeignKey(
        "ai_services.AgentRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checkups",
    )
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]


class CheckupQuestion(models.Model):
    """A care-team question included in every future checkup for a pregnancy."""

    pregnancy = models.ForeignKey(
        "dashboards.Pregnancy",
        on_delete=models.CASCADE,
        related_name="checkup_questions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_checkup_questions",
    )
    question = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class MaternalCheckIn(models.Model):
    """A periodic, structured wellbeing question answered by a mother."""

    QUESTIONS = [
        ("vomiting", "Since your last check-in, have you had repeated vomiting or trouble keeping fluids down?"),
        ("fainting", "Since your last check-in, have you fainted, blacked out, or felt close to fainting?"),
        ("pain_bleeding", "Since your last check-in, have you had new severe pain, bleeding, or a severe headache?"),
        ("wellbeing", "How have you been coping emotionally and physically since your last check-in?"),
        ("daily_health", "How have your sleep, appetite, energy, and ability to manage daily activities been recently?"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="maternal_checkins",
    )
    pregnancy = models.ForeignKey(
        "dashboards.Pregnancy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maternal_checkins",
    )
    checkup = models.ForeignKey(
        MaternalCheckup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    question_key = models.CharField(max_length=40)
    question = models.TextField()
    answer = models.TextField(blank=True)
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-asked_at"]