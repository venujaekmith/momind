from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Family, HospitalProfile, MotherDetails, MotherProfile, Role
from .models import BabyProfile, Clinics, Pregnancy, PregnancyProgress


class DashboardAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.mother_user = User.objects.create_user(
            username="mother-one",
            email="mother-one@example.com",
            password="safe-test-password",
            role=Role.MOTHER,
            is_role_selected=True,
        )
        self.mother = MotherProfile.objects.create(user=self.mother_user, mother_id="M-ONE")
        MotherDetails.objects.create(user=self.mother_user, mother=self.mother)
        self.pregnancy = Pregnancy.objects.create(
            mother=self.mother,
            last_menstrual_period=timezone.localdate() - timedelta(days=70),
        )

        self.other_user = User.objects.create_user(
            username="mother-two",
            email="mother-two@example.com",
            password="safe-test-password",
            role=Role.MOTHER,
            is_role_selected=True,
        )
        self.other_mother = MotherProfile.objects.create(user=self.other_user, mother_id="M-TWO")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboards:dashboard"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('dashboards:dashboard')}",
        )

    def test_unrelated_user_cannot_view_or_edit_pregnancy(self):
        self.client.force_login(self.other_user)
        detail = self.client.get(
            reverse("dashboards:midwife_mother_detail", args=[self.pregnancy.id])
        )
        self.assertEqual(detail.status_code, 403)
        edit = self.client.post(
            reverse("dashboards:add_progress", args=[self.pregnancy.id]),
            {"week": 10},
        )
        self.assertEqual(edit.status_code, 403)
        self.assertFalse(PregnancyProgress.objects.filter(pregnancy=self.pregnancy).exists())

    def test_clinic_pages_render_and_hide_patient_queue_from_unrelated_users(self):
        hospital_user = get_user_model().objects.create_user(
            username="hospital",
            email="hospital@example.com",
            password="safe-test-password",
            role=Role.HOSPITAL,
            is_role_selected=True,
        )
        hospital = HospitalProfile.objects.create(
            user=hospital_user, hospital_id="H-ONE", name="Central Hospital"
        )
        clinic = Clinics.objects.create(
            hospital=hospital,
            name="Antenatal clinic",
            date=timezone.localdate() + timedelta(days=1),
        )
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(reverse("dashboards:clinic_directory")).status_code, 200)
        response = self.client.get(reverse("dashboards:clinic_detail", args=[clinic.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_manage"])

    def test_water_logging_rejects_invalid_amount(self):
        self.client.force_login(self.mother_user)
        response = self.client.post(reverse("dashboards:log_water"), {"amount": "-5"})
        self.assertRedirects(response, reverse("dashboards:dashboard"))
        self.assertEqual(self.mother.water_logs.count(), 0)

    def test_unrelated_user_cannot_access_baby_ai_record(self):
        baby = BabyProfile.objects.create(
            pregnancy=self.pregnancy,
            name="Baby",
            birth_date=timezone.localdate(),
        )
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("dashboards:babyai", args=[baby.id]))
        self.assertEqual(response.status_code, 403)


class DemoDashboardSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_every_demo_role_dashboard_renders(self):
        usernames = [
            "demo_mother",
            "demo_postpartum",
            "demo_father",
            "demo_midwife",
            "demo_doctor",
            "demo_hospital",
            "demo_staff",
        ]
        for username in usernames:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(
                    self.client.login(username=username, password="MomindDemo2026!")
                )
                response = self.client.get(reverse("dashboards:dashboard"))
                self.assertEqual(response.status_code, 200)

# Create your tests here.
