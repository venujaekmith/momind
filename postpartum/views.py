from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import (
    PostpartumProfile, MoodEntry, JournalEntry, 
    BreathingExercise, DailyTip, StressLog
)
from django.utils import timezone
from dashboards.models import Pregnancy
from .forms import MoodForm, JournalForm, StressForm
from .models import AIStressAssessment
from .forms import AIStressAssessmentForm
from ai_services.services.postpartum_ai import PostpartumAIService
import random
import json
import re
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from groq import Groq
from .models import Conversation, Message, DrawingSession, StressAssessment

client = Groq(api_key=settings.GROQ_API_KEY)


CHAT_SYSTEM_PROMPT = """You are a warm, gentle postpartum support companion. Your role is to have a natural, caring conversation with a new mother about her day, feelings, sleep, baby, body, and current life situation.

Ask open, empathetic questions one at a time. Listen carefully. After 4-6 exchanges, when you have enough context, include a special data block at the very end of your response in this EXACT format:

<stress_data>{"score": 45, "level": "moderate", "insight": "one caring sentence about what you noticed", "recommendation": "one gentle practical suggestion"}</stress_data>

Score guide: 10-35 = low, 36-65 = moderate, 66-95 = high

Rules:
- Be warm and human, never clinical
- Keep each response short: 2-4 sentences + one follow-up question
- Never mention scoring or assessment to the mother
- Never include the <stress_data> block more than once per conversation
- Ask about: mood, sleep, feeding challenges, support system, physical recovery, any worries about the outside world
"""

DRAW_SYSTEM_PROMPT = """You are analyzing a drawing made by a postpartum mother to express her current emotional state.

Examine:
- Colors (dark/muted vs bright/warm)
- Line quality (jagged/sharp vs smooth/flowing)
- Composition (chaotic vs ordered, empty vs full)
- Any recognizable shapes, symbols, figures
- Overall emotional tone

Respond ONLY with valid JSON, no other text, no markdown fences:
{"score": 55, "level": "moderate", "insight": "one warm sentence about the emotional quality of the drawing", "recommendation": "one gentle suggestion for the mother"}

Score: 10-35 low, 36-65 moderate, 66-95 high"""

STRESS_EXTRACTION_PROMPT = """You are analyzing the conversation between a postpartum mother and her support companion.

Based on the entire conversation history, assess her current emotional state and stress level.

Respond **ONLY** with valid JSON in this exact format, nothing else:
{
  "score": 45,
  "level": "moderate",
  "insight": "one caring sentence summarizing her emotional state",
  "recommendation": "one gentle practical suggestion"
}

Score guide: 10-35 = low, 36-65 = moderate, 66-95 = high"""

@login_required
def ai_stress_assessment(request):
    if request.method == "POST":
        form = AIStressAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.user = request.user

            service = PostpartumAIService()
            result = service.generate_assessment_result({
                "q1_mood": assessment.q1_mood,
                "q2_sleep": assessment.q2_sleep,
                "q3_feeling": assessment.q3_feeling,
                "q4_writing": assessment.q4_writing,
                "q5_drawing_desc": assessment.q5_drawing_desc,
            })

            assessment.stress_score = result["score"]
            assessment.insight = result["insight"]
            assessment.recommendation = result["recommendation"]

            assessment.save()
            return redirect('postpartum:assessment_result', assessment.id)
    else:
        form = AIStressAssessmentForm()

    questions = [
        "On a scale of 1-10, how would you rate your mood today?",
        "How many hours did you sleep last night?",
        "How are you feeling emotionally?",
        "Free writing space - write anything",
        "Describe a drawing that represents your current feelings"
    ]

    return render(request, 'ai_assessment.html', {
        'form': form,
        'questions': questions
    })


@login_required
def assessment_result(request, assessment_id):
    assessment = AIStressAssessment.objects.get(id=assessment_id, user=request.user)
    return render(request, 'assessment_result.html', {'assessment': assessment})

