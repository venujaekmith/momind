from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import FatherProfile, MotherProfile, Role


class AccountFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="new-parent",
            email="new-parent@example.com",
            password="safe-test-password",
        )
        self.client.force_login(self.user)

    def test_invalid_role_is_rejected_without_mutating_user(self):
        response = self.client.post(reverse("accounts:select_role"), {"role": "ADMIN"})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_role_selected)
        self.assertIsNone(self.user.role)

    def test_mother_role_creates_profile_and_cannot_be_changed(self):
        response = self.client.post(reverse("accounts:select_role"), {"role": Role.MOTHER})
        self.assertRedirects(response, reverse("accounts:mother_details"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_role_selected)
        self.assertTrue(MotherProfile.objects.filter(user=self.user).exists())

        response = self.client.post(reverse("accounts:select_role"), {"role": Role.FATHER})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboards:dashboard"))
        self.assertFalse(FatherProfile.objects.filter(user=self.user).exists())

    def test_father_details_updates_existing_profile(self):
        self.user.role = Role.FATHER
        self.user.is_role_selected = True
        self.user.save(update_fields=["role", "is_role_selected"])
        profile = FatherProfile.objects.create(user=self.user, father_id="F-TEST")
        mother_user = get_user_model().objects.create_user(
            username="mother", email="mother@example.com", password="password"
        )
        mother = MotherProfile.objects.create(user=mother_user, mother_id="M-TEST")

        response = self.client.post(
            reverse("accounts:father_details"),
            {"linked_mother": mother.id},
        )
        self.assertRedirects(response, reverse("dashboards:dashboard"))
        profile.refresh_from_db()
        self.assertEqual(profile.linked_mother, mother)
        self.assertEqual(FatherProfile.objects.filter(user=self.user).count(), 1)

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(
            self.client.post(reverse("accounts:logout")),
            reverse("accounts:login"),
        )


class AccountTemplateSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_public_account_pages_render(self):
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:register")).status_code, 200)

    def test_every_role_details_page_renders(self):
        routes = {
            "demo_mother": "accounts:mother_details",
            "demo_father": "accounts:father_details",
            "demo_midwife": "accounts:midwife_details",
            "demo_doctor": "accounts:doctor_details",
            "demo_hospital": "accounts:hospital_details",
            "demo_staff": "accounts:hospital_staff_details",
        }
        User = get_user_model()
        for username, route in routes.items():
            with self.subTest(username=username):
                self.client.force_login(User.objects.get(username=username))
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)
