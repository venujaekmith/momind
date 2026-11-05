"""Create a small, repeatable data set for demos and manual testing."""

from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    DoctorProfile,
    Family,
    FatherProfile,
    HospitalProfile,
    HospitalStaffProfile,
    MidwifeProfile,
    MotherDetails,
    MotherProfile,
    Role,
    User,
)
from community.models import (
    ClinicSchedule,
    CommunityNotification,
    ForumCategory,
    ForumComment,
    ForumPost,
    ForumReaction,
    ForumSubscription,
    GroupMember,
    GroupPost,
    HospitalGroup,
    HospitalGroupSubscription,
)
from dashboards.models import (
    BabyDevelopmentRecord,
    BabyProfile,
    ClinicalMilestone,
    Clinics,
    FetalHealth,
    KickCount,
    LabTest,
    Medication,
    MidwifeVisit,
    MoHVisit,
    MotherWeightRecord,
    Notification,
    Pregnancy,
    PregnancyProgress,
    RiskAssessment,
    ScheduleEvent,
    TrimesterPlan,
    TrimesterTask,
    Vaccination,
    VisitNote,
    WaterIntake,
)
from postpartum.models import (
    AIStressAssessment,
    BreathingExercise,
    Conversation,
    DailyTip,
    JournalEntry,
    Message,
    MoodEntry,
    PostpartumProfile,
    StressAssessment,
    StressLog,
)


DEMO_PASSWORD = "MomindDemo2026!"


