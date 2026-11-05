import json

from django.conf import settings
from django.utils import timezone

from accounts.models import MotherProfile
from dashboards.models import (
    Pregnancy,
)
from ai_services.services.maternal_agent import MaternalCareAgent

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None


class CommunityPersonalizationService:
    """Builds scoped maternal context and reviewable AI content for professionals."""

    def __init__(self):
        self.client = None
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if Groq and api_key:
            self.client = Groq(api_key=api_key)
        self.model = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")

    def build_context(self, mother, concern, triggered_by=None, viewer_role=None):
        pregnancy = (
            Pregnancy.objects.filter(mother=mother)
            .order_by("-is_active", "-created_at")
            .first()
        )
        if not pregnancy:
            return {
                "concern": concern,
                "pregnancy": None,
                "agent_review": "No pregnancy record is available for this mother.",
            }

        # Community AI uses the Maternal Care Agent in review-only mode. This
        # records the inspection and risk analysis without sending notifications
        # or creating safety alerts from a community page.
        agent_run = MaternalCareAgent().run(
            pregnancy,
            triggered_by=triggered_by,
            execute_actions=False,
        )
        context = self._scope_context(
            dict(agent_run.result.get("context", {})),
            viewer_role or getattr(triggered_by, "role", None),
        )
        context["concern"] = concern
        context["viewer_role"] = viewer_role or getattr(triggered_by, "role", None)
        context["agent_review"] = {
            "run_id": str(agent_run.id),
            "assessment_id": agent_run.result.get("assessment_id"),
            "risk_level": agent_run.result.get("risk_level"),
            "risk_score": agent_run.result.get("risk_score"),
            "risk_factors": (
                agent_run.risk_assessment.factors.get("rule_factors", [])
                if agent_run.risk_assessment
                else []
            ),
            # The stored explanation was generated from the complete clinical
            # record. Do not expose it cross-role; the report prompt explains
            # only the role-scoped evidence below.
            "explanation": "",
            "trend": agent_run.memory_snapshot.get("trend", "first_assessment"),
            "actions": agent_run.result.get("actions", []),
            "model_version": agent_run.result.get("model_version"),
            "human_review_required": True,
        }
        return json.loads(json.dumps(context, default=str))

    @staticmethod
    def _scope_context(context, viewer_role):
        """Keep only the clinical fields needed by the requesting professional."""
        common_fields = {
            "pregnancy_status",
            "pregnancy_week",
            "is_high_risk_history",
            "current_bp",
            "current_fetal_heart_rate",
            "recent_progress_summary",
            "recent_fetal_summary",
            "recent_abnormal_labs",
            "recent_labs",
            "lab_report_summary",
            "lab_report_analysis",
            "lab_report_count",
            "postpartum_week",
            "postpartum_delivery_type",
            "recent_postpartum_mood",
            "recent_postpartum_stress",
            "recent_kick_counts",
            "recent_water_intake_ml",
            "medications",
            "vaccinations",
            "symptom_signals",
            "clinical_milestones",
        }
        role_fields = {
            "DOCTOR": {
                "recent_moh_visits",
                "visit_notes",
                "recent_baby_development",
                "symptom_history",
            },
            "MIDWIFE": {
                "recent_midwife_visits",
                "symptom_history",
            },
        }
        allowed = common_fields | role_fields.get(viewer_role, set())
        scoped = {
            key: value
            for key, value in context.items()
            if key in allowed
        }
        if "symptom_history" in scoped:
            excluded_author = "midwife" if viewer_role == "DOCTOR" else "doctor"
            scoped["symptom_history"] = [
                entry for entry in scoped["symptom_history"]
                if entry.get("author") != excluded_author
            ]
        return scoped

    def generate_summary(self, context):
        fallback = self._full_risk_report(context)
        role_label = {
            "DOCTOR": "doctor",
            "MIDWIFE": "midwife",
        }.get(context.get("viewer_role"), "authorized professional")
        prompt = (
            f"Create a complete current AI risk assessment report for a {role_label}. "
            "Use only the supplied authorized data and only details relevant to the concern. "
            "The supplied context was reviewed by the Maternal Care Agent. Clearly highlight the "
            "risk level, score, warning factors, evidence reviewed, trend, permitted care actions, "
            "missing information, and the human-review boundary. Use these headings exactly: "
            "RISK STATUS, RISKS IDENTIFIED, EVIDENCE REVIEWED, TREND, CARE ACTIONS, "
            "MISSING OR UNVERIFIED INFORMATION, SAFETY NOTE. "
            "Do not diagnose, prescribe, invent missing data, or include unrelated personal information. "
            f"Concern: {context['concern']}\nContext: {json.dumps(context)}"
        )
        return self._complete(prompt, fallback)

    def personalize_response(self, context, professional_response):
        fallback = (
            f"{professional_response}\n\n"
            "Personalization note: Review this response against the mother's current status "
            "before sending. The original professional response and medical intent are preserved."
        )
        prompt = (
            "Adapt the professional's response for this mother using only the supplied role-scoped "
            "authorized context. The context was reviewed by the Maternal Care Agent. "
            "Preserve the original medical intent, do not add diagnosis or treatment, "
            "and do not make independent clinical decisions. Return only the adapted response "
            "for the professional to review. Do not mention AI or hidden data.\n"
            f"Professional response: {professional_response}\n"
            f"Authorized context: {json.dumps(context)}"
        )
        return self._complete(prompt, fallback)

    def _complete(self, prompt, fallback):
        if not self.client:
            return fallback
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a bounded maternal-health contextualization assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=900,
            )
            content = response.choices[0].message.content.strip()
            return content or fallback
        except Exception:
            return fallback

    @staticmethod
    def _full_risk_report(context):
        review = context.get("agent_review", {})
        level = (review.get("risk_level") or "unknown").upper()
        score = review.get("risk_score")
        factors = review.get("risk_factors") or ["No rule-based warning factors recorded."]
        explanation = review.get("explanation") or "No additional AI explanation is available."
        trend = str(review.get("trend", "first_assessment")).replace("_", " ")
        actions = review.get("actions") or []
        action_lines = []
        for action in actions:
            label = str(action.get("tool", "care action")).replace("_", " ").title()
            detail = action.get("reason") or action.get("status", "recorded")
            action_lines.append(f"- {label}: {detail}")
        if not action_lines:
            action_lines.append("- No care-coordination action was recorded.")

        pregnancy = context.get("pregnancy")
        if pregnancy is None and context.get("pregnancy_status"):
            pregnancy = {
                "status": context["pregnancy_status"],
                "is_active": context["pregnancy_status"] == "ongoing",
                "week": context.get("pregnancy_week"),
                "is_high_risk": context.get("is_high_risk_history", False),
            }
        lines = [
            "RISK STATUS",
            f"- Classification: {level}; score: {score if score is not None else 'not available'}/100.",
            f"- Current concern: {context['concern']}",
            "",
            "RISKS IDENTIFIED",
            *[f"- {factor}" for factor in factors],
            f"- Agent explanation: {explanation}",
            "",
            "EVIDENCE REVIEWED",
        ]
        if pregnancy:
            state = "active pregnancy" if pregnancy["is_active"] else pregnancy["status"]
            lines.append(f"- Pregnancy status: {state}; week: {pregnancy['week'] or 'not recorded'}.")
            lines.append(f"- High-risk history flag: {'yes' if pregnancy['is_high_risk'] else 'no'}.")
        else:
            lines.append("- Pregnancy status: no pregnancy record is available.")
        progress = context.get("recent_progress") or context.get("recent_progress_summary", [])
        if progress:
            latest = progress[0]
            if isinstance(latest, str):
                latest_text = latest
            else:
                latest_text = latest.get("symptoms") or latest.get("notes") or "none recorded"
            lines.append(f"- Latest recorded symptoms/notes: {latest_text}.")
        else:
            lines.append("- Recent symptoms and trends: no recent progress record is available.")
        if context.get("recent_abnormal_labs"):
            lines.append(f"- Abnormal laboratory results: {', '.join(context['recent_abnormal_labs'])}.")
        elif context.get("recent_labs"):
            lines.append(f"- Recent laboratory tests: {', '.join(context['recent_labs'])}.")
        else:
            lines.append("- Laboratory results: no recent results recorded.")
        lines.extend([
            "",
            "TREND",
            f"- Compared with prior agent assessments: {trend}.",
            "",
            "CARE ACTIONS",
            *action_lines,
            "",
            "MISSING OR UNVERIFIED INFORMATION",
            "- Verify symptoms, measurements, laboratory results, and care-team instructions before acting.",
            "",
            "SAFETY NOTE",
            "- Decision support only. This report does not diagnose or prescribe; a qualified clinician must review it.",
        ])
        return "\n".join(lines)
