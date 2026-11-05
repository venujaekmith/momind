# ai_service/views.py
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from dashboards.models import Pregnancy, RiskAssessment, LabTest
from accounts.models import Family
from .models import AgentRun
from .services.maternal_agent import MaternalCareAgent, serialize_agent_run
from .services.risk_assessment import AdvancedPregnancyRiskService
from .services.postpartum_ai import PostpartumAIService
from .services.lab_report_analysis import LabReportAnalysisService


FEATURE_PRESENTATION = {
    "age": ("Mother's age", "years"),
    "gestational_week": ("Pregnancy week", "weeks"),
    "bmi": ("BMI", ""),
    "bp_systolic": ("Systolic blood pressure", "mmHg"),
    "bp_diastolic": ("Diastolic blood pressure", "mmHg"),
    "fetal_heart_rate": ("Fetal heart rate", "bpm"),
    "weight_gain": ("Recorded weight change", "kg"),
    "abnormal_lab_count": ("Abnormal lab results", ""),
    "previous_pregnancies": ("Previous pregnancies", ""),
    "postpartum_week": ("Postpartum week", "weeks"),
    "recent_postpartum_mood": ("Recent mood score", "/10"),
    "recent_postpartum_stress": ("Recent stress score", "/10"),
}


def _risk_page_context(assessment, agent_run, trend):
    """Turn stored assessment data into safe, readable presentation data."""
    factors = assessment.factors or {}
    level = (assessment.risk_level or "low").lower()
    severity = {
        "low": {
            "title": "Routine monitoring",
            "summary": "No major warning signals were identified in the information currently recorded.",
            "icon": "fa-circle-check",
        },
        "medium": {
            "title": "Prompt care-team review",
            "summary": "Some findings need a timely review by a midwife or doctor.",
            "icon": "fa-clock",
        },
        "high": {
            "title": "Urgent clinical review",
            "summary": "Important warning signals were found. A qualified clinician should review this assessment urgently.",
            "icon": "fa-triangle-exclamation",
        },
        "critical": {
            "title": "Immediate clinical review",
            "summary": "Serious warning signals were found. Contact the maternity care team immediately.",
            "icon": "fa-triangle-exclamation",
        },
    }.get(level)
    if severity is None:
        severity = {
            "title": "Clinical review needed",
            "summary": "A care professional should review this assessment.",
            "icon": "fa-stethoscope",
        }

    recommendations = {
        "low": [
            "Continue routine antenatal appointments and follow the care plan.",
            "Keep health, fetal movement, and lab information up to date.",
            "Contact the maternity care team if symptoms or fetal movement change.",
        ],
        "medium": [
            "Arrange a prompt review with the assigned midwife or doctor.",
            "Review the contributing factors below with the care team.",
            "Seek urgent help if symptoms worsen or fetal movement reduces.",
        ],
        "high": [
            "Contact the maternity care team for urgent clinical review.",
            "Do not rely on this score alone; a clinician must assess the recorded warning signals.",
            "Use local emergency services for severe or rapidly worsening symptoms.",
        ],
        "critical": [
            "Contact the maternity care team immediately and follow their instructions.",
            "Use local emergency services for severe symptoms or if the care team cannot be reached.",
            "A clinician must confirm the cause and decide the next treatment step.",
        ],
    }.get(level, ["Ask a qualified maternity care professional to review this assessment."])

    explanation = factors.get("llm_explanation") or ""
    if not explanation or "Detailed explanation unavailable" in explanation:
        recorded_factors = factors.get("rule_factors", [])
        if recorded_factors:
            findings = "The assessment identified: " + ", ".join(recorded_factors) + "."
        else:
            findings = "No major rule-based warning factors were identified in the information currently recorded."
        explanation = (
            "**Summary**\n"
            f"This record is classified as **{level.upper()} risk** with a score of "
            f"**{assessment.risk_score}/100**. {severity['summary']}\n\n"
            "### Findings used\n"
            f"{findings}\n\n"
            "### Clinical note\n"
            "This result supports care decisions but does not provide a diagnosis. "
            "A midwife or doctor should interpret it together with symptoms and a clinical examination."
        )

    features = []
    for key, (label, unit) in FEATURE_PRESENTATION.items():
        value = factors.get("features", {}).get(key)
        if value in (None, ""):
            continue
        # Zero is useful for counts, but is misleading for missing measurements.
        if value == 0 and key in {"bp_systolic", "bp_diastolic", "fetal_heart_rate", "bmi"}:
            continue
        features.append({"label": label, "value": value, "unit": unit})

    action_labels = {
        "notify_care_team": "Care team notified",
        "create_in_app_safety_alert": "In-app safety alert",
    }
    actions = []
    if agent_run:
        for action in agent_run.result.get("actions", []):
            tool = action.get("tool", "care_action")
            detail = "Completed"
            if action.get("recipient_count") is not None:
                count = action["recipient_count"]
                detail = f"Sent to {count} care-team member{'s' if count != 1 else ''}"
            elif action.get("alert_id"):
                detail = f"Alert #{action['alert_id']} created"
            elif action.get("reason"):
                detail = action["reason"]
            actions.append({
                "label": action_labels.get(tool, tool.replace("_", " ").title()),
                "status": action.get("status", "completed"),
                "detail": detail,
            })

    trend_points = [
        {"date": date, "score": score, "level": level_name}
        for date, score, level_name in zip(
            trend.get("dates", []), trend.get("scores", []), trend.get("levels", [])
        )
    ]
    return {
        "severity": severity,
        "recommendations": recommendations,
        "clinical_factors": factors.get("rule_factors", []),
        "feature_summary": features,
        "explanation": explanation,
        "lab_reports": factors.get("lab_report_analysis") or [],
        "actions": actions,
        "trend_points": trend_points,
        "human_review_required": bool(agent_run and agent_run.result.get("human_review_required")),
    }


