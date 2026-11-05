from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile, HospitalProfile, MidwifeProfile, MotherProfile, Role
from dashboards.models import Clinics, Pregnancy, ScheduleEvent
from .models import (
    CommunityNotification,
    GroupMember,
    HospitalGroup,
    HospitalGroupSubscription,
    CommunityAIInsight,
    GroupPost,
    GroupComment,
)
from .services.personalization import CommunityPersonalizationService


class CommunityPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.hospital_user = User.objects.create_user(
            username="hospital-owner",
            email="hospital-owner@example.com",
            password="safe-test-password",
            role=Role.HOSPITAL,
            is_role_selected=True,
        )
        self.hospital = HospitalProfile.objects.create(
            user=self.hospital_user,
            hospital_id="H-COMMUNITY",
            name="Community Hospital",
        )
        self.regular_user = User.objects.create_user(
            username="community-user",
            email="community-user@example.com",
            password="safe-test-password",
            role=Role.MOTHER,
            is_role_selected=True,
        )
        self.midwife_user = User.objects.create_user(
            username="community-midwife",
            email="community-midwife@example.com",
            password="safe-test-password",
            role=Role.MIDWIFE,
            is_role_selected=True,
        )
        self.midwife = MidwifeProfile.objects.create(
            user=self.midwife_user,
            midwife_id="MW-COMMUNITY",
        )
        self.doctor_user = User.objects.create_user(
            username="community-doctor",
            email="community-doctor@example.com",
            password="testpass123",
            role=Role.DOCTOR,
            is_role_selected=True,
        )
        DoctorProfile.objects.create(
            user=self.doctor_user,
            doctor_id="DOC-COMMUNITY",
            hospital=self.hospital,
        )
        self.group = HospitalGroup.objects.create(
            hospital=self.hospital,
            name="Private care group",
            created_by=self.hospital_user,
            is_private=True,
        )

    def test_private_group_cannot_be_self_joined(self):
        self.client.force_login(self.regular_user)
        response = self.client.post(reverse("community:join_group", args=[self.group.id]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GroupMember.objects.filter(group=self.group, user=self.regular_user).exists())

    def test_unrelated_user_cannot_announce_for_hospital_clinic(self):
        clinic = Clinics.objects.create(
            hospital=self.hospital,
            name="Clinic",
            date=timezone.localdate() + timedelta(days=1),
        )
        self.client.force_login(self.regular_user)
        response = self.client.post(
            reverse("community:create_clinic_announcement", args=[clinic.id]),
            {"message": "Changed"},
        )
        self.assertEqual(response.status_code, 403)

    def test_clinic_announcement_notifies_booked_patients_and_subscribers_once(self):
        clinic = Clinics.objects.create(
            hospital=self.hospital,
            name="Antenatal clinic",
            date=timezone.localdate() + timedelta(days=1),
        )
        mother = MotherProfile.objects.create(
            user=self.regular_user,
            mother_id="M-COMMUNITY",
        )
        pregnancy = Pregnancy.objects.create(mother=mother)
        ScheduleEvent.objects.create(
            pregnancy=pregnancy,
            title="Antenatal appointment",
            event_type="hospital_clinic",
            scheduled_date=clinic.date,
            clinic=clinic,
        )
        HospitalGroupSubscription.objects.create(
            user=self.regular_user,
            hospital_group=self.group,
        )

        self.client.force_login(self.hospital_user)
        response = self.client.post(
            reverse("community:create_clinic_announcement", args=[clinic.id]),
            {"message": "The clinic will begin at 9:00 AM."},
        )

        self.assertRedirects(response, reverse("community:hospital_dashboard"))
        notification = CommunityNotification.objects.get(user=self.regular_user)
        self.assertEqual(notification.notification_type, "hospital_announcement")
        self.assertEqual(notification.hospital_group, self.group)
        self.assertIsNone(notification.clinic_schedule)

    def test_forum_creation_requires_login(self):
        response = self.client.get(reverse("community:create_post"))
        self.assertEqual(response.status_code, 302)

    def test_community_pages_render_for_hospital_owner(self):
        self.assertEqual(self.client.get(reverse("community:forum_home")).status_code, 200)
        self.client.force_login(self.hospital_user)
        urls = [
            reverse("community:group_list"),
            reverse("community:group_detail", args=[self.group.id]),
            reverse("community:clinic_schedules", args=[self.group.id]),
            reverse("community:create_clinic_schedule", args=[self.group.id]),
            reverse("community:hospital_dashboard"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_public_group_uses_post_join_flow(self):
        public_group = HospitalGroup.objects.create(
            owner_midwife=self.midwife,
            name="Public midwife group",
            created_by=self.midwife_user,
            is_private=False,
        )
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("community:group_list"))
        self.assertContains(
            response,
            f'action="{reverse("community:join_group", args=[public_group.id])}"',
            html=False,
        )
        self.assertContains(response, 'method="post"', html=False)

    def test_midwife_can_create_and_manage_independent_group(self):
        self.client.force_login(self.midwife_user)
        list_response = self.client.get(reverse("community:group_list"))
        self.assertContains(list_response, reverse("community:create_group"))

        response = self.client.post(reverse("community:create_group"), {
            "name": "Midwife prenatal circle",
            "description": "Weekly education and peer support.",
            "is_private": "on",
            "hospital_id": "",
        })
        group = HospitalGroup.objects.get(name="Midwife prenatal circle")
        self.assertRedirects(response, reverse("community:group_detail", args=[group.id]))
        self.assertEqual(group.owner_midwife, self.midwife)
        self.assertIsNone(group.hospital)
        self.assertTrue(GroupMember.objects.filter(
            group=group,
            user=self.midwife_user,
            role=GroupMember.Role.ADMIN,
        ).exists())

        manage_url = reverse("community:manage_group", args=[group.id])
        self.assertEqual(self.client.get(manage_url).status_code, 200)
        add_response = self.client.post(manage_url, {
            "action": "add_member",
            "username": self.regular_user.username,
            "role": GroupMember.Role.PATIENT,
        })
        self.assertRedirects(add_response, manage_url)
        member = GroupMember.objects.get(group=group, user=self.regular_user)
        self.assertTrue(HospitalGroupSubscription.objects.filter(
            hospital_group=group,
            user=self.regular_user,
        ).exists())

        update_response = self.client.post(manage_url, {
            "action": "update_group",
            "name": "Midwife parent circle",
            "description": "Updated description",
            "is_private": "on",
        })
        self.assertRedirects(update_response, manage_url)
        group.refresh_from_db()
        self.assertEqual(group.name, "Midwife parent circle")

        remove_response = self.client.post(reverse(
            "community:remove_group_member",
            args=[group.id, member.id],
        ))
        self.assertRedirects(remove_response, manage_url)
        self.assertFalse(GroupMember.objects.filter(id=member.id).exists())

    def test_doctor_can_create_protected_group(self):
        self.client.force_login(self.doctor_user)
        response = self.client.post(reverse("community:create_group"), {
            "name": "Doctor care circle",
            "description": "Questions for my assigned mothers.",
            "is_private": "",
        })
        group = HospitalGroup.objects.get(name="Doctor care circle")
        self.assertRedirects(response, reverse("community:group_detail", args=[group.id]))
        self.assertEqual(group.owner_doctor.user_id, self.doctor_user.id)
        self.assertEqual(group.hospital_id, self.hospital.id)
        self.assertTrue(group.is_private)

    def test_private_professional_response_is_only_visible_to_mother(self):
        GroupMember.objects.create(
            group=self.group,
            user=self.regular_user,
            role=GroupMember.Role.PATIENT,
        )
        GroupMember.objects.create(
            group=self.group,
            user=self.doctor_user,
            role=GroupMember.Role.DOCTOR,
        )
        post = GroupPost.objects.create(
            group=self.group,
            author=self.regular_user,
            content="I have a private concern.",
        )
        self.client.force_login(self.doctor_user)
        response = self.client.post(
            reverse("community:add_group_comment", args=[self.group.id, post.id]),
            {"content": "Please contact me through your care plan.", "visibility": "private"},
        )
        self.assertRedirects(response, reverse("community:group_detail", args=[self.group.id]))
        comment = GroupComment.objects.get(post=post)
        self.assertTrue(comment.is_private)
        self.assertEqual(comment.recipient_id, self.regular_user.id)
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("community:group_detail", args=[self.group.id]))
        self.assertContains(response, "Please contact me through your care plan.")

    def test_unrelated_user_cannot_manage_midwife_group(self):
        group = HospitalGroup.objects.create(
            owner_midwife=self.midwife,
            name="Private midwife team",
            created_by=self.midwife_user,
            is_private=True,
        )
        GroupMember.objects.create(
            group=group,
            user=self.midwife_user,
            role=GroupMember.Role.ADMIN,
        )
        self.client.force_login(self.regular_user)
        self.assertEqual(
            self.client.get(reverse("community:manage_group", args=[group.id])).status_code,
            403,
        )

    def test_midwife_role_member_can_manage_hospital_group(self):
        GroupMember.objects.create(
            group=self.group,
            user=self.midwife_user,
            role=GroupMember.Role.MIDWIFE,
        )
        self.client.force_login(self.midwife_user)
        self.assertEqual(
            self.client.get(reverse("community:manage_group", args=[self.group.id])).status_code,
            200,
        )

    def test_doctor_can_generate_summary_and_approve_personalized_response(self):
        mother = MotherProfile.objects.create(
            user=self.regular_user,
            mother_id="M-AI-COMMUNITY",
        )
        Pregnancy.objects.create(mother=mother)
        GroupMember.objects.create(
            group=self.group,
            user=self.regular_user,
            role=GroupMember.Role.PATIENT,
        )
        GroupMember.objects.create(
            group=self.group,
            user=self.doctor_user,
            role=GroupMember.Role.DOCTOR,
        )
        post = GroupPost.objects.create(
            group=self.group,
            author=self.regular_user,
            content="I have been feeling unusually tired today.",
        )
        self.client.force_login(self.doctor_user)

        summary_response = self.client.post(
            reverse("community:request_mother_summary", args=[self.group.id, post.id])
        )
        self.assertRedirects(summary_response, reverse("community:group_detail", args=[self.group.id]))
        self.assertTrue(
            CommunityAIInsight.objects.filter(
                group_post=post,
                kind=CommunityAIInsight.Kind.SUMMARY,
                requested_by=self.doctor_user,
            ).exists()
        )
        personalization_response = self.client.post(
            reverse("community:personalize_group_response", args=[self.group.id, post.id]),
            {"response": "Please rest and contact the clinic if this continues."},
        )
        self.assertRedirects(
            personalization_response,
            reverse("community:group_detail", args=[self.group.id]),
        )
        insight = CommunityAIInsight.objects.get(
            group_post=post,
            kind=CommunityAIInsight.Kind.PERSONALIZED_RESPONSE,
        )
        self.assertFalse(insight.is_approved)

        approval_response = self.client.post(
            reverse(
                "community:approve_personalized_response",
                args=[self.group.id, post.id, insight.id],
            ),
            {"approved_content": "Edited and approved response.", "visibility": "private"},
        )
        self.assertRedirects(approval_response, reverse("community:group_detail", args=[self.group.id]))
        insight.refresh_from_db()
        self.assertTrue(insight.is_approved)
        comment = GroupComment.objects.get(post=post, author=self.doctor_user)
        self.assertEqual(comment.content, "Edited and approved response.")
        self.assertTrue(comment.is_private)
        self.assertEqual(comment.recipient_id, self.regular_user.id)

    def test_ai_context_is_scoped_to_the_requesting_professional(self):
        context = {
            "pregnancy_status": "ongoing",
            "recent_moh_visits": [{"complaints": "doctor-only"}],
            "recent_midwife_visits": [{"notes": "midwife-only"}],
            "family_members": [{"role": "Father", "name": "Not needed"}],
            "symptom_history": [
                {"author": "doctor", "text": "doctor symptom"},
                {"author": "midwife", "text": "midwife symptom"},
                {"author": None, "text": "mother symptom"},
            ],
        }

        doctor_context = CommunityPersonalizationService._scope_context(context, Role.DOCTOR)
        midwife_context = CommunityPersonalizationService._scope_context(context, Role.MIDWIFE)

        self.assertIn("recent_moh_visits", doctor_context)
        self.assertNotIn("recent_midwife_visits", doctor_context)
        self.assertNotIn("family_members", doctor_context)
        self.assertEqual(
            [item["author"] for item in doctor_context["symptom_history"]],
            ["doctor", None],
        )
        self.assertIn("recent_midwife_visits", midwife_context)
        self.assertNotIn("recent_moh_visits", midwife_context)
        self.assertNotIn("family_members", midwife_context)
        self.assertEqual(
            [item["author"] for item in midwife_context["symptom_history"]],
            ["midwife", None],
        )

    def test_risk_report_has_clear_sections_and_no_family_details(self):
        report = CommunityPersonalizationService._full_risk_report({
            "concern": "Reduced fetal movement",
            "viewer_role": Role.MIDWIFE,
            "agent_review": {
                "risk_level": "high",
                "risk_score": 68,
                "risk_factors": ["Low movement recorded"],
                "trend": "worsening",
                "actions": [],
            },
            "pregnancy_status": "ongoing",
            "pregnancy_week": 32,
            "is_high_risk_history": False,
            "recent_fetal_summary": ["Week 32: HR 145, movement Low"],
        })

        for section in (
            "RISK STATUS",
            "RISKS IDENTIFIED",
            "EVIDENCE REVIEWED",
            "TREND",
            "CARE ACTIONS",
            "MISSING OR UNVERIFIED INFORMATION",
            "SAFETY NOTE",
        ):
            self.assertIn(section, report)
        self.assertIn("HIGH", report)
        self.assertIn("Low movement recorded", report)
        self.assertNotIn("Father", report)

    def test_midwife_can_generate_and_approve_private_personalized_response(self):
        mother = MotherProfile.objects.create(
            user=self.regular_user,
            mother_id="M-AI-MIDWIFE",
        )
        Pregnancy.objects.create(mother=mother)
        GroupMember.objects.create(
            group=self.group,
            user=self.regular_user,
            role=GroupMember.Role.PATIENT,
        )
        GroupMember.objects.create(
            group=self.group,
            user=self.midwife_user,
            role=GroupMember.Role.MIDWIFE,
        )
        post = GroupPost.objects.create(
            group=self.group,
            author=self.regular_user,
            content="I have a new concern for my midwife.",
        )
        self.client.force_login(self.midwife_user)

        summary_response = self.client.post(
            reverse("community:request_mother_summary", args=[self.group.id, post.id])
        )
        self.assertRedirects(summary_response, reverse("community:group_detail", args=[self.group.id]))

        personalization_response = self.client.post(
            reverse("community:personalize_group_response", args=[self.group.id, post.id]),
            {"response": "Please monitor this and contact the clinic if it worsens."},
        )
        self.assertRedirects(
            personalization_response,
            reverse("community:group_detail", args=[self.group.id]),
        )
        insight = CommunityAIInsight.objects.get(
            group_post=post,
            kind=CommunityAIInsight.Kind.PERSONALIZED_RESPONSE,
            requested_by=self.midwife_user,
        )
        approval_response = self.client.post(
            reverse(
                "community:approve_personalized_response",
                args=[self.group.id, post.id, insight.id],
            ),
            {"approved_content": "Please monitor this and call me if it worsens.", "visibility": "private"},
        )
        self.assertRedirects(
            approval_response,
            reverse("community:group_detail", args=[self.group.id]),
        )
        comment = GroupComment.objects.get(post=post, author=self.midwife_user)
        self.assertTrue(comment.is_private)
        self.assertEqual(comment.recipient_id, self.regular_user.id)

    def test_doctor_group_owner_can_generate_ai_help(self):
        group = HospitalGroup.objects.create(
            owner_doctor=DoctorProfile.objects.get(user=self.doctor_user),
            name="Doctor-led care group",
            created_by=self.doctor_user,
            is_private=True,
        )
        GroupMember.objects.create(
            group=group,
            user=self.doctor_user,
            role=GroupMember.Role.ADMIN,
        )
        mother = MotherProfile.objects.create(
            user=self.regular_user,
            mother_id="M-AI-DOCTOR-OWNER",
        )
        Pregnancy.objects.create(mother=mother)
        GroupMember.objects.create(
            group=group,
            user=self.regular_user,
            role=GroupMember.Role.PATIENT,
        )
        post = GroupPost.objects.create(
            group=group,
            author=self.regular_user,
            content="I have a question for the doctor-led community.",
        )
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("community:request_mother_summary", args=[group.id, post.id])
        )

        self.assertRedirects(response, reverse("community:group_detail", args=[group.id]))
        self.assertTrue(
            CommunityAIInsight.objects.filter(
                group_post=post,
                kind=CommunityAIInsight.Kind.SUMMARY,
                requested_by=self.doctor_user,
            ).exists()
        )
        personalization_response = self.client.post(
            reverse("community:personalize_group_response", args=[group.id, post.id]),
            {"response": "Please contact the clinic if this continues."},
        )
        self.assertRedirects(
            personalization_response,
            reverse("community:group_detail", args=[group.id]),
        )
        insight = CommunityAIInsight.objects.get(
            group_post=post,
            kind=CommunityAIInsight.Kind.PERSONALIZED_RESPONSE,
            requested_by=self.doctor_user,
        )
        approval_response = self.client.post(
            reverse(
                "community:approve_personalized_response",
                args=[group.id, post.id, insight.id],
            ),
            {"approved_content": "Please contact the clinic if this continues."},
        )
        self.assertRedirects(
            approval_response,
            reverse("community:group_detail", args=[group.id]),
        )
        insight.refresh_from_db()
        self.assertTrue(insight.is_approved)

    def test_midwife_group_owner_can_generate_ai_help(self):
        group = HospitalGroup.objects.create(
            owner_midwife=self.midwife,
            name="Midwife-led care group",
            created_by=self.midwife_user,
            is_private=True,
        )
        GroupMember.objects.create(
            group=group,
            user=self.midwife_user,
            role=GroupMember.Role.ADMIN,
        )
        mother = MotherProfile.objects.create(
            user=self.regular_user,
            mother_id="M-AI-MIDWIFE-OWNER",
        )
        Pregnancy.objects.create(mother=mother)
        GroupMember.objects.create(
            group=group,
            user=self.regular_user,
            role=GroupMember.Role.PATIENT,
        )
        post = GroupPost.objects.create(
            group=group,
            author=self.regular_user,
            content="I have a question for the midwife-led community.",
        )
        self.client.force_login(self.midwife_user)

        response = self.client.post(
            reverse("community:request_mother_summary", args=[group.id, post.id])
        )

        self.assertRedirects(response, reverse("community:group_detail", args=[group.id]))
        self.assertTrue(
            CommunityAIInsight.objects.filter(
                group_post=post,
                kind=CommunityAIInsight.Kind.SUMMARY,
                requested_by=self.midwife_user,
            ).exists()
        )

    def test_non_professional_with_professional_membership_role_cannot_use_ai(self):
        GroupMember.objects.create(
            group=self.group,
            user=self.regular_user,
            role=GroupMember.Role.DOCTOR,
        )
        post = GroupPost.objects.create(
            group=self.group,
            author=self.regular_user,
            content="I have a concern.",
        )
        self.client.force_login(self.regular_user)
        response = self.client.post(
            reverse("community:request_mother_summary", args=[self.group.id, post.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_outside_community_cannot_use_ai(self):
        post = GroupPost.objects.create(
            group=self.group,
            author=self.regular_user,
            content="I have a concern.",
        )
        self.client.force_login(self.doctor_user)
        response = self.client.post(
            reverse("community:request_mother_summary", args=[self.group.id, post.id])
        )
        self.assertEqual(response.status_code, 403)

# Create your tests here.
