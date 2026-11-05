import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dashboards.models import LabAttachment, LabTest

from .llm_client import PregnancyLLMExplainer


class LabReportAnalysisService:
    """Explain lab tests and uploaded lab reports in plain language."""

    def __init__(self):
        self.llm = PregnancyLLMExplainer()

    def analyze_lab_test(self, lab_test: LabTest) -> Dict[str, Any]:
        context = self._build_context(lab_test)
        if getattr(self.llm, "client", None):
            try:
                payload = self.llm.explain_lab_report(
                    lab_test=lab_test,
                    attachment_text=context.get("attachment_text", ""),
                    context_data=context,
                )
                if isinstance(payload, dict):
                    return self._normalize_payload(payload, lab_test, context)
            except Exception:
                pass

        return self._fallback_analysis(lab_test, context)

    def analyze_pregnancy_labs(self, pregnancy, limit: int = 5) -> List[Dict[str, Any]]:
        labs = LabTest.objects.filter(pregnancy=pregnancy).order_by("-taken_date")[:limit]
        return [self.analyze_lab_test(lab) for lab in labs]

    def summarize_for_assessment(self, pregnancy) -> Dict[str, Any]:
        analyses = self.analyze_pregnancy_labs(pregnancy, limit=5)
        summary_lines = []
        for item in analyses:
            summary_lines.append(
                f"{item.get('test_name', 'Lab test')}: {item.get('plain_language', '')}"
            )

        return {
            "lab_report_count": len(analyses),
            "lab_report_analysis": analyses,
            "lab_report_summary": "\n".join(summary_lines) if summary_lines else "No lab reports available.",
        }

    def _build_context(self, lab_test: LabTest) -> Dict[str, Any]:
        # An unsaved lab can still be analyzed (for example during form
        # validation), but Django cannot query its reverse relation yet.
        attachments = (
            list(lab_test.attachments.all().order_by("uploaded_at"))
            if lab_test.pk
            else []
        )
        attachment_text = self._collect_attachment_text(attachments)
        pregnancy = None
        if getattr(lab_test, "pregnancy_id", None):
            pregnancy = lab_test.pregnancy
        mother = getattr(pregnancy, "mother", None)
        user = getattr(mother, "user", None)
        return {
            "test_name": lab_test.test_name,
            "result_value": lab_test.result_value,
            "unit": lab_test.unit,
            "normal_range": lab_test.normal_range,
            "is_abnormal": lab_test.is_abnormal,
            "taken_date": lab_test.taken_date,
            "attachment_text": attachment_text,
            "attachment_count": len(attachments),
            "pregnancy_week": getattr(pregnancy, "get_pregnancy_week", lambda: None)(),
            "mother_name": (
                user.get_full_name() or user.username
                if user
                else ""
            ),
        }

    def _collect_attachment_text(self, attachments: List[LabAttachment]) -> str:
        parts = []
        for attachment in attachments:
            text = self._read_attachment_text(attachment)
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def _read_attachment_text(self, attachment: LabAttachment) -> str:
        if not attachment.file:
            return ""
        file_path = attachment.file.path
        if not file_path or not os.path.exists(file_path):
            return ""

        file_obj = Path(file_path)
        suffix = file_obj.suffix.lower()
        try:
            if suffix in {".txt", ".md", ".csv", ".json", ".log"}:
                return file_obj.read_text(encoding="utf-8", errors="ignore")
            if suffix == ".pdf":
                try:
                    from pypdf import PdfReader
                except ImportError:
                    return ""
                reader = PdfReader(str(file_obj))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
        return ""

    def _normalize_payload(self, payload: Dict[str, Any], lab_test: LabTest, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "test_name": context.get("test_name") or lab_test.test_name,
            "summary": payload.get("summary") or payload.get("plain_language") or self._fallback_summary(lab_test, context),
            "plain_language": payload.get("plain_language") or payload.get("summary") or self._fallback_summary(lab_test, context),
            "key_findings": payload.get("key_findings") or self._derive_findings(lab_test, context),
            "recommendations": payload.get("recommendations") or payload.get("next_steps") or self._default_recommendations(lab_test, context),
            "urgency": self._normalize_urgency(payload.get("urgency"), lab_test.is_abnormal),
            "result_value": context.get("result_value"),
            "unit": context.get("unit"),
            "normal_range": context.get("normal_range"),
            "is_abnormal": lab_test.is_abnormal,
            "taken_date": lab_test.taken_date,
        }

    @staticmethod
    def _normalize_urgency(value: Any, is_abnormal: bool) -> str:
        """Convert model-generated urgency text into a stable API value."""
        default = "urgent" if is_abnormal else "monitor"
        if not isinstance(value, str):
            return default

        normalized = value.strip().lower()
        if normalized in {"urgent", "monitor"}:
            return normalized

        urgent_terms = ("urgent", "immediate", "emergency", "critical")
        non_urgent_terms = ("non-urgent", "non urgent", "non‑urgent", "routine", "monitor")
        if any(term in normalized for term in non_urgent_terms):
            return "monitor"
        if any(term in normalized for term in urgent_terms):
            return "urgent"
        return default

    def _fallback_analysis(self, lab_test: LabTest, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "test_name": context.get("test_name") or lab_test.test_name,
            "summary": self._fallback_summary(lab_test, context),
            "plain_language": self._fallback_summary(lab_test, context),
            "key_findings": self._derive_findings(lab_test, context),
            "recommendations": self._default_recommendations(lab_test, context),
            "urgency": "urgent" if lab_test.is_abnormal else "monitor",
            "result_value": context.get("result_value"),
            "unit": context.get("unit"),
            "normal_range": context.get("normal_range"),
            "is_abnormal": lab_test.is_abnormal,
            "taken_date": lab_test.taken_date,
        }

    def _fallback_summary(self, lab_test: LabTest, context: Dict[str, Any]) -> str:
        base = f"{lab_test.test_name} was recorded with result {lab_test.result_value}"
        if context.get("unit"):
            base += f" {context['unit']}"
        if context.get("normal_range"):
            base += f" and a reference range of {context['normal_range']}"
        if lab_test.is_abnormal:
            base += ". This value is marked as abnormal and should be reviewed by the care team."
        else:
            base += ". This value is within the expected reference range based on the stored information."
        return base

    def _derive_findings(self, lab_test: LabTest, context: Dict[str, Any]) -> List[str]:
        findings = []
        if context.get("result_value"):
            findings.append(f"Recorded value: {context['result_value']}")
        if context.get("normal_range"):
            findings.append(f"Reference range: {context['normal_range']}")
        if lab_test.is_abnormal:
            findings.append("The result was marked abnormal.")
        if context.get("attachment_text"):
            findings.append("Uploaded report content was available for review.")
        return findings or ["No additional details were available."]

    def _default_recommendations(self, lab_test: LabTest, context: Dict[str, Any]) -> List[str]:
        if lab_test.is_abnormal:
            return [
                "Share this result with the attending doctor or midwife.",
                "Ask whether a repeat test or follow-up appointment is needed.",
                "Keep monitoring symptoms and report new concerns promptly.",
            ]
        return [
            "Continue routine prenatal monitoring.",
            "Keep the report for the next clinic visit.",
            "If symptoms change, contact the care team.",
        ]
