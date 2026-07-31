# ai_service/services/risk_assessment.py
import json

import pandas as pd
import xgboost as xgb
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.db import transaction

from accounts.models import Family
from dashboards.models import (
    RiskAssessment, Pregnancy, PregnancyProgress, FetalHealth,
    WeightLog, LabTest, EmergencyAlert, Notification
)
from postpartum.models import MoodEntry, JournalEntry, StressLog
from .llm_client import PregnancyLLMExplainer
from .lab_report_analysis import LabReportAnalysisService


def _json_safe(value):
    """Convert dates, decimals, and other Django values into JSON-safe data."""
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


class AdvancedPregnancyRiskService:

    def __init__(self):
        self.ml_model = self._load_or_train_model()
        self.llm = PregnancyLLMExplainer()
        scoring_engine = "xgboost" if self.ml_model is not None else "clinical-rules"
        explanation_engine = "groq" if self.llm.client is not None else "safe-fallback"
        self.model_version = f"maternal-agent-{scoring_engine}-{explanation_engine}-v2.0"
        self.lab_analysis_service = LabReportAnalysisService()

    def _load_or_train_model(self):
        model_path = Path(settings.BASE_DIR) / "ai_services" / "models" / "risk_model.json"
        try:
            model = xgb.Booster()
            model.load_model(str(model_path))
            return model
        except Exception:
            # Do not train a random model during a web request. Apart from
            # delaying every assessment, random labels make results unstable.
            # _predict_with_ml provides a deterministic fallback until a
            # versioned model is deployed at model_path.
            return None

    def calculate_risk(
        self,
        pregnancy: Pregnancy,
        trigger_actions=True,
        prepared_features=None,
        prepared_context=None,
    ):
        with transaction.atomic():
            features = prepared_features or self._extract_features(pregnancy)
            context_data = prepared_context or self._gather_context(pregnancy)
            context_data['summary_text'] = self._format_context_for_prompt(context_data)

            ml_score, ml_level, probabilities = self._predict_with_ml(features)
            rule_score, rule_factors = self._apply_rule_based(features)

            final_score = round(min(100.0, max(0.0, 0.7 * ml_score + 0.3 * rule_score)), 2)
            final_level = self._determine_risk_level(final_score)

            llm_explanation = self.llm.explain_risk(
                features,
                final_score,
                final_level,
                rule_factors,
                context_data
            )

            assessment = RiskAssessment.objects.create(
                pregnancy=pregnancy,
                risk_score=final_score,
                risk_level=final_level,
                factors=_json_safe({
                    "features": features,
                    "rule_factors": rule_factors,
                    "llm_explanation": llm_explanation,
                    "analysis_summary": context_data['summary_text'],
                    "lab_report_summary": context_data.get('lab_report_summary'),
                    "lab_report_analysis": context_data.get('lab_report_analysis'),
                }),
                prediction_model_version=self.model_version,
            )

            if trigger_actions:
                self._trigger_emergency_alert(pregnancy, final_level, llm_explanation)
                self._notify_family(pregnancy, assessment, context_data)
            return assessment

    def _extract_features(self, pregnancy):
        mother = pregnancy.mother
        details = getattr(mother, 'mother_details', None)

        latest_progress = PregnancyProgress.objects.filter(
            pregnancy=pregnancy).order_by('-recorded_at').first()
        latest_fetal = FetalHealth.objects.filter(
            pregnancy=pregnancy).order_by('-recorded_at').first()
        latest_weight = WeightLog.objects.filter(
            mother=mother).order_by('-date').first()
        # Prefer a postpartum profile attached to this pregnancy, fall back to any user-level profile
        postpartum_profile = getattr(pregnancy, 'postpartum_profile', None) or (getattr(mother.user, 'postpartum_profiles', None).order_by('-id').first() if getattr(mother.user, 'postpartum_profiles', None) is not None else None)
        latest_mood = MoodEntry.objects.filter(user=mother.user).order_by('-date').first()
        latest_stress = StressLog.objects.filter(user=mother.user).order_by('-date').first()

        return {
            "age": (getattr(details, 'age', None) or 28) if details else 28,
            "gestational_week": pregnancy.get_pregnancy_week() or 0,
            "bmi": self._calculate_bmi(details, pregnancy.pre_pregnancy_weight),
            "has_diabetes": int(getattr(details, 'has_diabetes', False)),
            "has_hypertension": int(getattr(details, 'has_hypertension', False)),
            "previous_pregnancies": (getattr(details, 'previous_pregnancies', None) or 0) if details else 0,
            "bp_systolic": (latest_progress.bp_systolic or 0) if latest_progress else 0,
            "bp_diastolic": (latest_progress.bp_diastolic or 0) if latest_progress else 0,
            "fetal_heart_rate": (latest_fetal.heart_rate or 0) if latest_fetal else 0,
            "movement_level_low": int(latest_fetal.movement_level == "low" if latest_fetal else False),
            "weight_gain": round(float(latest_weight.weight) - float(pregnancy.pre_pregnancy_weight), 2)
                          if latest_weight and pregnancy.pre_pregnancy_weight else 0.0,
            "abnormal_lab_count": LabTest.objects.filter(
                pregnancy=pregnancy, is_abnormal=True).count(),
            "is_high_risk_history": int(pregnancy.is_high_risk),
            "postpartum_week": getattr(postpartum_profile, 'current_week', None),
            "recent_postpartum_mood": latest_mood.mood_score if latest_mood else None,
            "recent_postpartum_stress": latest_stress.stress_level if latest_stress else None,
        }

    def _predict_with_ml(self, features):
        feature_order = [
            "age", "gestational_week", "bmi", "has_diabetes", "has_hypertension",
            "previous_pregnancies", "bp_systolic", "bp_diastolic", "fetal_heart_rate",
            "movement_level_low", "weight_gain", "abnormal_lab_count"
        ]

        if self.ml_model is None:
            score = 0.0
            score += 30 if features["has_hypertension"] else 0
            score += 25 if features["has_diabetes"] else 0
            score += 25 if features["bp_systolic"] >= 140 else 0
            score += 15 if (features["bp_diastolic"] or 0) >= 90 else 0
            score += 25 if features["movement_level_low"] else 0
            score += min(20, features["abnormal_lab_count"] * 10)
            score += 10 if features["age"] < 18 or features["age"] >= 35 else 0
            score = min(100.0, score)
            level = self._determine_risk_level(score)
            probabilities = [0.0, 0.0, 0.0, 0.0]
            probabilities[["low", "medium", "high", "critical"].index(level)] = 1.0
            return score, level, probabilities

        df = pd.DataFrame([features])[feature_order]

        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        dmatrix = xgb.DMatrix(df)

        pred = self.ml_model.predict(dmatrix)
        probabilities = self.ml_model.predict(dmatrix, output_margin=False).tolist()

        ml_score = float(pred[0]) * 25
        ml_level = ["low", "medium", "high", "critical"][int(pred[0])]

        return ml_score, ml_level, probabilities

    def _apply_rule_based(self, features):
        score = 0.0
        factors = []

        if (features["bp_systolic"] or 0) >= 140:
            score += 35
            factors.append("High Blood Pressure")
        if features["movement_level_low"]:
            score += 45
            factors.append("Reduced Fetal Movement")
        if features["has_diabetes"]:
            score += 25
            factors.append("Diabetes")
        if features["has_hypertension"]:
            score += 30
            factors.append("Hypertension")
        if features["abnormal_lab_count"] >= 2:
            score += 20
            factors.append("Multiple Abnormal Labs")

        if features.get("postpartum_week") is not None:
            score += 10
            factors.append("Postpartum Monitoring")
            if features["postpartum_week"] <= 6:
                score += 15
                factors.append("Early Postpartum Period")
            if features.get("recent_postpartum_mood") is not None and features["recent_postpartum_mood"] <= 4:
                score += 20
                factors.append("Low Postpartum Mood")
            if features.get("recent_postpartum_stress") is not None and features["recent_postpartum_stress"] >= 7:
                score += 20
                factors.append("Elevated Postpartum Stress")

        return score, factors

    def _determine_risk_level(self, score: float):
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        return "low"

    def _gather_context(self, pregnancy):
        mother = pregnancy.mother
        details = getattr(mother, 'mother_details', None)
        postpartum_profile = getattr(pregnancy, 'postpartum_profile', None) or (getattr(mother.user, 'postpartum_profiles', None).order_by('-id').first() if getattr(mother.user, 'postpartum_profiles', None) is not None else None)

        latest_progress = PregnancyProgress.objects.filter(
            pregnancy=pregnancy).order_by('-recorded_at')[:5]
        latest_fetal = FetalHealth.objects.filter(
            pregnancy=pregnancy).order_by('-recorded_at')[:5]
        latest_labs = LabTest.objects.filter(pregnancy=pregnancy).order_by('-taken_date')[:5]
        latest_mood = MoodEntry.objects.filter(user=mother.user).order_by('-date').first()
        lab_analysis_summary = self.lab_analysis_service.summarize_for_assessment(pregnancy)
        latest_stress = StressLog.objects.filter(user=mother.user).order_by('-date').first()
        latest_journal = JournalEntry.objects.filter(user=mother.user).order_by('-date').first()

        family = Family.objects.filter(mother=mother).first()
        family_members = []
        if family:
            if family.father:
                family_members.append({"role": "Father", "name": family.father.user.get_full_name() or family.father.user.username})
            if family.midwife:
                family_members.append({"role": "Midwife", "name": family.midwife.user.get_full_name() or family.midwife.user.username})
            if family.doctor:
                family_members.append({"role": "Doctor", "name": family.doctor.user.get_full_name() or family.doctor.user.username})
            if family.hospital:
                family_members.append({"role": "Hospital", "name": family.hospital.user.get_full_name() or family.hospital.user.username})

        abnormal_labs = [lab.test_name for lab in latest_labs if getattr(lab, 'is_abnormal', False)]

        progress_summary = [
            f"Week {record.week}: BP {record.bp_systolic}/{record.bp_diastolic}, weight {record.weight or 'N/A'}"
            for record in latest_progress
        ]
        fetal_summary = [
            f"Week {record.week}: HR {record.heart_rate or 'N/A'}, movement {record.movement_level.capitalize()}"
            for record in latest_fetal
        ]

        return {
            "mother_name": mother.user.get_full_name() or mother.user.username,
            "pregnancy_status": pregnancy.status,
            "pregnancy_week": pregnancy.get_pregnancy_week() or 0,
            "pre_pregnancy_weight": pregnancy.pre_pregnancy_weight,
            "is_high_risk_history": pregnancy.is_high_risk,
            "current_bp": {
                "systolic": latest_progress[0].bp_systolic if latest_progress else None,
                "diastolic": latest_progress[0].bp_diastolic if latest_progress else None,
            },
            "current_fetal_heart_rate": latest_fetal[0].heart_rate if latest_fetal else None,
            "recent_progress_summary": progress_summary,
            "recent_fetal_summary": fetal_summary,
            "recent_abnormal_labs": abnormal_labs,
            "recent_labs": [lab.test_name for lab in latest_labs],
            "lab_report_summary": lab_analysis_summary.get('lab_report_summary', ''),
            "lab_report_analysis": lab_analysis_summary.get('lab_report_analysis', []),
            "lab_report_count": lab_analysis_summary.get('lab_report_count', 0),
            "postpartum_week": getattr(postpartum_profile, 'current_week', None),
            "postpartum_delivery_type": getattr(postpartum_profile, 'delivery_type', None),
            "recent_postpartum_mood": latest_mood.mood_score if latest_mood else None,
            "recent_postpartum_stress": latest_stress.stress_level if latest_stress else None,
            "recent_journal_excerpt": latest_journal.content[:250] if latest_journal else None,
            "family_members": family_members,
        }

    def _format_context_for_prompt(self, context_data):
        lines = [
            f"Patient: {context_data['mother_name']}",
            f"Pregnancy status: {context_data['pregnancy_status']}",
            f"Current pregnancy week: {context_data['pregnancy_week']}",
            f"Pre-pregnancy weight: {context_data['pre_pregnancy_weight']}",
            f"High-risk history: {'yes' if context_data['is_high_risk_history'] else 'no'}",
        ]

        if context_data['current_bp']['systolic'] and context_data['current_bp']['diastolic']:
            lines.append(f"Latest blood pressure: {context_data['current_bp']['systolic']}/{context_data['current_bp']['diastolic']}")

        if context_data['current_fetal_heart_rate']:
            lines.append(f"Latest fetal heart rate: {context_data['current_fetal_heart_rate']}")

        if context_data['recent_progress_summary']:
            lines.append("Recent pregnancy progress:")
            lines.extend(context_data['recent_progress_summary'])

        if context_data['recent_fetal_summary']:
            lines.append("Recent fetal health records:")
            lines.extend(context_data['recent_fetal_summary'])

        if context_data['recent_abnormal_labs']:
            lines.append(f"Abnormal labs: {', '.join(context_data['recent_abnormal_labs'])}")

        if context_data['postpartum_week'] is not None:
            lines.append(f"Postpartum week: {context_data['postpartum_week']}")
            lines.append(f"Delivery type: {context_data['postpartum_delivery_type']}")
            if context_data['recent_postpartum_mood'] is not None:
                lines.append(f"Most recent mood score: {context_data['recent_postpartum_mood']}")
            if context_data['recent_postpartum_stress'] is not None:
                lines.append(f"Most recent stress level: {context_data['recent_postpartum_stress']}")
            if context_data['recent_journal_excerpt']:
                lines.append(f"Journal excerpt: {context_data['recent_journal_excerpt']}")

        if context_data['family_members']:
            lines.append("Care team:")
            lines.extend([f"{member['role']}: {member['name']}" for member in context_data['family_members']])

        return "\n".join(lines)

    def _build_notification_message(self, assessment, context_data):
        summary = (
            f"AI assessment for {context_data['mother_name']}: "
            f"Risk level {assessment.risk_level.upper()} ({assessment.risk_score}/100). "
        )
        if context_data['recent_abnormal_labs']:
            summary += f"Recent abnormal lab tests include {', '.join(context_data['recent_abnormal_labs'])}. "
        if context_data['postpartum_week'] is not None:
            summary += f"Mother is currently in postpartum week {context_data['postpartum_week']}. "

        summary += "Please review the AI explanation and take recommended follow-up actions."
        return summary

    def _notify_family(self, pregnancy, assessment, context_data):
        mother = pregnancy.mother
        family = Family.objects.filter(mother=mother).first()
        recipients = {mother.user}

        if family:
            if family.father and family.father.user:
                recipients.add(family.father.user)
            if family.midwife and family.midwife.user:
                recipients.add(family.midwife.user)
            if family.doctor and family.doctor.user:
                recipients.add(family.doctor.user)
            if family.hospital and family.hospital.user:
                recipients.add(family.hospital.user)

        message = self._build_notification_message(assessment, context_data)
        title = f"AI Health Summary - {assessment.risk_level.title()} Risk"

        notification_ids = []
        for recipient in recipients:
            notification = Notification.objects.create(
                user=recipient,
                title=title,
                message=message
            )
            notification_ids.append(notification.id)
        return notification_ids

    def _trigger_emergency_alert(self, pregnancy, risk_level, explanation):
        if risk_level in ["high", "critical"]:
            recent_cutoff = timezone.now() - timedelta(hours=6)
            existing = EmergencyAlert.objects.filter(
                pregnancy=pregnancy,
                is_resolved=False,
                triggered_by_ai=True,
                created_at__gte=recent_cutoff,
            ).order_by("-created_at").first()
            if existing:
                return {"alert_id": existing.id, "created": False}
            alert = EmergencyAlert.objects.create(
                pregnancy=pregnancy,
                alert_type="other",
                message=f"AI Risk Alert: {risk_level.upper()} risk detected.",
                triggered_by_ai=True
            )
            return {"alert_id": alert.id, "created": True}
        return None

    def notify_care_team(self, pregnancy, assessment, context_data):
        """Execute the notification tool and return auditable identifiers."""
        return self._notify_family(pregnancy, assessment, context_data)

    def create_safety_alert(self, pregnancy, risk_level, explanation):
        """Execute a policy-guarded emergency alert tool."""
        return self._trigger_emergency_alert(pregnancy, risk_level, explanation)

    def get_risk_trend(self, pregnancy, days=30):
        assessments = list(RiskAssessment.objects.filter(
            pregnancy=pregnancy,
            created_at__gte=timezone.now() - timedelta(days=days)
        ).order_by('created_at'))

        trend = "first_assessment"
        if len(assessments) > 1:
            first_score = assessments[0].risk_score
            last_score = assessments[-1].risk_score
            if last_score < first_score:
                trend = "improving"
            elif last_score > first_score:
                trend = "worsening"
            else:
                trend = "stable"

        return {
            "dates": [a.created_at.strftime("%Y-%m-%d") for a in assessments],
            "scores": [float(a.risk_score) for a in assessments],
            "levels": [a.risk_level for a in assessments],
            "trend": trend,
        }

    def _calculate_bmi(self, details, pre_weight):
        if details and getattr(details, 'height_cm', None) and pre_weight:
            return round(pre_weight / ((details.height_cm / 100) ** 2), 2)
        return 0.0
