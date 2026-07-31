import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import MotherProfile, Role
from dashboards.models import Pregnancy
from .services.context import build_context

from .models import ChatMessage, ChatSession


class ChatEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="chat-user",
            email="chat@example.com",
            password="safe-test-password",
        )

    def test_endpoints_require_authentication(self):
        self.assertEqual(self.client.post(reverse("chat:start_session")).status_code, 302)
        self.assertEqual(self.client.post(reverse("chat:send_message")).status_code, 302)

    def test_chatbot_template_uses_current_routes_and_csrf(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:chatbot"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("chat:start_session"))
        self.assertContains(response, reverse("chat:send_message"))
        self.assertContains(response, "csrfmiddlewaretoken")

    @patch("chat.views.get_ai_reply", side_effect=RuntimeError("offline"))
    def test_chat_validates_and_falls_back_when_provider_is_offline(self, _mock_reply):
        self.client.force_login(self.user)
        started = self.client.post(reverse("chat:start_session")).json()
        session = ChatSession.objects.get(id=started["session_id"])

        empty = self.client.post(
            reverse("chat:send_message"),
            data=json.dumps({"session_id": session.id, "message": "  "}),
            content_type="application/json",
        )
        self.assertEqual(empty.status_code, 400)

        response = self.client.post(
            reverse("chat:send_message"),
            data=json.dumps({"session_id": session.id, "message": "I need support"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["reply"])
        self.assertEqual(ChatMessage.objects.filter(session=session).count(), 2)

    def test_user_cannot_read_another_users_session(self):
        other = get_user_model().objects.create_user(
            username="other-chat",
            email="other-chat@example.com",
            password="safe-test-password",
        )
        session = ChatSession.objects.create(user=other)
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:get_messages", args=[session.id]))
        self.assertEqual(response.status_code, 404)

    def test_chat_context_uses_the_mothers_current_pregnancy(self):
        self.user.role = Role.MOTHER
        self.user.is_role_selected = True
        self.user.save(update_fields=["role", "is_role_selected"])
        mother = MotherProfile.objects.create(user=self.user, mother_id="M-CHAT")
        pregnancy = Pregnancy.objects.create(
            mother=mother,
            last_menstrual_period=timezone.localdate() - timedelta(weeks=18),
            expected_delivery_date=timezone.localdate() + timedelta(weeks=22),
        )

        context = build_context(self.user, "How is this week different?")

        self.assertEqual(context["phase"], "pregnancy")
        self.assertEqual(context["week"], pregnancy.get_pregnancy_week())
        self.assertEqual(context["delivery_date"], str(pregnancy.expected_delivery_date))

# Create your tests here.
