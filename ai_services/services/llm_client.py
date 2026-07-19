# ai_service/services/llm_client.py
from django.conf import settings
import json

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None


class PregnancyLLMExplainer:
    def __init__(self):
        self.client = None
        self.model = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")
        api_key = getattr(settings, "GROQ_API_KEY", None)
        if Groq and api_key:
            try:
                self.client = Groq(api_key=api_key)
            except Exception:
                self.client = None

    def explain_lab_report(self, lab_test, attachment_text: str = "", context_data: dict = None):
        """Turn lab data and uploaded report text into easy-to-understand guidance."""
        context_data = context_data or {}
        prompt = f"""
You are a clear and compassionate maternal health assistant. Explain this lab report in a way a mother can easily understand.

Lab Test: {context_data.get('test_name', getattr(lab_test, 'test_name', 'Lab report'))}
Result: {context_data.get('result_value', getattr(lab_test, 'result_value', 'N/A'))}
Unit: {context_data.get('unit', getattr(lab_test, 'unit', '')) or 'N/A'}
Reference Range: {context_data.get('normal_range', getattr(lab_test, 'normal_range', 'N/A')) or 'N/A'}
Marked Abnormal: {'Yes' if getattr(lab_test, 'is_abnormal', False) else 'No'}
Pregnancy Week: {context_data.get('pregnancy_week', 'N/A')}
Mother: {context_data.get('mother_name', 'Mother')}

Uploaded report text:
{attachment_text or 'No uploaded report text was provided.'}

Task:
Return JSON only with keys: summary, plain_language, key_findings, recommendations, urgency.
The plain_language field should explain what the result means in everyday words.
The recommendations should be simple next steps a mother or care team can follow.
"""

        fallback = {
            "summary": "Lab report details were captured and can be reviewed with the care team.",
            "plain_language": "The lab result has been recorded. A clinician should review it together with the mother to explain what it means.",
            "key_findings": ["The result and reference range were stored successfully."],
            "recommendations": ["Discuss the result with the doctor or midwife.", "Bring the report to the next clinic visit."],
            "urgency": "urgent" if getattr(lab_test, 'is_abnormal', False) else "monitor",
        }

        if not self.client:
            return fallback

        messages = [
            {"role": "system", "content": "You are a caring maternal health assistant who explains medical information clearly."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=700,
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            payload = json.loads(raw)
            fallback.update({k: payload.get(k) for k in fallback.keys() if payload.get(k) is not None})
            return fallback
        except Exception:
            return fallback

    def explain_risk(self, features: dict, risk_score: float, risk_level: str, rule_factors: list, context_data: dict = None):
        """
        Generate empathetic, professional, and actionable explanation using Groq.
        """
        context_data = context_data or {}
        prompt = f"""
You are an expert maternal and postpartum health assistant. Your reply should be calm, supportive, and clinically useful.

Patient Summary:
- Name: {context_data.get('mother_name', 'Mother')}
- Pregnancy Status: {context_data.get('pregnancy_status', 'Unknown')}
- Pregnancy Week: {context_data.get('pregnancy_week', 'N/A')}
- Postpartum Week: {context_data.get('postpartum_week', 'N/A')}
- Delivery Type: {context_data.get('postpartum_delivery_type', 'N/A')}
- Pre-existing Conditions: { 'Diabetes' if features.get('has_diabetes') else '' } { 'Hypertension' if features.get('has_hypertension') else '' }
- High-risk History: {'Yes' if context_data.get('is_high_risk_history') else 'No'}
- Latest BP: {context_data.get('current_bp', {}).get('systolic', 'N/A')}/{context_data.get('current_bp', {}).get('diastolic', 'N/A')}
- Recent Fetal HR: {context_data.get('current_fetal_heart_rate', 'N/A')}
- Recent Abnormal Labs: {', '.join(context_data.get('recent_abnormal_labs', [])) or 'None'}
- Recent Mood Score: {context_data.get('recent_postpartum_mood', 'N/A')}
- Recent Stress Level: {context_data.get('recent_postpartum_stress', 'N/A')}
- Detailed Lab Report Summary: {context_data.get('lab_report_summary', 'No lab report analysis available.')}

Risk Summary:
- AI Risk Score: {risk_score}/100
- Risk Level: {risk_level.upper()}
- Key Risk Factors: {', '.join(rule_factors) if rule_factors else 'None detected'}

Supporting Context:
{context_data.get('summary_text', '')}

---
Task:
Write a compassionate and clear report for the mother, and a concise support summary for her father and midwife. Include:
1. A plain-language explanation of the current risk level.
2. The most important details from lab reports, pregnancy progress, and postpartum health.
3. Immediate actions the care team should take.
4. What the mother can focus on today.
5. A short support note for the father and midwife describing how they can help.

Format the response with headings: Summary, What to Know, Recommendations, Support Team Note.
Keep the tone supportive, clinical, and non-alarming.
"""

        messages = [
            {"role": "system", "content": "You are a caring and knowledgeable maternal health AI assistant."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.35,
                max_tokens=900,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return f"Risk assessment generated. Detailed explanation unavailable at the moment. Risk Level: {risk_level.upper()} (Score: {risk_score})"