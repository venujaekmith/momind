# models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from django.conf import settings

User = settings.AUTH_USER_MODEL

class PostpartumProfile(models.Model):
    # Keep user for backward compatibility, but make postpartum profile unique per pregnancy.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="postpartum_profiles")
    pregnancy = models.OneToOneField(
        'dashboards.Pregnancy',
        on_delete=models.CASCADE,
        related_name='postpartum_profile',
        null=True,
        blank=True,
    )
    delivery_date = models.DateField(null=True, blank=True)
    delivery_type = models.CharField(max_length=50, choices=[
        ('normal', 'Normal Delivery'),
        ('c_section', 'C-Section'),
        ('other', 'Other')
    ], blank=True)
    baby_count = models.IntegerField(default=1)
    current_week = models.IntegerField(default=0, help_text="Postpartum week")
    
    def save(self, *args, **kwargs):
        if self.delivery_date:
            self.current_week = (date.today() - self.delivery_date).days // 7
        super().save(*args, **kwargs)

    def __str__(self):
        if self.pregnancy:
            return f"Postpartum for pregnancy {self.pregnancy.id} ({self.user.username})"
        return f"{self.user.username}'s Postpartum Profile"


class MoodEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    mood_score = models.IntegerField(choices=[(i, i) for i in range(1, 11)])  # 1-10
    feelings = models.TextField(blank=True)
    sleep_hours = models.FloatField(null=True, blank=True)
    energy_level = models.IntegerField(choices=[(i, i) for i in range(1, 11)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class JournalEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    mood = models.IntegerField(choices=[(i, i) for i in range(1, 11)], null=True)
    date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class BreathingExercise(models.Model):
    title = models.CharField(max_length=150)
    description = models.TextField()
    duration_seconds = models.IntegerField(default=180)
    instruction = models.TextField()
    is_sinhala = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class DailyTip(models.Model):
    week = models.IntegerField()
    title = models.CharField(max_length=200)
    content = models.TextField()
    tip_type = models.CharField(max_length=50, choices=[
        ('physical', 'Physical Recovery'),
        ('mental', 'Mental Health'),
        ('baby_care', 'Baby Care'),
        ('nutrition', 'Nutrition'),
        ('sri_lanka', 'Sri Lankan Traditional')
    ])


class StressLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    stress_level = models.IntegerField(choices=[(i, i) for i in range(1, 11)])
    trigger = models.CharField(max_length=200, blank=True)
    coping_method = models.TextField(blank=True)
    notes = models.TextField(blank=True)

class AIStressAssessment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    
    # Questions & Answers
    q1_mood = models.IntegerField(choices=[(i, str(i)) for i in range(1, 11)], null=True)
    q2_sleep = models.IntegerField(null=True)
    q3_feeling = models.TextField(blank=True)
    q4_writing = models.TextField(blank=True)      # Free writing
    q5_drawing_desc = models.TextField(blank=True) # "Describe what you would draw"
    
    stress_score = models.IntegerField(default=0)   # Calculated by AI (1-100)
    insight = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']


class Message(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class DrawingSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='drawings')
    image_data = models.TextField()  # base64 JPEG
    created_at = models.DateTimeField(auto_now_add=True)
    stress_score = models.IntegerField(null=True, blank=True)
    stress_level = models.CharField(max_length=20, blank=True)
    insight = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']


class StressAssessment(models.Model):
    LEVEL_CHOICES = [('low', 'Low'), ('moderate', 'Moderate'), ('high', 'High')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessments')
    conversation = models.OneToOneField(Conversation, on_delete=models.SET_NULL, null=True, blank=True)
    drawing = models.OneToOneField(DrawingSession, on_delete=models.SET_NULL, null=True, blank=True)
    chat_score = models.IntegerField(null=True, blank=True)
    draw_score = models.IntegerField(null=True, blank=True)
    overall_score = models.IntegerField(null=True, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, blank=True)
    chat_insight = models.TextField(blank=True)
    draw_insight = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def compute_overall(self):
        scores = [s for s in [self.chat_score, self.draw_score] if s is not None]
        if scores:
            self.overall_score = round(sum(scores) / len(scores))
            if self.overall_score > 65:
                self.level = 'high'
            elif self.overall_score > 35:
                self.level = 'moderate'
            else:
                self.level = 'low'
            self.save()
