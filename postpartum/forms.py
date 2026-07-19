# forms.py
from django import forms
from .models import *

class MoodForm(forms.ModelForm):
    class Meta:
        model = MoodEntry
        fields = ['mood_score', 'energy_level', 'sleep_hours', 'feelings']
        widgets = {
            'mood_score': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'energy_level': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'feelings': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'How are you feeling today? (optional)'
            }),
        }


class JournalForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ['title', 'content', 'mood']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Title (e.g., A grateful moment today)'}),
            'content': forms.Textarea(attrs={
                'rows': 8, 
                'placeholder': 'Write your thoughts here... It\'s safe to express everything.'
            }),
        }


class StressForm(forms.ModelForm):
    class Meta:
        model = StressLog
        fields = ['stress_level', 'trigger', 'coping_method', 'notes']
        widgets = {
            'stress_level': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'trigger': forms.TextInput(attrs={'placeholder': 'What triggered your stress?'}),
            'coping_method': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What helped you cope?'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }


class PostpartumProfileForm(forms.ModelForm):
    class Meta:
        model = PostpartumProfile
        fields = ['delivery_date', 'delivery_type', 'baby_count']
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date'}),
        }

class AIStressAssessmentForm(forms.ModelForm):
    class Meta:
        model = AIStressAssessment
        fields = ['q1_mood', 'q2_sleep', 'q3_feeling', 'q4_writing', 'q5_drawing_desc']
        widgets = {
            'q1_mood': forms.RadioSelect(),
            'q2_sleep': forms.NumberInput(attrs={'min': 0, 'max': 24}),
            'q3_feeling': forms.Textarea(attrs={'rows': 3, 'placeholder': 'How have you been feeling emotionally?'}),
            'q4_writing': forms.Textarea(attrs={
                'rows': 6, 
                'placeholder': 'Write anything that comes to your mind... no filter.'
            }),
            'q5_drawing_desc': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'If you could draw how you feel right now, what would you draw?'
            }),
        }