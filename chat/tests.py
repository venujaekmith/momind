import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile, Family, FatherProfile, MidwifeProfile, MotherProfile, Role
from dashboards.models import Notification, Pregnancy
from .services.context import build_context

from .models import (
    ChatMessage,
    ChatSession,
    CheckupQuestion,
    CheckupSession,
    MaternalCheckIn,
    ProfessionalChatMessage,
    ProfessionalChatRequest,
)


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

    def test_mother_receives_daily_checkin_and_answer_is_saved(self):
        self.user.role = Role.MOTHER
        self.user.is_role_selected = True
        self.user.save(update_fields=["role", "is_role_selected"])
        mother = MotherProfile.objects.create(user=self.user, mother_id="M-CHECKIN")
        pregnancy = Pregnancy.objects.create(mother=mother)
        self.client.force_login(self.user)

        started = self.client.post(reverse("chat:start_checkup_session")).json()
        self.assertEqual(started["question"], MaternalCheckIn.QUESTIONS[0][1])

        response = self.client.post(
            reverse("chat:send_checkup_message"),
            data=json.dumps({
                "session_id": started["session_id"],
                "question_id": started["question_id"],
                "message": "I have vomited twice and feel weak.",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        check_in = MaternalCheckIn.objects.get(id=started["question_id"])
        self.assertEqual(check_in.answer, "I have vomited twice and feel weak.")
        self.assertIsNotNone(check_in.answered_at)
        self.assertEqual(check_in.pregnancy, pregnancy)
        self.assertEqual(response.json()["total_questions"], 5)
        self.assertEqual(response.json()["answered_questions"], 1)
        self.assertEqual(response.json()["remaining_questions"], 4)

        next_started = self.client.post(reverse("chat:start_checkup_session")).json()
        self.assertIsNotNone(next_started["question"])
        self.assertTrue(CheckupSession.objects.filter(user=self.user).exists())

    def test_linked_care_team_can_trigger_checkup(self):
        self.user.role = Role.MOTHER
        self.user.is_role_selected = True
        self.user.save(update_fields=["role", "is_role_selected"])
        mother = MotherProfile.objects.create(user=self.user, mother_id="M-TRIGGER")
        pregnancy = Pregnancy.objects.create(mother=mother)
        doctor_user = get_user_model().objects.create_user(
            username="checkup-doctor",
            email="checkup-doctor@example.com",
            password="test-password",
            role=Role.DOCTOR,
        )
        doctor = DoctorProfile.objects.create(user=doctor_user, doctor_id="DOC-CHECKUP")
        Family.objects.create(mother=mother, pregnancy=pregnancy, doctor=doctor)
        self.client.force_login(doctor_user)

        response = self.client.post(
            reverse("chat:trigger_checkup", args=[pregnancy.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["question"], MaternalCheckIn.QUESTIONS[0][1])
        self.assertTrue(
            MaternalCheckIn.objects.filter(
                user=self.user,
                checkup__trigger_type="doctor",
            ).exists()
        )

    def test_linked_doctor_can_add_question_for_every_checkup(self):
        self.user.role = Role.MOTHER
        self.user.is_role_selected = True
        self.user.save(update_fields=["role", "is_role_selected"])
        mother = MotherProfile.objects.create(user=self.user, mother_id="M-QUESTION")
        pregnancy = Pregnancy.objects.create(mother=mother)
        doctor_user = get_user_model().objects.create(
            username="question-doctor",
            email="question-doctor@example.com",
            role=Role.DOCTOR,
        )
        doctor_user.set_password("test-password")
        doctor_user.save(update_fields=["password"])
        doctor = DoctorProfile.objects.create(user=doctor_user, doctor_id="DOC-QUESTION")
        Family.objects.create(mother=mother, pregnancy=pregnancy, doctor=doctor)

        self.client.force_login(doctor_user)
        response = self.client.post(
            reverse("chat:add_checkup_question", args=[pregnancy.id]),
            {"question": "Have you noticed any new swelling?"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            CheckupQuestion.objects.filter(
                pregnancy=pregnancy,
                created_by=doctor_user,
                question="Have you noticed any new swelling?",
            ).exists()
        )

    def test_family_members_can_chat_without_a_request(self):
        self.user.role = Role.MOTHER
        self.user.is_role_selected = True
        self.user.save(update_fields=["role", "is_role_selected"])
        mother = MotherProfile.objects.create(user=self.user, mother_id="M-FAMILY-CHAT")
        doctor_user = get_user_model().objects.create_user(
            username="chat-doctor",
            email="chat-doctor@example.com",
            role=Role.DOCTOR,
        )
        doctor = DoctorProfile.objects.create(user=doctor_user, doctor_id="DOC-FAMILY-CHAT")
        Family.objects.create(mother=mother, doctor=doctor)

        self.client.force_login(self.user)
        listing = self.client.get(reverse("chat:professional_chat"))
        self.assertEqual(listing.status_code, 200)
        chat_request = ProfessionalChatRequest.objects.get(
            requester=self.user, professional=doctor_user
        )
        self.assertEqual(chat_request.status, "accepted")

        sent = self.client.post(
            reverse("chat:professional_conversation", args=[chat_request.id]),
            {"message": "I have a question."},
        )
        self.assertRedirects(
            sent,
            reverse("chat:professional_conversation", args=[chat_request.id]),
        )
        self.assertTrue(
            ProfessionalChatMessage.objects.filter(
                request=chat_request, sender=self.user
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=doctor_user,
                title="New care team chat message",
            ).exists()
        )
        self.client.force_login(doctor_user)
        dashboard = self.client.get(reverse("dashboards:dashboard"))
        self.assertEqual(dashboard.context["care_team_unread_count"], 1)
        listing = self.client.get(reverse("chat:professional_chat"))
        self.assertContains(listing, "chat-user")
        self.assertContains(listing, "1 new")
        self.assertEqual(
            Notification.objects.filter(
                user=doctor_user,
                title="New care team chat message",
                is_read=False,
            ).count(),
            1,
        )
        conversation = self.client.get(
            reverse("chat:professional_conversation", args=[chat_request.id])
        )
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(
                user=doctor_user,
                title="New care team chat message",
                is_read=False,
            ).count(),
            0,
        )
        dashboard_after_read = self.client.get(reverse("dashboards:dashboard"))
        self.assertEqual(
            dashboard_after_read.context["care_team_unread_count"],
            0,
        )

        unrelated = get_user_model().objects.create_user(
            username="unrelated-doctor",
            email="unrelated-doctor@example.com",
            role=Role.DOCTOR,
        )
        self.client.force_login(unrelated)
        self.assertEqual(
            self.client.get(
                reverse("chat:professional_conversation", args=[chat_request.id])
            ).status_code,
            403,
        )

# Create your tests here.
