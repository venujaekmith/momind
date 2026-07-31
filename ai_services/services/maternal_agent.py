"""Auditable, tool-using Maternal Care Agent.

The agent is deliberately bounded: it may inspect records, analyze risk, remember
prior assessments, notify the linked care team, and create an in-app safety alert.
It cannot diagnose, prescribe, contact external services, or edit clinical data.
"""

import json

from django.utils import timezone

from ai_services.models import AgentRun, AgentStep
from dashboards.models import LabTest, RiskAssessment

from .risk_assessment import AdvancedPregnancyRiskService


def _json_safe(value):
    return json.loads(json.dumps(value, default=str))


class MaternalCareAgent:
    OBJECTIVE = (
        "Review the mother's longitudinal maternal-health record, assess current "
        "risk, explain the evidence, and take permitted care-coordination actions."
    )

    def __init__(self):
        self.risk_service = AdvancedPregnancyRiskService()

    def run(self, pregnancy, triggered_by=None):
        agent_run = AgentRun.objects.create(
            pregnancy=pregnancy,
            triggered_by=triggered_by,
            objective=self.OBJECTIVE,
            status="planning",
        )

        try:
            plan = self._build_plan(pregnancy)
            agent_run.plan = plan
            agent_run.status = "running"
            agent_run.save(update_fields=["plan", "status"])

            memory = self._execute_step(
                agent_run,
                "retrieve_memory",
                "Recall previous assessments",
                "Past results provide longitudinal memory and prevent a one-shot decision.",
                {},
                lambda: self._retrieve_memory(pregnancy),
            )
            agent_run.memory_snapshot = _json_safe(memory)
            agent_run.save(update_fields=["memory_snapshot"])

            record = self._execute_step(
                agent_run,
                "inspect_health_record",
                "Inspect maternal health record",
                "The agent needs current pregnancy, fetal, laboratory, and postpartum evidence.",
                {"pregnancy_id": pregnancy.id},
                lambda: self._inspect_record(pregnancy),
                presenter=self._present_record,
            )

            assessment = self._execute_step(
                agent_run,
                "calculate_hybrid_risk",
                "Calculate and explain risk",
                "Combine the available model, deterministic safety rules, and an LLM explanation.",
                {
                    "model_version": self.risk_service.model_version,
                    "feature_count": len(record["features"]),
                },
                lambda: self.risk_service.calculate_risk(
                    pregnancy,
                    trigger_actions=False,
                    prepared_features=record["features"],
                    prepared_context=record["context"],
                ),
                presenter=self._present_assessment,
            )
            agent_run.risk_assessment = assessment
            agent_run.save(update_fields=["risk_assessment"])

            decision = self._execute_step(
                agent_run,
                "decide_care_actions",
                "Decide permitted care actions",
                "Use risk severity, evidence, and prior memory to select bounded follow-up actions.",
                {
                    "risk_level": assessment.risk_level,
                    "previous_assessments": memory["assessment_count"],
                },
                lambda: self._decide_actions(assessment, memory),
            )

            action_results = self._execute_step(
                agent_run,
                "execute_care_actions",
                "Execute care-coordination actions",
                "Notify the linked care team and create an in-app alert only when policy permits.",
                {"actions": decision["actions"]},
                lambda: self._execute_actions(
                    pregnancy,
                    assessment,
                    record["context"],
                    decision,
                ),
                presenter=self._present_actions,
            )

            factors = dict(assessment.factors or {})
            factors["agent"] = {
                "run_id": str(agent_run.id),
                "objective": self.OBJECTIVE,
                "decision": decision,
                "actions": action_results,
            }
            assessment.factors = _json_safe(factors)
            assessment.save(update_fields=["factors"])

            result = {
                "agent_run_id": str(agent_run.id),
                "assessment_id": assessment.id,
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level,
                "model_version": assessment.prediction_model_version,
                "reasoning": decision["rationale"],
                "actions": action_results,
                "human_review_required": decision["human_review_required"],
                "safety_boundary": (
                    "Decision support only. The agent does not diagnose, prescribe, "
                    "or contact emergency services."
                ),
            }
            agent_run.result = _json_safe(result)
            agent_run.status = "completed"
            agent_run.completed_at = timezone.now()
            agent_run.save(update_fields=["result", "status", "completed_at"])
            return agent_run
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.error = str(exc)[:2000]
            agent_run.completed_at = timezone.now()
            agent_run.save(update_fields=["status", "error", "completed_at"])
            raise

    def _build_plan(self, pregnancy):
        plan = [
            {
                "sequence": 1,
                "tool": "retrieve_memory",
                "reason": "Compare the present record with prior agent assessments.",
            },
            {
                "sequence": 2,
                "tool": "inspect_health_record",
                "reason": "Gather current maternal, fetal, lab, and postpartum context.",
            },
        ]
        if LabTest.objects.filter(pregnancy=pregnancy).exists():
            plan[-1]["reason"] += " Analyze available lab reports."
        plan.extend([
            {
                "sequence": 3,
                "tool": "calculate_hybrid_risk",
                "reason": "Combine predictive scoring, safety rules, and explanation.",
            },
            {
                "sequence": 4,
                "tool": "decide_care_actions",
                "reason": "Choose actions allowed by the medical safety policy.",
            },
            {
                "sequence": 5,
                "tool": "execute_care_actions",
                "reason": "Persist outcomes, notify care participants, and escalate in-app when needed.",
            },
        ])
        return plan

    def _execute_step(
        self,
        agent_run,
        tool_name,
        label,
        rationale,
        input_data,
        operation,
        presenter=None,
    ):
        sequence = agent_run.steps.count() + 1
        step = AgentStep.objects.create(
            run=agent_run,
            sequence=sequence,
            tool_name=tool_name,
            label=label,
            rationale=rationale,
            input_data=_json_safe(input_data),
        )
        try:
            value = operation()
            public_value = presenter(value) if presenter else value
            step.output_data = _json_safe(public_value)
            step.status = "completed"
            step.completed_at = timezone.now()
            step.save(update_fields=["output_data", "status", "completed_at"])
            return value
        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)[:2000]
            step.completed_at = timezone.now()
            step.save(update_fields=["status", "error", "completed_at"])
            raise

    def _retrieve_memory(self, pregnancy):
        previous = list(
            RiskAssessment.objects.filter(pregnancy=pregnancy)
            .order_by("-created_at")[:5]
        )
        history = [
            {
                "assessment_id": item.id,
                "score": item.risk_score,
                "level": item.risk_level,
                "created_at": item.created_at.isoformat(),
            }
            for item in previous
        ]
        trend = "first_assessment"
        if len(history) >= 2:
            if history[0]["score"] < history[1]["score"]:
                trend = "improving"
            elif history[0]["score"] > history[1]["score"]:
                trend = "worsening"
            else:
                trend = "stable"
        return {"assessment_count": len(history), "recent": history, "trend": trend}

    def _inspect_record(self, pregnancy):
        features = self.risk_service._extract_features(pregnancy)
        context = self.risk_service._gather_context(pregnancy)
        context["summary_text"] = self.risk_service._format_context_for_prompt(context)
        return {"features": features, "context": context}

    def _present_record(self, record):
        context = record["context"]
        return {
            "feature_count": len(record["features"]),
            "pregnancy_week": context.get("pregnancy_week"),
            "progress_records_reviewed": len(context.get("recent_progress_summary", [])),
            "fetal_records_reviewed": len(context.get("recent_fetal_summary", [])),
            "lab_reports_reviewed": context.get("lab_report_count", 0),
            "abnormal_labs": context.get("recent_abnormal_labs", []),
            "postpartum_context_available": context.get("postpartum_week") is not None,
            "care_team_members": len(context.get("family_members", [])),
        }

    def _present_assessment(self, assessment):
        return {
            "assessment_id": assessment.id,
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level,
            "risk_factors": assessment.factors.get("rule_factors", []),
            "model_version": assessment.prediction_model_version,
            "explanation_generated": bool(assessment.factors.get("llm_explanation")),
        }

    def _present_actions(self, actions):
        notification_action = next(
            (item for item in actions if item.get("tool") == "notify_care_team"),
            {},
        )
        alert_action = next(
            (item for item in actions if item.get("tool") == "create_in_app_safety_alert"),
            {},
        )
        return {
            "actions_completed": len(actions),
            "recipient_count": notification_action.get("recipient_count", 0),
            "alert_id": alert_action.get("alert_id"),
            "alert_created": alert_action.get("created", False),
            "tools": [item.get("tool") for item in actions],
        }

    def _decide_actions(self, assessment, memory):
        level = assessment.risk_level
        factors = assessment.factors.get("rule_factors", [])
        actions = ["notify_care_team"]
        priority = "routine"
        human_review_required = False

        if level == "medium":
            priority = "prompt_review"
            human_review_required = True
        elif level in {"high", "critical"}:
            priority = "urgent_review"
            human_review_required = True
            actions.append("create_in_app_safety_alert")

        trend = memory.get("trend", "first_assessment")
        rationale = (
            f"The hybrid assessment classified this record as {level.upper()} risk"
            f" with a score of {assessment.risk_score}/100."
        )
        if factors:
            rationale += f" Material factors: {', '.join(factors)}."
        if trend != "first_assessment":
            rationale += f" Recent stored assessments indicate a {trend} trend."
        rationale += (
            " The safety policy requires care-team notification; high and critical "
            "levels additionally require an in-app alert and human clinical review."
        )
        return {
            "priority": priority,
            "actions": actions,
            "human_review_required": human_review_required,
            "rationale": rationale,
        }

    def _execute_actions(self, pregnancy, assessment, context, decision):
        results = []
        if "notify_care_team" in decision["actions"]:
            notification_ids = self.risk_service.notify_care_team(
                pregnancy,
                assessment,
                context,
            )
            results.append({
                "tool": "notify_care_team",
                "status": "completed",
                "notification_ids": notification_ids,
                "recipient_count": len(notification_ids),
            })

        if "create_in_app_safety_alert" in decision["actions"]:
            alert = self.risk_service.create_safety_alert(
                pregnancy,
                assessment.risk_level,
                assessment.factors.get("llm_explanation", ""),
            )
            results.append({
                "tool": "create_in_app_safety_alert",
                "status": "completed",
                **(alert or {"created": False, "reason": "Policy threshold not met"}),
            })
        return results


def serialize_agent_run(agent_run, include_steps=True):
    payload = {
        "id": str(agent_run.id),
        "status": agent_run.status,
        "objective": agent_run.objective,
        "plan": agent_run.plan,
        "memory": agent_run.memory_snapshot,
        "result": agent_run.result,
        "error": agent_run.error,
        "created_at": agent_run.created_at.isoformat(),
        "completed_at": agent_run.completed_at.isoformat() if agent_run.completed_at else None,
    }
    if include_steps:
        payload["steps"] = [
            {
                "sequence": step.sequence,
                "tool": step.tool_name,
                "label": step.label,
                "rationale": step.rationale,
                "status": step.status,
                "input": step.input_data,
                "output": step.output_data,
                "error": step.error,
            }
            for step in agent_run.steps.all()
        ]
    return payload
