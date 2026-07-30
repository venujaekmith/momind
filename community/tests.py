from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import HospitalProfile, Role
from dashboards.models import Clinics
from .models import GroupMember, HospitalGroup


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
        self.group.is_private = False
        self.group.save(update_fields=["is_private"])
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("community:group_list"))
        self.assertContains(
            response,
            f'action="{reverse("community:join_group", args=[self.group.id])}"',
            html=False,
        )
        self.assertContains(response, 'method="post"', html=False)

# Create your tests here.
