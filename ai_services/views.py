# ai_service/views.py
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from dashboards.models import Pregnancy, RiskAssessment, LabTest
from .services.risk_assessment import AdvancedPregnancyRiskService
from .services.postpartum_ai import PostpartumAIService
from .services.lab_report_analysis import LabReportAnalysisService


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

            service = AdvancedPregnancyRiskService()
            assessment = service.calculate_risk(pregnancy)

            return JsonResponse({
                "success": True,
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level,
                "explanation": assessment.factors.get("llm_explanation"),
                "trend": service.get_risk_trend(pregnancy, days=30),
                "assessed_at": assessment.created_at.isoformat(),
                "model_version": assessment.prediction_model_version,
                "lab_report_summary": assessment.factors.get("lab_report_summary"),
                "lab_report_analysis": assessment.factors.get("lab_report_analysis"),
            })

        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=400)

    def _has_permission(self, user, pregnancy):
        """Basic permission logic"""
        # Mother herself
        if hasattr(user, 'user_mother') and user.user_mother == pregnancy.mother:
            return True
        # Midwife / Doctor linked to mother
        # Add more logic as needed
        return user.is_staff or user.role in ['MIDWIFE', 'DOCTOR']


@login_required
def analyze_lab_report(request, lab_test_id):
    lab_test = get_object_or_404(LabTest, id=lab_test_id)
    pregnancy = lab_test.pregnancy
    user = request.user
    allowed_roles = {"MIDWIFE", "DOCTOR", "HOSPITAL", "HOSPITAL_STAFF"}
    has_access = (
        (hasattr(user, "user_mother") and user.user_mother == pregnancy.mother)
        or getattr(user, "role", None) in allowed_roles
        or user.is_staff
    )

    if not has_access:
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
        service = AdvancedPregnancyRiskService()
        assessment = service.calculate_risk(pregnancy)

        return JsonResponse({
            "success": True,
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level,
            "explanation": assessment.factors.get("llm_explanation"),
            "trend": service.get_risk_trend(pregnancy),
            "lab_report_summary": assessment.factors.get("lab_report_summary"),
            "lab_report_analysis": assessment.factors.get("lab_report_analysis"),
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    

@method_decorator(login_required, name='dispatch')
class ShowRiskView(View):
    """GET - Show Risk Dashboard"""
    def get(self, request, pregnancy_id):
        pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)

        # Get or create latest risk assessment
        latest_assessment = RiskAssessment.objects.filter(
            pregnancy=pregnancy
        ).order_by('-created_at').first()

        if not latest_assessment:
            service = AdvancedPregnancyRiskService()
            latest_assessment = service.calculate_risk(pregnancy)

        trend = AdvancedPregnancyRiskService().get_risk_trend(pregnancy, days=30)

        context = {
            "pregnancy": pregnancy,
            "mother": pregnancy.mother,
            "risk": latest_assessment,
            "trend": trend,
            "color": self.get_risk_color(latest_assessment.risk_level),
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