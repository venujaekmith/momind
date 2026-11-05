import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AIStressAssessment,
    BreathingExercise,
    Conversation,
    DrawingSession,
    JournalEntry,
    MoodEntry,
    PostpartumProfile,
    StressLog,
)


class PostpartumFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='postpartum-user',
            email='postpartum@example.com',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        self.exercise = BreathingExercise.objects.create(
            title='Calm breathing',
            description='A short reset.',
            duration_seconds=30,
            instruction='Breathe in, hold gently, and breathe out.',
        )

    def test_main_pages_render(self):
        urls = [
            reverse('postpartum:postpartum_dashboard'),
            reverse('postpartum:log_mood'),
            reverse('postpartum:journal'),
            reverse('postpartum:stress_log'),
            reverse('postpartum:profile_settings'),
            reverse('postpartum:wellness_history'),
            reverse('postpartum:ai_stress_assessment'),
            reverse('postpartum:ai_dash'),
            reverse('postpartum:chat'),
            reverse('postpartum:draw'),
            reverse('postpartum:wellness'),
            reverse('postpartum:breathing_exercise', args=[self.exercise.id]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_mood_journal_and_stress_entries_are_saved(self):
        response = self.client.post(reverse('postpartum:log_mood'), {
            'mood_score': 7,
            'energy_level': 6,
            'sleep_hours': 5.5,
            'feelings': 'Tired, but supported.',
        })
        self.assertRedirects(response, reverse('postpartum:postpartum_dashboard'))
        self.assertTrue(MoodEntry.objects.filter(user=self.user, mood_score=7).exists())
        self.client.post(reverse('postpartum:log_mood'), {
            'mood_score': 8,
            'energy_level': 7,
            'sleep_hours': 6,
            'feelings': 'A little better.',
        })
        self.assertEqual(MoodEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(MoodEntry.objects.get(user=self.user).mood_score, 8)

        response = self.client.post(reverse('postpartum:journal'), {
            'title': 'A small win',
            'content': 'We rested together this afternoon.',
            'mood': 7,
        })
        self.assertRedirects(response, reverse('postpartum:journal'))
        self.assertTrue(JournalEntry.objects.filter(user=self.user).exists())

        response = self.client.post(reverse('postpartum:stress_log'), {
            'stress_level': 5,
            'trigger': 'Interrupted sleep',
            'coping_method': 'Asked for help',
            'notes': '',
        })
        self.assertRedirects(response, reverse('postpartum:stress_log'))
        self.assertTrue(StressLog.objects.filter(user=self.user, stress_level=5).exists())

    def test_profile_rejects_future_delivery_date(self):
        future = timezone.localdate() + timedelta(days=1)
        response = self.client.post(reverse('postpartum:profile_settings'), {
            'delivery_date': future.isoformat(),
            'delivery_type': 'normal',
            'baby_count': 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delivery date cannot be in the future.')

        profile = PostpartumProfile.objects.get(user=self.user)
        self.assertIsNone(profile.delivery_date)

    @patch('postpartum.views.client', None)
    def test_chat_falls_back_cleanly_when_ai_is_unavailable(self):
        conversation = Conversation.objects.create(user=self.user)
        response = self.client.post(
            reverse('postpartum:send_message'),
            data=json.dumps({'conversation_id': conversation.id, 'message': 'I feel tired.'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['reply'])
        self.assertEqual(conversation.messages.count(), 2)

    @patch('postpartum.views.client', None)
    def test_drawing_analysis_has_offline_fallback(self):
        response = self.client.post(
            reverse('postpartum:analyze_drawing'),
            data=json.dumps({'image_data': 'small-test-image'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()['level'], {'low', 'moderate', 'high'})
        self.assertTrue(DrawingSession.objects.filter(user=self.user).exists())

    def test_new_conversation_requires_post(self):
        url = reverse('postpartum:new_conversation')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_assessment_result_is_user_scoped_and_returns_home(self):
        assessment = AIStressAssessment.objects.create(
            user=self.user,
            q1_mood=6,
            q2_sleep=5,
            stress_score=45,
            insight='You may be carrying some strain.',
            recommendation='Ask someone you trust for a short rest break.',
        )
        response = self.client.get(reverse('postpartum:assessment_result', args=[assessment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('postpartum:postpartum_dashboard'))