def has_pregnancy_access(user, pregnancy):
    if user.is_staff:
        return True
    if getattr(user, "role", None) == "MOTHER":
        return getattr(user, "user_mother", None) == pregnancy.mother
    family = Family.objects.filter(mother=pregnancy.mother)
    filters = {
        "FATHER": {"father__user": user},
        "MIDWIFE": {"midwife__user": user},
        "DOCTOR": {"doctor__user": user},
        "HOSPITAL": {"hospital__user": user},
        "HOSPITAL_STAFF": {
            "hospital__staff_members__user": user,
            "hospital__staff_members__is_active": True,
        },
    }.get(getattr(user, "role", None))
    return bool(filters and family.filter(**filters).exists())


def build_agent_response(agent_run):
    assessment = agent_run.risk_assessment
    trend = AdvancedPregnancyRiskService().get_risk_trend(
        agent_run.pregnancy,
        days=30,
    )
    return {
        "success": agent_run.status == "completed",
        "agent_run_id": str(agent_run.id),
        "agent_run_url": reverse("ai_services:agent_run_detail", args=[agent_run.id]),
        "agent": serialize_agent_run(agent_run),
        "risk_score": assessment.risk_score if assessment else None,
        "risk_level": assessment.risk_level if assessment else None,
        "explanation": assessment.factors.get("llm_explanation") if assessment else "",
        "trend": trend,
        "assessed_at": assessment.created_at.isoformat() if assessment else None,
        "model_version": assessment.prediction_model_version if assessment else None,
        "lab_report_summary": assessment.factors.get("lab_report_summary") if assessment else "",
        "lab_report_analysis": assessment.factors.get("lab_report_analysis") if assessment else [],
        "actions": agent_run.result.get("actions", []),
        "reasoning": agent_run.result.get("reasoning", ""),
        "human_review_required": agent_run.result.get("human_review_required", False),
    }


@method_decorator(login_required, name='dispatch')
class RiskAssessmentView(View):
    """
    Standard Django Class-Based View for Risk Assessment
    """

    def post(self, request, pregnancy_id):
        try:
            pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)

            # Optional: Permission check (example)
            if not self._has_permission(request.user, pregnancy):
                return JsonResponse({
                    "success": False,
                    "error": "You do not have permission to access this pregnancy."
                }, status=403)

            agent_run = MaternalCareAgent().run(
                pregnancy,
                triggered_by=request.user,
            )
            result = build_agent_response(agent_run)

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(result)
            return redirect("ai_services:show_risk", pregnancy_id=pregnancy.id)

        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=400)

    def _has_permission(self, user, pregnancy):
        return has_pregnancy_access(user, pregnancy)


