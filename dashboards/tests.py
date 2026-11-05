from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    Family,
    FatherProfile,
    HospitalProfile,
    HospitalStaffProfile,
    MotherDetails,
    MotherProfile,
    Role,
)
from .models import BabyProfile, Clinics, Pregnancy, PregnancyProgress, ScheduleEvent
from .views import create_default_pregnancy_schedule


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

    def test_incomplete_role_profile_returns_to_setup(self):
        incomplete = get_user_model().objects.create_user(
            username="incomplete-mother",
            email="incomplete@example.com",
            password="safe-test-password",
            role=Role.MOTHER,
            is_role_selected=True,
        )
        self.client.force_login(incomplete)

        response = self.client.get(reverse("dashboards:dashboard"))

        self.assertRedirects(response, reverse("accounts:mother_details"))
        self.assertTrue(MotherProfile.objects.get(user=incomplete).mother_id)

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

    def test_father_dashboard_uses_selected_pregnancy_and_only_offers_allowed_actions(self):
        father_user = get_user_model().objects.create_user(
            username="father-one",
            email="father-one@example.com",
            password="safe-test-password",
            role=Role.FATHER,
            is_role_selected=True,
        )
        father = FatherProfile.objects.create(
            user=father_user,
            father_id="F-ONE",
            linked_mother=self.mother,
        )
        Family.objects.create(mother=self.mother, father=father, pregnancy=self.pregnancy)
        previous = Pregnancy.objects.create(
            mother=self.mother,
            pregnancy_number=2,
            is_active=False,
            status="delivered",
            actual_delivery_date=timezone.localdate() - timedelta(days=30),
        )
        self.client.force_login(father_user)

        response = self.client.get(
            reverse("dashboards:dashboard"),
            {"pregnancy": previous.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pregnancy"], previous)
        self.assertTrue(response.context["is_postpartum"])
        self.assertContains(response, reverse("dashboards:pregnancy_detail", args=[previous.id]))
        self.assertNotContains(response, reverse("dashboards:end_pregnancy", args=[previous.id]))
        self.assertNotContains(response, reverse("dashboards:add_schedule", args=[previous.id]))

    def test_default_schedule_uses_pregnancy_dates_and_is_idempotent(self):
        self.pregnancy.last_menstrual_period = timezone.localdate() - timedelta(weeks=12)
        self.pregnancy.save(update_fields=["last_menstrual_period"])

        create_default_pregnancy_schedule(self.pregnancy)
        first_count = ScheduleEvent.objects.filter(pregnancy=self.pregnancy).count()
        create_default_pregnancy_schedule(self.pregnancy)

        events = ScheduleEvent.objects.filter(pregnancy=self.pregnancy)
        self.assertGreater(first_count, 0)
        self.assertEqual(events.count(), first_count)
        self.assertFalse(events.filter(scheduled_date__lt=timezone.localdate()).exists())

    def test_invalid_baby_data_does_not_partially_end_pregnancy(self):
        self.client.force_login(self.mother_user)
        response = self.client.post(
            reverse("dashboards:end_pregnancy", args=[self.pregnancy.id]),
            {
                "actual_delivery_date": timezone.localdate().isoformat(),
                "delivery_type": "normal",
                "baby_count": 1,
                "baby_name_0": "Baby",
                "baby_gender_0": "female",
                "birth_weight_0": "not-a-number",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.pregnancy.refresh_from_db()
        self.assertTrue(self.pregnancy.is_active)
        self.assertEqual(self.pregnancy.status, "ongoing")
        self.assertFalse(BabyProfile.objects.filter(pregnancy=self.pregnancy).exists())

    def test_hospital_staff_cannot_edit_unassigned_clinic_or_assign_staff(self):
        hospital_user = get_user_model().objects.create_user(
            username="hospital-secure",
            email="hospital-secure@example.com",
            password="safe-test-password",
            role=Role.HOSPITAL,
            is_role_selected=True,
        )
        hospital = HospitalProfile.objects.create(
            user=hospital_user,
            hospital_id="H-SECURE",
            name="Secure Hospital",
        )
        staff_user = get_user_model().objects.create_user(
            username="staff-secure",
            email="staff-secure@example.com",
            password="safe-test-password",
            role=Role.HOSPITAL_STAFF,
            is_role_selected=True,
        )
        staff = HospitalStaffProfile.objects.create(
            user=staff_user,
            staff_id="HS-SECURE",
            hospital=hospital,
        )
        clinic = Clinics.objects.create(
            hospital=hospital,
            name="Private clinic",
            date=timezone.localdate() + timedelta(days=2),
        )
        self.client.force_login(staff_user)

        self.assertEqual(
            self.client.get(reverse("dashboards:edit_hospital_clinic", args=[clinic.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("dashboards:assign_clinic_staff", args=[clinic.id]),
                {"staff_id": staff.staff_id},
            ).status_code,
            403,
        )


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
