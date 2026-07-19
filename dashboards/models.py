from django.db import models
from accounts.models import *
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL
# Create your models here.

class KickCount(models.Model):
    mother = models.ForeignKey(MotherProfile, on_delete=models.CASCADE, related_name="kicks")
    count = models.PositiveIntegerField()
    session_start = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.mother.user.username} - {self.count} kicks on {self.session_start.date()}"


class WaterIntake(models.Model):
    mother = models.ForeignKey(MotherProfile, on_delete=models.CASCADE, related_name="water_logs")
    amount_ml = models.PositiveIntegerField() # e.g., 250 for a glass
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class WeightLog(models.Model):
    mother = models.ForeignKey(MotherProfile, on_delete=models.CASCADE, related_name="weight_logs")
    weight = models.DecimalField(max_digits=5, decimal_places=2) # e.g., 65.50
    date = models.DateField(auto_now_add=True) 



class MotherWeightRecord(models.Model):

    mother = models.ForeignKey(
        MotherProfile,
        on_delete=models.CASCADE,
        related_name="weight_records"
    )

    weight_kg = models.FloatField()

    recorded_at = models.DateTimeField(auto_now_add=True)

    recorded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    notes = models.CharField(max_length=255, blank=True)


class Pregnancy(models.Model):
    mother = models.ForeignKey("accounts.MotherProfile", on_delete=models.CASCADE, related_name="pregnancies")

    pregnancy_number = models.IntegerField(default=1)  # 1st, 2nd, etc.

    is_active = models.BooleanField(default=True)

    last_menstrual_period = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)

    pre_pregnancy_weight = models.FloatField(null=True, blank=True)
    is_high_risk = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("ongoing", "Ongoing"),
            ("delivered", "Delivered"),
            ("completed", "Completed"),
        ],
        default="ongoing"
    )
    actual_delivery_date = models.DateField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def end_pregnancy(self, actual_delivery_date=None):
        self.is_active = False
        self.status = "delivered"
        self.actual_delivery_date = actual_delivery_date or timezone.now().date()
        self.ended_at = timezone.now()
        self.save()
        return self
    
    def get_pregnancy_week(self):
        if self.last_menstrual_period:
            delta = date.today() - self.last_menstrual_period
            weeks = delta.days // 7
            return max(0, min(weeks, 42))  # clamp between 0–42 weeks

        return None

class BabyProfile(models.Model):
    pregnancy = models.ForeignKey(
        "Pregnancy", 
        on_delete=models.CASCADE, 
        related_name="babies"   # Now plural: pregnancy.babies.all()
    )
    
    name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(
        max_length=20, 
        choices=[("male", "Male"), ("female", "Female"), ("unknown", "Unknown")], 
        default="unknown"
    )
    birth_date = models.DateField(null=True, blank=True)
    birth_weight_kg = models.FloatField(null=True, blank=True)
    birth_height_cm = models.FloatField(null=True, blank=True)
    
    is_alive = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name or 'Baby'} of {self.pregnancy.mother.user.username} ID:{self.id}"

    # Keep your age methods here
    def get_age_in_weeks(self):
        if not self.birth_date:
            return None
        delta = date.today() - self.birth_date
        return max(0, delta.days // 7)

    def get_age_display(self):
        if not self.birth_date:
            return "Not born yet"
        days = (date.today() - self.birth_date).days
        weeks = days // 7
        extra_days = days % 7
        if weeks == 0:
            return f"{extra_days} days old"
        return f"{weeks} weeks {extra_days} days old"
    
class BabyDevelopmentRecord(models.Model):
    baby = models.ForeignKey(
        BabyProfile, 
        on_delete=models.CASCADE, 
        related_name="development_records"
    )
    
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL
    )
    
    # Growth Measurements
    age_in_weeks = models.IntegerField(help_text="Baby's age in weeks at recording")
    weight_kg = models.FloatField(null=True, blank=True)
    height_cm = models.FloatField(null=True, blank=True)
    head_circumference_cm = models.FloatField(null=True, blank=True)
    
    # Health & Development
    feeding_type = models.CharField(
        max_length=30,
        choices=[
            ("breastfeeding", "Breastfeeding"),
            ("formula", "Formula"),
            ("mixed", "Mixed"),
            ("other", "Other")
        ],
        blank=True
    )
    
    milestones_achieved = models.TextField(blank=True, help_text="e.g., smiles, holds head, coos, etc.")
    concerns = models.TextField(blank=True, help_text="Any developmental concerns")
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-recorded_at']
        verbose_name = "Baby Development Record"

    def save(self, *args, **kwargs):
        if self.baby and self.baby.birth_date and not self.age_in_weeks:
            self.age_in_weeks = self.baby.get_age_in_weeks()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.baby} - Week {self.age_in_weeks} ({self.recorded_at.date()})"
    

