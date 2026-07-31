from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import MotherDetails, MotherProfile, Role
from ai_services.models import AgentRun
from ai_services.services.maternal_agent import MaternalCareAgent
from ai_services.services.postpartum_ai import PostpartumAIService
from ai_services.services.lab_report_analysis import LabReportAnalysisService
from dashboards.models import (
    EmergencyAlert,
    FetalHealth,
    LabTest,
    Notification,
    Pregnancy,
    PregnancyProgress,
)


class PostpartumAIServiceTests(SimpleTestCase):
    def test_assessment_fallback_generates_score_and_guidance(self):
        service = PostpartumAIService()
        result = service.generate_assessment_result({
            "q1_mood": 2,
            "q2_sleep": 3,
            "q3_feeling": "tired and scared",
            "q4_writing": "I feel alone",
            "q5_drawing_desc": "dark clouds",
        })

        self.assertGreaterEqual(result["score"], 10)
        self.assertLessEqual(result["score"], 95)
        self.assertIn(result["level"], {"low", "moderate", "high"})
        self.assertTrue(result["insight"])
        self.assertTrue(result["recommendation"])


class LabReportAnalysisServiceTests(SimpleTestCase):
    def test_analysis_returns_structured_guidance_for_lab_test(self):
        service = LabReportAnalysisService()
        lab_test = LabTest(test_name="CBC", result_value="7.2", unit="g/dL", normal_range="5.0-10.0", is_abnormal=False)
        analysis = service.analyze_lab_test(lab_test)

        self.assertEqual(analysis["test_name"], "CBC")
        self.assertTrue(analysis["plain_language"])
        self.assertIn("recommendations", analysis)
        self.assertIn("urgency", analysis)

        self.assertEqual(analysis["urgency"], "monitor")


@override_settings(GROQ_API_KEY="")
class MaternalCareAgentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="agent-mother",
            email="agent-mother@example.com",
            password="safe-test-password",
            role=Role.MOTHER,
            is_role_selected=True,
        )
        self.mother = MotherProfile.objects.create(
            user=self.user,
            mother_id="M-AGENT-001",
        )
        MotherDetails.objects.create(
            user=self.user,
            mother=self.mother,
            height_cm=160,
            has_hypertension=True,
        )
        self.pregnancy = Pregnancy.objects.create(
            mother=self.mother,
            last_menstrual_period=timezone.localdate() - timedelta(weeks=30),
            pre_pregnancy_weight=60,
        )
        PregnancyProgress.objects.create(
            pregnancy=self.pregnancy,
            week=30,
            bp_systolic=155,
            bp_diastolic=100,
        )
        FetalHealth.objects.create(
            pregnancy=self.pregnancy,
            week=30,
            heart_rate=138,
            movement_level="low",
        )
        LabTest.objects.create(
            pregnancy=self.pregnancy,
            test_name="Haemoglobin",
            result_value="9.2",
            unit="g/dL",
            normal_range="11.0-15.0",
            is_abnormal=True,
            taken_date=timezone.localdate(),
        )

    def test_agent_plans_reasons_remembers_and_takes_guarded_actions(self):
        agent_run = MaternalCareAgent().run(self.pregnancy, triggered_by=self.user)

        self.assertEqual(agent_run.status, "completed")
        self.assertEqual(agent_run.steps.count(), 5)
        self.assertEqual(
            list(agent_run.steps.values_list("tool_name", flat=True)),
            [
                "retrieve_memory",
                "inspect_health_record",
                "calculate_hybrid_risk",
                "decide_care_actions",
                "execute_care_actions",
            ],
        )
        self.assertEqual(agent_run.memory_snapshot["assessment_count"], 0)
        self.assertIn(agent_run.risk_assessment.risk_level, {"high", "critical"})
        self.assertEqual(
            agent_run.risk_assessment.factors["lab_report_analysis"][0]["taken_date"],
            timezone.localdate().isoformat(),
        )
        self.assertTrue(agent_run.result["human_review_required"])
        self.assertTrue(
            EmergencyAlert.objects.filter(
                pregnancy=self.pregnancy,
                triggered_by_ai=True,
            ).exists()
        )
        self.assertTrue(Notification.objects.filter(user=self.user).exists())
        self.assertEqual(
            agent_run.risk_assessment.factors["agent"]["run_id"],
            str(agent_run.id),
        )

        second_run = MaternalCareAgent().run(self.pregnancy, triggered_by=self.user)
        self.assertEqual(second_run.memory_snapshot["assessment_count"], 1)
        self.assertEqual(
            EmergencyAlert.objects.filter(
                pregnancy=self.pregnancy,
                triggered_by_ai=True,
            ).count(),
            1,
        )

    def test_agent_endpoint_returns_trace_and_is_family_scoped(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("ai_services:risk_assessment", args=[self.pregnancy.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["agent"]["steps"]), 5)
        agent_run = AgentRun.objects.get(id=payload["agent_run_id"])

        detail = self.client.get(
            reverse("ai_services:agent_run_detail", args=[agent_run.id])
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["agent"]["id"], str(agent_run.id))

        dashboard = self.client.get(
            reverse("ai_services:show_risk", args=[self.pregnancy.id])
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Agent reasoning trace")
        self.assertContains(dashboard, "calculate_hybrid_risk")

        other_user = get_user_model().objects.create_user(
            username="other-agent-user",
            email="other-agent@example.com",
            password="safe-test-password",
            role=Role.MOTHER,
            is_role_selected=True,
        )
        MotherProfile.objects.create(user=other_user, mother_id="M-AGENT-OTHER")
        self.client.force_login(other_user)
        forbidden = self.client.get(
            reverse("ai_services:agent_run_detail", args=[agent_run.id])
        )
        self.assertEqual(forbidden.status_code, 403)