@login_required
def postpartum_dashboard(request):
    # Optional: show postpartum for a specific pregnancy using ?pregnancy=<id>
    pregnancy_id = request.GET.get('pregnancy') or request.GET.get('pregnancy_id')
    pregnancy = None
    profile = None

    if pregnancy_id:
        try:
            pregnancy = Pregnancy.objects.get(id=pregnancy_id, mother__user=request.user)
        except Pregnancy.DoesNotExist:
            pregnancy = None

    if pregnancy:
        profile, created = PostpartumProfile.objects.get_or_create(
            pregnancy=pregnancy,
            defaults={
                'user': request.user,
                'delivery_date': pregnancy.actual_delivery_date or timezone.now().date(),
            }
        )
    else:
        # fallback: use latest postpartum profile for the user or create one
        profile = PostpartumProfile.objects.filter(user=request.user).order_by('-id').first()
        if not profile:
            profile = PostpartumProfile.objects.create(user=request.user)

    recent_moods = MoodEntry.objects.filter(user=request.user)[:7]
    today_tip = DailyTip.objects.filter(week=profile.current_week).first()
    breathing = BreathingExercise.objects.all()[:3]

    context = {
        'profile': profile,
        'recent_moods': recent_moods,
        'today_tip': today_tip,
        'breathing_exercises': breathing,
        'pregnancy': pregnancy,
    }
    # Include user's pregnancies for UI selection
    try:
        context['pregnancies'] = Pregnancy.objects.filter(mother__user=request.user).order_by('-created_at')
    except Exception:
        context['pregnancies'] = []
    return render(request, 'dashboardp.html', context)


@login_required
def log_mood(request):
    if request.method == "POST":
        form = MoodForm(request.POST)
        if form.is_valid():
            mood = form.save(commit=False)
            mood.user = request.user
            mood.save()
            return redirect('postpartum:postpartum_dashboard')
    else:
        form = MoodForm()
    return render(request, 'log_mood.html', {'form': form})


@login_required
def journal(request):
    if request.method == "POST":
        form = JournalForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            return redirect('postpartum:dashboard')
    else:
        form = JournalForm()
    return render(request, 'journal.html', {'form': form})


@login_required
def breathing_exercise(request, exercise_id=None):
    if exercise_id:
        exercise = BreathingExercise.objects.get(id=exercise_id)
    else:
        exercise = BreathingExercise.objects.first()
    return render(request, 'breathing.html', {'exercise': exercise})


@login_required
def stress_log(request):
    if request.method == "POST":
        form = StressForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            return redirect('postpartum:dashboard')
    else:
        form = StressForm()
    return render(request, 'stress_log.html', {'form': form})


def _parse_stress_data(text):
    """Extract <stress_data> JSON block from assistant response."""
    match = re.search(r'<stress_data>(.*?)</stress_data>', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    return None


def _clean_text(text):
    """Remove stress_data block from visible response."""
    return re.sub(r'<stress_data>.*?</stress_data>', '', text, flags=re.DOTALL).strip()




@login_required
def dashboard(request):
    latest_assessment = StressAssessment.objects.filter(user=request.user).first()
    recent_conversations = Conversation.objects.filter(user=request.user)[:5]
    context = {
        'assessment': latest_assessment,
        'conversations': recent_conversations,
    }
    return render(request, 'postpartum/dashboard.html', context)


@login_required
def chat_view(request):
    conversation_id = request.GET.get('conv')
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    else:
        conversation = Conversation.objects.filter(user=request.user, is_active=True).first()
        if not conversation:
            conversation = Conversation.objects.create(user=request.user)

    messages = conversation.messages.all()
    return render(request, 'postpartum/chat.html', {
        'conversation': conversation,
        'messages': messages,
    })


def _force_stress_assessment(conversation):
    """Force stress assessment when model didn't output <stress_data> block."""
    
    # Get conversation history
    messages = conversation.messages.all()
    history = [{"role": msg.role, "content": msg.content} for msg in messages]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",   # or a stronger model like llama-3.3-70b
            messages=history + [
                {"role": "system", "content": STRESS_EXTRACTION_PROMPT}
            ],
            temperature=0.5,
            max_tokens=600,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'```json|```', '', raw).strip()

        return json.loads(raw)

    except Exception as e:
        print(f"Stress assessment failed: {e}")
        return None