class PregnancyProgress(models.Model):

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="progress")

    week = models.IntegerField()

    weight = models.FloatField(null=True, blank=True)
    bp_systolic = models.IntegerField(null=True, blank=True)
    bp_diastolic = models.IntegerField(null=True, blank=True)

    baby_heart_rate = models.IntegerField(null=True, blank=True)

    symptoms = models.TextField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    recorded_at = models.DateTimeField(auto_now_add=True)

    recorded_by = models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL)


class FetalHealth(models.Model):
   

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="fetal_records")

    week = models.IntegerField()

    heart_rate = models.IntegerField(null=True, blank=True)

    movement_level = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
        ],
        default="normal"
    )

    growth_status = models.CharField(max_length=50, null=True, blank=True)

    recorded_at = models.DateTimeField(auto_now_add=True)

    recorded_by = models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL)


class LabTest(models.Model):
    

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="lab_tests")

    test_name = models.CharField(max_length=100)

    result_value = models.CharField(max_length=100)

    unit = models.CharField(max_length=20, null=True, blank=True)

    normal_range = models.CharField(max_length=50, null=True, blank=True)

    is_abnormal = models.BooleanField(default=False)

    taken_date = models.DateField()

    recorded_by = models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL)


def lab_attachment_path(instance, filename):
    return f"labs_attachments/{instance.post.pregnancy.mother.user.username}/{filename}"


class LabAttachment(models.Model):

    post = models.ForeignKey(
        LabTest,
        on_delete=models.CASCADE,
        related_name='attachments'
    )

    file = models.FileField(upload_to=lab_attachment_path)

    uploaded_at = models.DateTimeField(auto_now_add=True)


class EmergencyAlert(models.Model):
   

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="alerts")

    alert_type = models.CharField(
        max_length=50,
        choices=[
            ("bleeding", "Bleeding"),
            ("high_bp", "High Blood Pressure"),
            ("no_movement", "No Fetal Movement"),
            ("pain", "Severe Pain"),
            ("other", "Other"),
        ]
    )

    message = models.TextField()

    is_resolved = models.BooleanField(default=False)

    triggered_by_ai = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
   

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")

    title = models.CharField(max_length=100)
    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

class Medication(models.Model):
    

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE)

    name = models.CharField(max_length=100)

    dosage = models.CharField(max_length=50)

    frequency = models.CharField(max_length=50)

    start_date = models.DateField()

    end_date = models.DateField(null=True, blank=True)

class Vaccination(models.Model):
    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name='vaccinations')
    vaccine_name = models.CharField(max_length=100)  # e.g., Tetanus Toxoid
    dose_number = models.IntegerField()
    date_given = models.DateField()
    given_by = models.CharField(max_length=150, blank=True)  # Doctor or Midwife name

    def __str__(self):
        return f"{self.vaccine_name} Dose {self.dose_number}"

class MoHVisit(models.Model):
    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name='visits')
    visit_date = models.DateField()
    gestational_age = models.IntegerField(help_text="Weeks")  # POA in weeks
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    blood_pressure = models.CharField(max_length=20, blank=True)  # e.g., 120/80
    sfh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Symphysio-Fundal Height")
    fetal_heart_rate = models.IntegerField(null=True, blank=True)
    urine_sugar = models.CharField(max_length=20, blank=True)
    urine_albumin = models.CharField(max_length=20, blank=True)
    complaints = models.TextField(blank=True)
    advice = models.TextField(blank=True)
    
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, null=True, blank=True)
    midwife = models.ForeignKey(MidwifeProfile, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-visit_date']

    def __str__(self):
        return f"Visit at {self.gestational_age} weeks - {self.visit_date}"

#include in ai
class RiskAssessment(models.Model):
    
    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="risks")

    risk_score = models.FloatField(default=0.0)

    risk_level = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="low"
    )

    factors = models.JSONField(default=dict)  # AI explanations

    prediction_model_version = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class TrimesterPlan(models.Model):
    pregnancy = models.OneToOneField(
        "Pregnancy",
        on_delete=models.CASCADE,
        related_name="trimester_plan"
    )

    current_trimester = models.IntegerField(default=1)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def update_trimester(self):
        week = self.pregnancy.get_pregnancy_week()

        if week is None:
            self.current_trimester = 1
        elif week <= 13:
            self.current_trimester = 1
        elif week <= 27:
            self.current_trimester = 2
        else:
            self.current_trimester = 3

        self.save()

