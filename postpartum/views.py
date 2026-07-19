import json
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from groq import Groq

from ai_services.services.postpartum_ai import PostpartumAIService
from dashboards.models import Pregnancy
from .forms import (
    AIStressAssessmentForm,
    JournalForm,
    MoodForm,
    PostpartumProfileForm,
    StressForm,
)
from .models import (
    AIStressAssessment,
    BreathingExercise,
    Conversation,
    DailyTip,
    DrawingSession,
    JournalEntry,
    Message,
    MoodEntry,
    PostpartumProfile,
    StressAssessment,
    StressLog,
)

try:
    client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
except Exception:
    client = None


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
    assessment = get_object_or_404(AIStressAssessment, id=assessment_id, user=request.user)
    return render(request, 'assessment_result.html', {'assessment': assessment})

@login_required
def postpartum_dashboard(request):
    # Optional: show postpartum for a specific pregnancy using ?pregnancy=<id>
    pregnancy_id = request.GET.get('pregnancy') or request.GET.get('pregnancy_id')
    pregnancy = None
    profile = None

    pregnancies = Pregnancy.objects.filter(
        mother__user=request.user,
        status__in=['delivered', 'completed'],
    ).order_by('-created_at')

    if pregnancy_id:
        pregnancy = pregnancies.filter(id=pregnancy_id).first()
    elif pregnancies.exists():
        pregnancy = pregnancies.first()

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

    mood_queryset = MoodEntry.objects.filter(user=request.user).order_by('-date', '-created_at')
    recent_moods = mood_queryset[:7]
    recent_stress = StressLog.objects.filter(user=request.user).order_by('-date', '-id')[:3]
    recent_journals = JournalEntry.objects.filter(user=request.user)[:3]
    today_tip = DailyTip.objects.filter(week=profile.current_week).first()
    breathing = BreathingExercise.objects.all()[:3]
    mood_summary = mood_queryset.aggregate(
        average_mood=Avg('mood_score'),
        average_energy=Avg('energy_level'),
        average_sleep=Avg('sleep_hours'),
    )

    context = {
        'profile': profile,
        'recent_moods': recent_moods,
        'today_tip': today_tip,
        'breathing_exercises': breathing,
        'pregnancy': pregnancy,
        'recent_stress': recent_stress,
        'recent_journals': recent_journals,
        'mood_summary': mood_summary,
        'mood_logged_today': mood_queryset.filter(date=timezone.localdate()).exists(),
        'latest_ai_assessment': AIStressAssessment.objects.filter(user=request.user).first(),
    }
    context['pregnancies'] = pregnancies
    return render(request, 'dashboardp.html', context)


@login_required
def log_mood(request):
    today_entry = MoodEntry.objects.filter(
        user=request.user,
        date=timezone.localdate(),
    ).order_by('-created_at').first()
    if request.method == "POST":
        form = MoodForm(request.POST, instance=today_entry)
        if form.is_valid():
            mood = form.save(commit=False)
            mood.user = request.user
            mood.save()
            messages.success(request, "Your mood check-in was saved.")
            return redirect('postpartum:postpartum_dashboard')
    else:
        form = MoodForm(instance=today_entry)
    return render(request, 'log_mood.html', {
        'form': form,
        'recent_moods': MoodEntry.objects.filter(user=request.user).order_by('-date', '-created_at')[:5],
    })


@login_required
def journal(request):
    if request.method == "POST":
        form = JournalForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, "Your journal entry was saved privately.")
            return redirect('postpartum:journal')
    else:
        form = JournalForm()
    return render(request, 'journal.html', {
        'form': form,
        'entries': JournalEntry.objects.filter(user=request.user)[:8],
    })


@login_required
def breathing_exercise(request, exercise_id=None):
    exercise = get_object_or_404(BreathingExercise, id=exercise_id)
    return render(request, 'breathing.html', {'exercise': exercise})


@login_required
def stress_log(request):
    if request.method == "POST":
        form = StressForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            messages.success(request, "Your stress check-in was saved.")
            return redirect('postpartum:stress_log')
    else:
        form = StressForm()
    return render(request, 'stress_log.html', {
        'form': form,
        'recent_logs': StressLog.objects.filter(user=request.user).order_by('-date', '-id')[:6],
    })


@login_required
def profile_settings(request):
    pregnancy_id = request.GET.get('pregnancy') or request.POST.get('pregnancy')
    pregnancy = None
    pregnancies = Pregnancy.objects.filter(
        mother__user=request.user,
        status__in=['delivered', 'completed'],
    ).order_by('-created_at')
    if pregnancy_id:
        pregnancy = pregnancies.filter(id=pregnancy_id).first()
    elif pregnancies.exists():
        pregnancy = pregnancies.first()

    if pregnancy:
        profile, _ = PostpartumProfile.objects.get_or_create(
            pregnancy=pregnancy,
            defaults={
                'user': request.user,
                'delivery_date': pregnancy.actual_delivery_date,
            },
        )
    else:
        profile = PostpartumProfile.objects.filter(user=request.user).order_by('-id').first()
        if not profile:
            profile = PostpartumProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = PostpartumProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your postpartum profile was updated.")
            target = reverse('postpartum:profile_settings')
            if pregnancy:
                target = f'{target}?pregnancy={pregnancy.id}'
            return redirect(target)
    else:
        form = PostpartumProfileForm(instance=profile)

    return render(request, 'profile_settings.html', {
        'form': form,
        'profile': profile,
        'pregnancy': pregnancy,
        'pregnancies': pregnancies,
    })