@login_required
@require_POST
def send_message(request):
    data = json.loads(request.body)
    conv_id = data.get('conversation_id')
    user_text = data.get('message', '').strip()

    if not user_text:
        return JsonResponse({'error': 'Empty message'}, status=400)

    conversation = get_object_or_404(Conversation, id=conv_id, user=request.user)

    # Save user message
    Message.objects.create(conversation=conversation, role='user', content=user_text)

    # Build messages list for Groq
    history = [{"role": msg.role, "content": msg.content} 
               for msg in conversation.messages.all()]

    # Call Groq for normal response
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=history,
        temperature=0.7,
        max_tokens=1000,
    )
    raw_reply = response.choices[0].message.content

    # Save full reply
    Message.objects.create(conversation=conversation, role='assistant', content=raw_reply)

    stress = _parse_stress_data(raw_reply)
    clean_reply = _clean_text(raw_reply)

    result = {'reply': clean_reply, 'stress': None}

    assistant_message_count = conversation.messages.filter(role='assistant').count()

    if not stress and assistant_message_count >= 4:  # Trigger after 4 assistant replies
        stress = _force_stress_assessment(conversation)

    # Save assessment if we have stress data
    if stress:
        score = max(10, min(95, int(stress.get('score', 50))))
        level = stress.get('level', 'moderate')
        insight = stress.get('insight', '')
        recommendation = stress.get('recommendation', '')
        
        assessment, _ = StressAssessment.objects.get_or_create(
            user=request.user,
            conversation=conversation,
        )
        assessment.chat_score = score
        assessment.chat_insight = insight
        assessment.recommendation = recommendation
        assessment.compute_overall()

        result['stress'] = {
            'score': score,
            'level': level,
            'insight': insight,
            'recommendation': recommendation,
        }

    return JsonResponse(result)


@login_required
@require_POST
def analyze_drawing(request):
    data = json.loads(request.body)
    image_b64 = data.get('image_data', '')

    if not image_b64:
        return JsonResponse({'error': 'No image data'}, status=400)

    # Strip data URL prefix if present
    if image_b64.startswith('data:'):
        image_b64 = image_b64.split(',', 1)[1]

    # Groq Vision Call
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",  # Strong vision model
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": DRAW_SYSTEM_PROMPT,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        },
                    },
                ],
            }
        ],
        temperature=0.5,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'```json|```', '', raw).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Could not parse analysis'}, status=500)

    score = max(10, min(95, int(result.get('score', 50))))
    level = result.get('level', 'moderate')
    insight = result.get('insight', '')
    recommendation = result.get('recommendation', '')

    # Save drawing session
    drawing = DrawingSession.objects.create(
        user=request.user,
        image_data=image_b64,
        stress_score=score,
        stress_level=level,
        insight=insight,
        recommendation=recommendation,
    )

    # Link to assessment
    assessment = StressAssessment.objects.filter(user=request.user).first()
    if not assessment:
        assessment = StressAssessment.objects.create(user=request.user)
    
    assessment.drawing = drawing
    assessment.draw_score = score
    assessment.draw_insight = insight
    if not assessment.recommendation:
        assessment.recommendation = recommendation
    assessment.compute_overall()

    return JsonResponse({
        'score': score,
        'level': level,
        'insight': insight,
        'recommendation': recommendation,
    })


# Other views remain the same...
@login_required
def new_conversation(request):
    Conversation.objects.filter(user=request.user, is_active=True).update(is_active=False)
    conversation = Conversation.objects.create(user=request.user)
    return JsonResponse({'conversation_id': conversation.id})


@login_required
def wellness_view(request):
    assessment = StressAssessment.objects.filter(user=request.user).first()
    return render(request, 'postpartum/wellness.html', {'assessment': assessment})

@login_required
def draw_view(request):
    return render(request, 'postpartum/draw.html')