class MidwifeVisit(models.Model):
    pregnancy = models.ForeignKey(
        "Pregnancy",
        on_delete=models.CASCADE,
        related_name="midwife_visits"
    )

    scheduled_date = models.DateField()
    completed = models.BooleanField(default=False)

    trimester = models.IntegerField()

    visit_type = models.CharField(
        max_length=50,
        choices=[
            ("routine", "Routine Checkup"),
            ("growth", "Growth Check"),
            ("risk", "Risk Review"),
            ("lab", "Lab Follow-up"),
        ],
        default="routine"
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def mark_completed(self):
        self.completed = True
        self.save()

class ClinicalMilestone(models.Model):
    pregnancy = models.ForeignKey(
        "Pregnancy",
        on_delete=models.CASCADE,
        related_name="milestones"
    )

    title = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    week_due = models.IntegerField()

    is_completed = models.BooleanField(default=False)

    completed_at = models.DateTimeField(null=True, blank=True)

    auto_generated = models.BooleanField(default=True)


class Clinics(models.Model):
    hospital = models.ForeignKey(
        "accounts.HospitalProfile",
        on_delete=models.CASCADE,
        related_name="clinics"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=20)
    is_active = models.BooleanField(default=True)
    staff = models.ManyToManyField(
        "accounts.HospitalStaffProfile",
        blank=True,
        related_name="clinics"
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_clinics"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date','time']

    def __str__(self):
        return f"{self.name} @ {self.hospital.name} on {self.date}"

    def queue_count(self):
        return self.appointments.filter(
            event_type="hospital_clinic",
            scheduled_date=self.date
        ).count()


class ScheduleEvent(models.Model):
    """General scheduling for visits, clinics, ultrasounds, etc."""
    EVENT_TYPES = [
        ("midwife_visit", "Midwife Visit"),
        ("doctor_appointment", "Doctor Appointment"),
        ("hospital_clinic", "Hospital Clinic"),
        ("ultrasound", "Ultrasound Scan"),
        ("lab_test", "Lab Test Appointment"),
        ("milestone", "Important Milestone"),
        ("other", "Other"),
    ]

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="schedule_events")
    
    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, default="midwife_visit")
    
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    clinic = models.ForeignKey(
        'Clinics',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='appointments'
    )
    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    what_to_bring = models.TextField(blank=True, help_text="Items mother should bring")
    
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_events")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'scheduled_time']

    def __str__(self):
        return f"{self.title} - {self.scheduled_date}"

    def mark_completed(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save()


class TrimesterTask(models.Model):
    """Automated tasks/milestones per trimester"""
    TRIMESTER_CHOICES = [(1, "First"), (2, "Second"), (3, "Third")]

    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="trimester_tasks")
    trimester = models.IntegerField(choices=TRIMESTER_CHOICES)
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    week_range = models.CharField(max_length=50)  # e.g., "Weeks 1-4"
    
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    def mark_completed(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save()

# models.py
class VisitNote(models.Model):
    """Midwife notes during each visit"""
    pregnancy = models.ForeignKey(Pregnancy, on_delete=models.CASCADE, related_name="visit_notes")
    scheduled_event = models.ForeignKey('ScheduleEvent', null=True, blank=True, on_delete=models.SET_NULL)
    
    visit_date = models.DateField()
    notes = models.TextField()
    findings = models.TextField(blank=True)          # e.g., BP, Weight, Fundal height
    recommendations = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-visit_date']

# notifications when linking someone to familiy. 
class Link_notification(models.Model):
    linker = models.ForeignKey(User,on_delete=models.CASCADE,related_name="user_linker_request")
    linker_type = models.CharField(max_length=20)
    link = models.ForeignKey(User,on_delete=models.CASCADE,related_name="user_link_request")
    link_type = models.CharField(max_length=20)
    # Free-form note supplied by requester (e.g., message to the target)
    note = models.TextField(null=True,blank=True)
    # Identifier for the member being requested (e.g., MID-12345)
    member_identifier = models.CharField(max_length=100, null=True, blank=True)
    accepted = models.BooleanField(default=False)