class Command(BaseCommand):
    help = "Seed realistic, idempotent Momind demo data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEMO_PASSWORD,
            help="Password assigned to all demo accounts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        today = timezone.localdate()

        mother_user = self._user("demo_mother", Role.MOTHER, "Nadeesha", "Perera", password)
        postpartum_user = self._user(
            "demo_postpartum", Role.MOTHER, "Amaya", "Fernando", password
        )
        father_user = self._user("demo_father", Role.FATHER, "Kasun", "Perera", password)
        midwife_user = self._user(
            "demo_midwife", Role.MIDWIFE, "Tharushi", "Silva", password
        )
        doctor_user = self._user("demo_doctor", Role.DOCTOR, "Anjali", "Jayasinghe", password)
        hospital_user = self._user(
            "demo_hospital", Role.HOSPITAL, "Serenity", "Hospital", password
        )
        staff_user = self._user(
            "demo_staff", Role.HOSPITAL_STAFF, "Malith", "De Alwis", password
        )

        hospital, _ = HospitalProfile.objects.update_or_create(
            user=hospital_user,
            defaults={
                "hospital_id": "H-DEMO-001",
                "name": "Serenity Women and Children Hospital",
                "is_verified": True,
                "contact_number": "+94 11 234 5678",
                "district": "Colombo",
                "address": "42 Flower Road, Colombo 07",
            },
        )
        doctor, _ = DoctorProfile.objects.update_or_create(
            user=doctor_user,
            defaults={
                "doctor_id": "DR-DEMO-001",
                "hospital": hospital,
                "is_verified": True,
                "designation": "Consultant Obstetrician",
            },
        )
        midwife, _ = MidwifeProfile.objects.update_or_create(
            user=midwife_user,
            defaults={
                "midwife_id": "MW-DEMO-001",
                "license_no": "SLMC-MW-2048",
                "is_verified": True,
                "phm_area": "Colombo Central",
                "moh_area": "Colombo Municipal Council",
            },
        )
        staff, _ = HospitalStaffProfile.objects.update_or_create(
            user=staff_user,
            defaults={
                "staff_id": "HS-DEMO-001",
                "hospital": hospital,
                "role_title": "Maternity Clinic Coordinator",
                "is_active": True,
            },
        )
        mother, _ = MotherProfile.objects.update_or_create(
            user=mother_user,
            defaults={"mother_id": "M-DEMO-001", "pregnancy_week": 28},
        )
        postpartum_mother, _ = MotherProfile.objects.update_or_create(
            user=postpartum_user,
            defaults={"mother_id": "M-DEMO-002", "pregnancy_week": 40},
        )
        father, _ = FatherProfile.objects.update_or_create(
            user=father_user,
            defaults={"father_id": "F-DEMO-001", "linked_mother": mother},
        )

        MotherDetails.objects.update_or_create(
            user=mother_user,
            defaults={
                "mother": mother,
                "height_cm": 162,
                "blood_group": "O+",
                "has_diabetes": False,
                "has_hypertension": False,
                "previous_pregnancies": 0,
                "home_latitude": 6.9271,
                "home_longitude": 79.8612,
            },
        )
        MotherDetails.objects.update_or_create(
            user=postpartum_user,
            defaults={
                "mother": postpartum_mother,
                "height_cm": 158,
                "blood_group": "A+",
                "has_diabetes": False,
                "has_hypertension": False,
                "previous_pregnancies": 1,
            },
        )

        pregnancy, _ = Pregnancy.objects.update_or_create(
            mother=mother,
            pregnancy_number=1,
            defaults={
                "is_active": True,
                "status": "ongoing",
                "last_menstrual_period": today - timedelta(weeks=28, days=2),
                "expected_delivery_date": today + timedelta(weeks=11, days=5),
                "pre_pregnancy_weight": 58.5,
                "is_high_risk": False,
            },
        )
        family, _ = Family.objects.update_or_create(
            pregnancy=pregnancy,
            defaults={
                "mother": mother,
                "father": father,
                "midwife": midwife,
                "doctor": doctor,
                "hospital": hospital,
            },
        )
        del family

        clinic, _ = Clinics.objects.update_or_create(
            hospital=hospital,
            name="Tuesday Antenatal Clinic",
            defaults={
                "description": "Routine antenatal reviews, growth checks, and education.",
                "location": "Maternity Wing — Level 2",
                "date": today + timedelta(days=2),
                "time": time(9, 0),
                "capacity": 24,
                "is_active": True,
                "created_by": hospital_user,
            },
        )
        clinic.staff.add(staff)

        progress = [
            (16, 61.2, 112, 72, 148, "Mild nausea", "Growth is on track."),
            (20, 63.0, 114, 74, 150, "Occasional backache", "Anomaly scan normal."),
            (24, 65.1, 116, 76, 146, "Good energy", "Continue daily walking."),
            (28, 67.0, 118, 78, 144, "Mild ankle swelling", "Hydration and rest advised."),
        ]
        for week, weight, sys, dia, heart, symptoms, notes in progress:
            PregnancyProgress.objects.update_or_create(
                pregnancy=pregnancy,
                week=week,
                defaults={
                    "weight": weight,
                    "bp_systolic": sys,
                    "bp_diastolic": dia,
                    "baby_heart_rate": heart,
                    "symptoms": symptoms,
                    "notes": notes,
                    "recorded_by": midwife_user,
                },
            )
            FetalHealth.objects.update_or_create(
                pregnancy=pregnancy,
                week=week,
                defaults={
                    "heart_rate": heart,
                    "movement_level": "normal",
                    "growth_status": "Appropriate for gestational age",
                    "recorded_by": doctor_user,
                },
            )

        for test_name, value, unit, normal, abnormal, days_ago in [
            ("Haemoglobin", "11.8", "g/dL", "11.0–15.0", False, 8),
            ("Fasting blood glucose", "82", "mg/dL", "70–99", False, 8),
            ("Urine protein", "Negative", "", "Negative", False, 3),
        ]:
            LabTest.objects.update_or_create(
                pregnancy=pregnancy,
                test_name=test_name,
                taken_date=today - timedelta(days=days_ago),
                defaults={
                    "result_value": value,
                    "unit": unit,
                    "normal_range": normal,
                    "is_abnormal": abnormal,
                    "recorded_by": doctor_user,
                },
            )

        for title, event_type, days, event_time, location in [
            ("Antenatal clinic review", "hospital_clinic", 2, time(9, 30), clinic.location),
            ("Growth ultrasound", "ultrasound", 9, time(10, 15), "Imaging Centre — Level 1"),
            ("Midwife home visit", "midwife_visit", 16, time(15, 0), "Home"),
        ]:
            ScheduleEvent.objects.update_or_create(
                pregnancy=pregnancy,
                title=title,
                defaults={
                    "event_type": event_type,
                    "scheduled_date": today + timedelta(days=days),
                    "scheduled_time": event_time,
                    "clinic": clinic if event_type == "hospital_clinic" else None,
                    "location": location,
                    "notes": "Demo appointment generated by seed_demo.",
                    "what_to_bring": "Pregnancy record, recent reports, and water bottle",
                    "created_by": staff_user,
                },
            )

        for title, description, week_range, done in [
            ("Complete anomaly scan", "Review baby's anatomy and growth.", "Weeks 18–22", True),
            ("Track daily movement", "Notice and record the baby's usual movement pattern.", "Weeks 24–28", True),
            ("Prepare a birth plan", "Discuss preferences with the care team.", "Weeks 28–32", False),
            ("Attend breastfeeding class", "Learn positioning, latch, and early feeding cues.", "Weeks 30–34", False),
        ]:
            TrimesterTask.objects.update_or_create(
                pregnancy=pregnancy,
                title=title,
                defaults={
                    "trimester": 2 if "18" in week_range or "24" in week_range else 3,
                    "description": description,
                    "week_range": week_range,
                    "is_completed": done,
                },
            )

        TrimesterPlan.objects.update_or_create(
            pregnancy=pregnancy, defaults={"current_trimester": 3}
        )
        RiskAssessment.objects.update_or_create(
            pregnancy=pregnancy,
            prediction_model_version="demo-1.0",
            defaults={
                "risk_score": 12.0,
                "risk_level": "low",
                "factors": {
                    "blood_pressure": "normal",
                    "glucose": "normal",
                    "fetal_growth": "on_track",
                },
            },
        )
        Vaccination.objects.update_or_create(
            pregnancy=pregnancy,
            vaccine_name="Tetanus-diphtheria",
            dose_number=1,
            defaults={"date_given": today - timedelta(days=35), "given_by": "MW Tharushi Silva"},
        )
        Medication.objects.update_or_create(
            pregnancy=pregnancy,
            name="Prenatal multivitamin",
            defaults={
                "dosage": "1 tablet",
                "frequency": "Once daily after breakfast",
                "start_date": today - timedelta(weeks=20),
            },
        )
        MidwifeVisit.objects.update_or_create(
            pregnancy=pregnancy,
            scheduled_date=today + timedelta(days=16),
            defaults={
                "completed": False,
                "trimester": 3,
                "visit_type": "routine",
                "notes": "Review movement chart and birth-preparation checklist.",
            },
        )
        ClinicalMilestone.objects.update_or_create(
            pregnancy=pregnancy,
            title="Third trimester begins",
            defaults={
                "description": "Begin final-trimester monitoring and birth preparation.",
                "week_due": 28,
                "is_completed": True,
            },
        )
        MoHVisit.objects.update_or_create(
            pregnancy=pregnancy,
            visit_date=today - timedelta(days=3),
            defaults={
                "gestational_age": 28,
                "weight": 67,
                "blood_pressure": "118/78",
                "sfh": 28,
                "fetal_heart_rate": 144,
                "urine_sugar": "Negative",
                "urine_albumin": "Negative",
                "complaints": "Mild ankle swelling in the evening.",
                "advice": "Rest with feet elevated and maintain hydration.",
                "doctor": doctor,
                "midwife": midwife,
            },
        )
        VisitNote.objects.update_or_create(
            pregnancy=pregnancy,
            visit_date=today - timedelta(days=3),
            defaults={
                "notes": "Mother and baby are progressing well.",
                "findings": "BP 118/78, weight 67 kg, fetal heart rate 144 bpm.",
                "recommendations": "Continue supplements, movement tracking, and gentle exercise.",
                "recorded_by": midwife_user,
            },
        )

        self._seed_activity(mother, mother_user, midwife_user, today)
        self._seed_community(
            mother_user, postpartum_user, father_user, midwife_user, doctor_user,
            hospital, hospital_user, clinic, today
        )
        self._seed_postpartum(postpartum_mother, postpartum_user, doctor_user, today)

        self.stdout.write(self.style.SUCCESS("Momind demo data is ready."))
        self.stdout.write(f"Password for every demo account: {password}")
        self.stdout.write(
            "Users: demo_mother, demo_postpartum, demo_father, demo_midwife, "
            "demo_doctor, demo_hospital, demo_staff"
        )

    def _user(self, username, role, first_name, last_name, password):
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                "email": f"{username}@momind.demo",
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "is_role_selected": True,
                "is_active": True,
            },
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        return user

    def _seed_activity(self, mother, mother_user, midwife_user, today):
        WaterIntake.objects.filter(mother=mother).delete()
        for amount, hours_ago in [(300, 1), (250, 3), (300, 5), (250, 7), (300, 9)]:
            item = WaterIntake.objects.create(mother=mother, amount_ml=amount)
            WaterIntake.objects.filter(pk=item.pk).update(
                timestamp=timezone.now() - timedelta(hours=hours_ago)
            )

        KickCount.objects.filter(mother=mother).delete()
        for count, duration, days_ago in [(10, 18, 0), (10, 22, 1), (10, 19, 2)]:
            item = KickCount.objects.create(mother=mother, count=count, duration_minutes=duration)
            KickCount.objects.filter(pk=item.pk).update(
                session_start=timezone.now() - timedelta(days=days_ago)
            )

        MotherWeightRecord.objects.update_or_create(
            mother=mother,
            notes="Routine antenatal measurement",
            defaults={"weight_kg": 67.0, "recorded_by": midwife_user},
        )
        for title, message, is_read in [
            ("Upcoming clinic", "Your antenatal clinic is in 2 days at 9:30 AM.", False),
            ("Healthy movement pattern", "Today's kick count is within your usual range.", False),
            ("Lab results ready", "Your latest routine lab results are available.", True),
        ]:
            Notification.objects.update_or_create(
                user=mother_user,
                title=title,
                defaults={"message": message, "is_read": is_read},
            )

    def _seed_community(
        self, mother_user, postpartum_user, father_user, midwife_user, doctor_user,
        hospital, hospital_user, clinic, today
    ):
        categories = {}
        for name, description in [
            ("Pregnancy Support", "Questions, encouragement, and shared pregnancy experiences."),
            ("Newborn Care", "Practical support for baby's first months."),
            ("Mental Wellness", "A kind space for emotional wellbeing and self-care."),
        ]:
            categories[name], _ = ForumCategory.objects.update_or_create(
                name=name, defaults={"description": description}
            )

        posts = []
        for author, category, title, content, anonymous in [
            (
                mother_user, categories["Pregnancy Support"],
                "What helped you prepare for the third trimester?",
                "I have just reached week 28. I would love practical tips for staying comfortable and preparing for the next few weeks.",
                False,
            ),
            (
                postpartum_user, categories["Newborn Care"],
                "A small win with our bedtime routine",
                "A warm bath, dim lights, and feeding in a quiet room helped us settle into a gentler evening rhythm.",
                False,
            ),
            (
                mother_user, categories["Mental Wellness"],
                "Remembering to rest without feeling guilty",
                "Sharing a reminder that rest is part of caring for ourselves and our babies.",
                True,
            ),
        ]:
            post, _ = ForumPost.objects.update_or_create(
                author=author,
                title=title,
                defaults={
                    "category": category,
                    "content": content,
                    "is_anonymous": anonymous,
                },
            )
            posts.append(post)

        ForumComment.objects.update_or_create(
            post=posts[0],
            author=midwife_user,
            defaults={
                "content": "A birth-preparation list, gentle daily movement, and asking questions at each visit can make this stage feel much more manageable."
            },
        )
        ForumComment.objects.update_or_create(
            post=posts[0],
            author=postpartum_user,
            defaults={"content": "A supportive pillow and preparing a few freezer meals helped me a lot."},
        )
        ForumReaction.objects.update_or_create(
            user=father_user, post=posts[0], defaults={"reaction": "SUPPORT"}
        )
        ForumReaction.objects.update_or_create(
            user=doctor_user, post=posts[0], defaults={"reaction": "LOVE"}
        )
        ForumSubscription.objects.get_or_create(
            user=mother_user, forum=categories["Pregnancy Support"]
        )

        group, _ = HospitalGroup.objects.update_or_create(
            hospital=hospital,
            name="Serenity Antenatal Circle",
            defaults={
                "description": "Clinic updates and moderated support for Serenity maternity patients.",
                "created_by": hospital_user,
                "is_private": False,
            },
        )
        for user, role in [
            (hospital_user, "ADMIN"),
            (doctor_user, "DOCTOR"),
            (mother_user, "PATIENT"),
            (postpartum_user, "PATIENT"),
        ]:
            GroupMember.objects.update_or_create(
                group=group, user=user, defaults={"role": role}
            )
        GroupPost.objects.update_or_create(
            group=group,
            author=hospital_user,
            content="This week's antenatal clinic begins at 9:00 AM. Please arrive 15 minutes early with your pregnancy record.",
        )
        HospitalGroupSubscription.objects.get_or_create(
            user=mother_user, hospital_group=group
        )

        schedule, _ = ClinicSchedule.objects.update_or_create(
            hospital=hospital,
            title="Antenatal Education and Review",
            scheduled_date=today + timedelta(days=2),
            defaults={
                "description": "Routine review followed by a short birth-preparation session.",
                "start_time": time(9),
                "end_time": time(12),
                "location": clinic.location,
                "specialization": "Maternal Care",
                "max_patients": 24,
                "available_slots": 7,
                "created_by": hospital_user,
            },
        )
        CommunityNotification.objects.update_or_create(
            user=mother_user,
            title="Clinic reminder",
            defaults={
                "notification_type": "clinic_schedule",
                "message": "Antenatal Education and Review is scheduled in 2 days.",
                "hospital_group": group,
                "clinic_schedule": schedule,
                "is_read": False,
            },
        )

    def _seed_postpartum(self, mother, user, doctor_user, today):
        pregnancy, _ = Pregnancy.objects.update_or_create(
            mother=mother,
            pregnancy_number=1,
            defaults={
                "is_active": False,
                "status": "delivered",
                "last_menstrual_period": today - timedelta(weeks=46),
                "expected_delivery_date": today - timedelta(weeks=6),
                "actual_delivery_date": today - timedelta(weeks=6),
                "pre_pregnancy_weight": 55.0,
            },
        )
        baby, _ = BabyProfile.objects.update_or_create(
            pregnancy=pregnancy,
            name="Mihira",
            defaults={
                "gender": "male",
                "birth_date": today - timedelta(weeks=6),
                "birth_weight_kg": 3.2,
                "birth_height_cm": 50.0,
                "notes": "Healthy full-term delivery.",
            },
        )
        BabyDevelopmentRecord.objects.update_or_create(
            baby=baby,
            age_in_weeks=6,
            defaults={
                "recorded_by": doctor_user,
                "weight_kg": 4.7,
                "height_cm": 55,
                "head_circumference_cm": 38,
                "feeding_type": "breastfeeding",
                "milestones_achieved": "Tracks faces, responds to familiar voices, brief social smiles.",
                "notes": "Healthy growth and development.",
            },
        )
        PostpartumProfile.objects.update_or_create(
            pregnancy=pregnancy,
            defaults={
                "user": user,
                "delivery_date": today - timedelta(weeks=6),
                "delivery_type": "normal",
                "baby_count": 1,
                "current_week": 6,
            },
        )

        MoodEntry.objects.filter(user=user).delete()
        for days_ago, mood, energy, sleep, feelings in [
            (0, 8, 7, 6.5, "Calm and more confident today."),
            (1, 7, 6, 5.5, "A little tired but well supported."),
            (2, 6, 5, 5.0, "Busy day; took a short rest in the afternoon."),
            (3, 8, 7, 6.0, "Enjoyed a peaceful walk with the baby."),
            (4, 7, 6, 5.5, "Feeling grateful and hopeful."),
        ]:
            item = MoodEntry.objects.create(
                user=user,
                mood_score=mood,
                energy_level=energy,
                sleep_hours=sleep,
                feelings=feelings,
            )
            MoodEntry.objects.filter(pk=item.pk).update(date=today - timedelta(days=days_ago))

        JournalEntry.objects.update_or_create(
            user=user,
            title="Six weeks together",
            defaults={
                "content": "We are learning each other's rhythms. Today I noticed how much more confident I feel responding to Mihira's cues.",
                "mood": 8,
            },
        )
        StressLog.objects.update_or_create(
            user=user,
            trigger="Interrupted sleep",
            defaults={
                "stress_level": 4,
                "coping_method": "Shared the early-morning feed routine and took a restorative nap.",
                "notes": "Felt noticeably better after resting.",
            },
        )
        AIStressAssessment.objects.update_or_create(
            user=user,
            q4_writing="I feel supported, though sleep is still inconsistent.",
            defaults={
                "q1_mood": 8,
                "q2_sleep": 6,
                "q3_feeling": "Hopeful and a little tired",
                "q5_drawing_desc": "A sunrise over a quiet garden",
                "stress_score": 28,
                "insight": "Current stress appears manageable with good protective support.",
                "recommendation": "Continue sharing care, protect one daily rest period, and check in with your care team if mood changes persist.",
            },
        )
        for title, description, seconds, instruction in [
            (
                "Three-minute calming breath",
                "A gentle reset for busy moments.",
                180,
                "Inhale for four counts, pause briefly, and exhale for six counts.",
            ),
            (
                "Bedtime body release",
                "Slow breathing and a simple body scan before sleep.",
                300,
                "Relax the jaw and shoulders, then breathe slowly while scanning from head to toes.",
            ),
        ]:
            BreathingExercise.objects.update_or_create(
                title=title,
                defaults={
                    "description": description,
                    "duration_seconds": seconds,
                    "instruction": instruction,
                    "is_sinhala": False,
                },
            )
        for tip_type, title, content in [
            ("physical", "Recovery is not a race", "Increase activity gradually and allow time for rest."),
            ("mental", "A two-minute check-in", "Name one feeling and one thing you need today."),
            ("nutrition", "Keep nourishment easy", "Prepare simple snacks and keep water nearby during feeds."),
            ("baby_care", "Follow your baby's cues", "Early feeding cues include stirring, rooting, and hands near the mouth."),
        ]:
            DailyTip.objects.update_or_create(
                week=6,
                tip_type=tip_type,
                defaults={"title": title, "content": content},
            )
        conversation, _ = Conversation.objects.update_or_create(
            user=user, is_active=True
        )
        Message.objects.get_or_create(
            conversation=conversation,
            role="user",
            content="I am doing better, but I still feel tired after interrupted sleep.",
        )
        Message.objects.get_or_create(
            conversation=conversation,
            role="assistant",
            content="That sounds understandable at six weeks postpartum. Let us look at one small way to protect your rest today.",
        )
        StressAssessment.objects.update_or_create(
            user=user,
            conversation=conversation,
            defaults={
                "chat_score": 30,
                "overall_score": 30,
                "level": "low",
                "chat_insight": "Mild sleep-related strain with strong support and positive coping.",
                "recommendation": "Continue shared care and regular wellbeing check-ins.",
            },
        )
