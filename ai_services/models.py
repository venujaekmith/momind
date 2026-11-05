import uuid

from django.conf import settings
from django.db import models


class AgentRun(models.Model):
    """Persistent audit record for one Maternal Care Agent workflow."""

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pregnancy = models.ForeignKey(
        "dashboards.Pregnancy",
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triggered_agent_runs",
    )
    risk_assessment = models.ForeignKey(
        "dashboards.RiskAssessment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agent_runs",
    )
    objective = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    plan = models.JSONField(default=list, blank=True)
    memory_snapshot = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Maternal agent run {self.id} ({self.status})"


class AgentStep(models.Model):
    """One observable tool call or decision in an agent run."""

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="steps")
    sequence = models.PositiveIntegerField()
    tool_name = models.CharField(max_length=80)
    label = models.CharField(max_length=140)
    rationale = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "sequence"],
                name="unique_agent_step_sequence",
            )
        ]

    def __str__(self):
        return f"{self.run_id}: {self.sequence}. {self.tool_name}"