@login_required
def analyze_lab_report(request, lab_test_id):
    lab_test = get_object_or_404(LabTest, id=lab_test_id)
    pregnancy = lab_test.pregnancy
    user = request.user
    if not has_pregnancy_access(user, pregnancy):
        return JsonResponse({
            "success": False,
            "error": "You do not have permission to access this lab report."
        }, status=403)

    service = LabReportAnalysisService()
    analysis = service.analyze_lab_test(lab_test)
    return JsonResponse({"success": True, "lab_report": analysis})


@login_required
def postpartum_assessment(request):
    service = PostpartumAIService()
    if request.method == "POST":
        payload = {
            "q1_mood": request.POST.get("q1_mood"),
            "q2_sleep": request.POST.get("q2_sleep"),
            "q3_feeling": request.POST.get("q3_feeling", ""),
            "q4_writing": request.POST.get("q4_writing", ""),
            "q5_drawing_desc": request.POST.get("q5_drawing_desc", ""),
        }
        result = service.generate_assessment_result(payload)
        return JsonResponse(result)

    return JsonResponse({"message": "Use POST to submit a postpartum assessment."})


# Optional: Function-based view alternative
@login_required
def calculate_risk(request, pregnancy_id):
    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "POST method required"}, status=405)

    try:
        pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
        if not has_pregnancy_access(request.user, pregnancy):
            return JsonResponse({
                "success": False,
                "error": "You do not have permission to access this pregnancy.",
            }, status=403)
        agent_run = MaternalCareAgent().run(pregnancy, triggered_by=request.user)
        return JsonResponse(build_agent_response(agent_run))
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    

@method_decorator(login_required, name='dispatch')
class ShowRiskView(View):
    """GET - Show Risk Dashboard"""
    def get(self, request, pregnancy_id):
        pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
        if not has_pregnancy_access(request.user, pregnancy):
            return JsonResponse({
                "success": False,
                "error": "You do not have permission to access this pregnancy.",
            }, status=403)

        # Get or create latest risk assessment
        latest_assessment = RiskAssessment.objects.filter(
            pregnancy=pregnancy
        ).order_by('-created_at').first()

        if not latest_assessment:
            agent_run = MaternalCareAgent().run(pregnancy, triggered_by=request.user)
            latest_assessment = agent_run.risk_assessment

        agent_run = AgentRun.objects.filter(
            pregnancy=pregnancy,
            risk_assessment=latest_assessment,
        ).prefetch_related("steps").first()

        trend = AdvancedPregnancyRiskService().get_risk_trend(pregnancy, days=30)

        context = {
            "pregnancy": pregnancy,
            "mother": pregnancy.mother,
            "risk": latest_assessment,
            "agent_run": agent_run,
            "agent_steps": agent_run.steps.all() if agent_run else [],
            "trend": trend,
            "color": self.get_risk_color(latest_assessment.risk_level),
            **_risk_page_context(latest_assessment, agent_run, trend),
        }

        return render(request, 'risk_dashboard.html', context)

    def get_risk_color(self, level):
        colors = {
            "low": "success",
            "medium": "warning",
            "high": "danger",
            "critical": "danger"
        }
        return colors.get(level, "secondary")


# Optional function-based view
@login_required
def show_risk(request, pregnancy_id):
    """Function-based alternative"""
    view = ShowRiskView()
    return view.get(request, pregnancy_id)


@login_required
def agent_run_detail(request, run_id):
    agent_run = get_object_or_404(
        AgentRun.objects.select_related("pregnancy", "risk_assessment").prefetch_related("steps"),
        id=run_id,
    )
    if not has_pregnancy_access(request.user, agent_run.pregnancy):
        return JsonResponse({
            "success": False,
            "error": "You do not have permission to inspect this agent run.",
        }, status=403)
    return JsonResponse({"success": True, "agent": serialize_agent_run(agent_run)})
