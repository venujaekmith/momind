from django.test import SimpleTestCase

from ai_services.services.postpartum_ai import PostpartumAIService
from ai_services.services.lab_report_analysis import LabReportAnalysisService
from dashboards.models import LabTest, Pregnancy


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
