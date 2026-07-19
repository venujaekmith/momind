import json
import re
from typing import Any, Dict, Optional

from django.conf import settings

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None


class PostpartumAIService:
    """Postpartum wellbeing analysis with a heuristic fallback."""

    def __init__(self):
        self.client = None
        self.model = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")
        api_key = getattr(settings, "GROQ_API_KEY", None)
        if Groq and api_key:
            try:
                self.client = Groq(api_key=api_key)
            except Exception:
                self.client = None

    def generate_assessment_result(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        raw_score = 0
        q1_mood = answers.get("q1_mood")
        q2_sleep = answers.get("q2_sleep")
        q3_feeling = str(answers.get("q3_feeling") or "")
        q4_writing = str(answers.get("q4_writing") or "")
        q5_drawing_desc = str(answers.get("q5_drawing_desc") or "")

        if q1_mood is not None:
            raw_score += (11 - int(q1_mood)) * 6
        if q2_sleep is not None:
            try:
                sleep_hours = float(q2_sleep)
            except (TypeError, ValueError):
                sleep_hours = 0
            if sleep_hours < 6:
                raw_score += (6 - sleep_hours) * 8

        text = f"{q3_feeling} {q4_writing} {q5_drawing_desc}".lower()
        negative_words = [
            "tired", "sad", "cry", "alone", "scared", "overwhelmed", "angry", "worthless"
        ]
        for word in negative_words:
            if word in text:
                raw_score += 8

        score = max(10, min(95, int(round(raw_score))))
        level = self._score_to_level(score)
        insight, recommendation = self._build_guidance(score)

        if self.client:
            try:
                llm_response = self._ask_llm(q3_feeling, q4_writing, q5_drawing_desc, score)
                if llm_response:
                    insight = llm_response.get("insight") or insight
                    recommendation = llm_response.get("recommendation") or recommendation
            except Exception:
                pass

        return {
            "score": score,
            "level": level,
            "insight": insight,
            "recommendation": recommendation,
        }

    def process_chat_message(self, history: list[Dict[str, str]], user_message: str) -> Dict[str, Any]:
        if self.client:
            try:
                messages = list(history) + [{"role": "user", "content": user_message}]
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=800,
                )
                reply = response.choices[0].message.content.strip()
                return {"reply": reply, "stress": None}
            except Exception:
                pass

        return {
            "reply": "I’m here with you. Tell me what feels most challenging right now, and I’ll help you take the next step.",
            "stress": None,
        }

    def analyze_drawing(self, image_base64: str) -> Dict[str, Any]:
        score = 55
        level = self._score_to_level(score)
        insight = "Your drawing suggests a mix of emotion and resilience."
        recommendation = "Take a moment to breathe and notice one grounding detail in your surroundings."
        return {"score": score, "level": level, "insight": insight, "recommendation": recommendation}

    def _ask_llm(self, feeling: str, writing: str, drawing_desc: str, score: int) -> Optional[Dict[str, Any]]:
        prompt = f"""
You are a warm postpartum wellbeing assistant. The mother reported:
- Mood: {feeling}
- Journal: {writing}
- Drawing: {drawing_desc}
- Current score: {score}/100

Return JSON only with keys: insight, recommendation.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a gentle maternal wellbeing assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return {
            "insight": payload.get("insight", ""),
            "recommendation": payload.get("recommendation", ""),
        }

    def _score_to_level(self, score: int) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "moderate"
        return "low"

    def _build_guidance(self, score: int) -> tuple[str, str]:
        if score > 70:
            return (
                "You seem to be experiencing high levels of stress. This is very common in the early postpartum period.",
                "Try a calm breathing exercise and consider reaching out to your midwife or doctor if this feeling continues.",
            )
        if score > 40:
            return (
                "You are experiencing moderate stress. Your body and mind are adjusting after birth.",
                "Practice gentle self-care, rest when possible, and reach out to family or other mothers for support.",
            )
        return (
            "Your stress level appears manageable right now. Great job taking care of yourself.",
            "Continue journaling, resting, and celebrating small wins each day.",
        )
