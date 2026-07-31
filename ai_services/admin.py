from django.contrib import admin

from .models import AgentRun, AgentStep


class AgentStepInline(admin.TabularInline):
    model = AgentStep
    extra = 0
    can_delete = False
    readonly_fields = (
        "sequence",
        "tool_name",
        "label",
        "rationale",
        "status",
        "input_data",
        "output_data",
        "error",
        "started_at",
        "completed_at",
    )


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "pregnancy", "status", "triggered_by", "created_at", "completed_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "pregnancy__mother__user__username", "objective")
    readonly_fields = (
        "id",
        "pregnancy",
        "triggered_by",
        "risk_assessment",
        "objective",
        "status",
        "plan",
        "memory_snapshot",
        "result",
        "error",
        "created_at",
        "completed_at",
    )
    inlines = [AgentStepInline]