@login_required
def wellness_history(request):
    mood_entries = MoodEntry.objects.filter(user=request.user).order_by('-date', '-created_at')[:30]
    stress_entries = StressLog.objects.filter(user=request.user).order_by('-date', '-id')[:30]
    journal_entries = JournalEntry.objects.filter(user=request.user)[:12]
    summaries = MoodEntry.objects.filter(user=request.user).aggregate(
        average_mood=Avg('mood_score'),
        average_energy=Avg('energy_level'),
        average_sleep=Avg('sleep_hours'),
    )
    summaries['average_stress'] = StressLog.objects.filter(user=request.user).aggregate(
        value=Avg('stress_level')
    )['value']
    return render(request, 'wellness_history.html', {
        'mood_entries': mood_entries,
        'stress_entries': stress_entries,
        'journal_entries': journal_entries,
        'summaries': summaries,
    })


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
        'assessment': StressAssessment.objects.filter(user=request.user, conversation=conversation).first(),
    })


def _force_stress_assessment(conversation):
    """Force stress assessment when model didn't output <stress_data> block."""
    
    # Get conversation history
    messages = conversation.messages.all()
    history = [{"role": msg.role, "content": msg.content} for msg in messages]

    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",   # or a stronger model like llama-3.3-70b
            messages=[{"role": "system", "content": STRESS_EXTRACTION_PROMPT}] + history,
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
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    conv_id = data.get('conversation_id')
    user_text = data.get('message', '').strip()

    if not user_text:
        return JsonResponse({'error': 'Empty message'}, status=400)
    if not conv_id:
        return JsonResponse({'error': 'Conversation is required'}, status=400)
    if len(user_text) > 4000:
        return JsonResponse({'error': 'Message is too long'}, status=400)

    conversation = get_object_or_404(Conversation, id=conv_id, user=request.user)

    # Save user message
    Message.objects.create(conversation=conversation, role='user', content=user_text)

    # Build messages list for Groq
    history = [{"role": msg.role, "content": msg.content} 
               for msg in conversation.messages.all()]

    # Call Groq for normal response
    try:
        if not client:
            raise RuntimeError('AI service unavailable')
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{'role': 'system', 'content': CHAT_SYSTEM_PROMPT}] + history,
            temperature=0.7,
            max_tokens=1000,
        )
        raw_reply = response.choices[0].message.content
    except Exception:
        raw_reply = "I’m here with you. What feels most important to talk about right now—your rest, recovery, the baby, or something else?"

    stress = _parse_stress_data(raw_reply)
    clean_reply = _clean_text(raw_reply)
    Message.objects.create(conversation=conversation, role='assistant', content=clean_reply)

    result = {'reply': clean_reply, 'stress': None}

    assistant_message_count = conversation.messages.filter(role='assistant').count()

    if not stress and assistant_message_count >= 4:  # Trigger after 4 assistant replies
        stress = _force_stress_assessment(conversation)

    # Save assessment if we have stress data
    if isinstance(stress, dict):
        try:
            score = max(10, min(95, int(stress.get('score', 50))))
        except (TypeError, ValueError):
            score = 50
        level = 'high' if score > 65 else ('moderate' if score > 35 else 'low')
        insight = str(stress.get('insight', ''))
        recommendation = str(stress.get('recommendation', ''))
        
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
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    image_b64 = data.get('image_data', '')

    if not image_b64:
        return JsonResponse({'error': 'No image data'}, status=400)
    if len(image_b64) > 3_000_000:
        return JsonResponse({'error': 'Drawing is too large'}, status=400)

    # Strip data URL prefix if present
    if image_b64.startswith('data:'):
        image_b64 = image_b64.split(',', 1)[1]

    # Groq Vision Call
    try:
        if not client:
            raise RuntimeError('AI service unavailable')
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": DRAW_SYSTEM_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]}],
            temperature=0.5,
            max_tokens=800,
        )
        raw = re.sub(r'```json|```', '', response.choices[0].message.content.strip()).strip()
        result = json.loads(raw)
    except Exception:
        result = PostpartumAIService().analyze_drawing(image_b64)

    try:
        score = max(10, min(95, int(result.get('score', 50))))
    except (AttributeError, TypeError, ValueError):
        score = 50
        result = {}
    level = 'high' if score > 65 else ('moderate' if score > 35 else 'low')
    insight = str(result.get('insight', ''))
    recommendation = str(result.get('recommendation', ''))

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


@login_required
@require_POST
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
