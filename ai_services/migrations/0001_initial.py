# Generated for the persistent Maternal Care Agent runtime.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_initial"),
        ("dashboards", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("objective", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("planning", "Planning"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="planning", max_length=20)),
                ("plan", models.JSONField(blank=True, default=list)),
                ("memory_snapshot", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("pregnancy", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agent_runs", to="dashboards.pregnancy")),
                ("risk_assessment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agent_runs", to="dashboards.riskassessment")),
                ("triggered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggered_agent_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AgentStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("tool_name", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=140)),
                ("rationale", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="running", max_length=20)),
                ("input_data", models.JSONField(blank=True, default=dict)),
                ("output_data", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="ai_services.agentrun")),
            ],
            options={"ordering": ["sequence"]},
        ),
        migrations.AddConstraint(
            model_name="agentstep",
            constraint=models.UniqueConstraint(fields=("run", "sequence"), name="unique_agent_step_sequence"),
        ),
    ]
