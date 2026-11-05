# ai_service/urls.py
from django.urls import path
from .views import *

app_name= "ai_services"

urlpatterns = [
    # Calculate Risk (POST)
    path('risk-assess/<int:pregnancy_id>/', RiskAssessmentView.as_view(), name='risk_assessment'),

    # Analyze a saved lab report attachment for one lab record
    path('lab-report-analysis/<int:lab_test_id>/', analyze_lab_report, name='lab_report_analysis'),

    # Show Risk Dashboard (GET)
    path('show-risk/<int:pregnancy_id>/', ShowRiskView.as_view(), name='show_risk'),

    # Inspect the complete plan, memory, reasoning, tool calls, and actions.
    path('agent-runs/<uuid:run_id>/', agent_run_detail, name='agent_run_detail'),

    # Postpartum AI assessment endpoint
    path('postpartum-assessment/', postpartum_assessment, name='postpartum_assessment'),

    # Optional function-based version
    path('show-risk-fb/<int:pregnancy_id>/', show_risk, name='show_risk_fb'),
]
