# forms.py
from django import forms
from .models import *

class MoodForm(forms.ModelForm):
    class Meta:
        model = MoodEntry
        fields = ['mood_score', 'energy_level', 'sleep_hours', 'feelings']
        widgets = {
            'mood_score': forms.RadioSelect(),
            'energy_level': forms.RadioSelect(),
            'sleep_hours': forms.NumberInput(attrs={'min': 0, 'max': 24, 'step': 0.5, 'placeholder': 'e.g. 6.5'}),
            'feelings': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'How are you feeling today? (optional)'
            }),
        }
        labels = {
            'mood_score': 'Mood today',
            'energy_level': 'Energy level',
            'sleep_hours': 'Sleep in the last 24 hours',
            'feelings': 'What is on your mind?',
        }

    def clean_sleep_hours(self):
        sleep_hours = self.cleaned_data.get('sleep_hours')
        if sleep_hours is not None and not 0 <= sleep_hours <= 24:
            raise forms.ValidationError('Enter sleep between 0 and 24 hours.')
        return sleep_hours


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
        labels = {'mood': 'Mood while writing'}


class StressForm(forms.ModelForm):
    class Meta:
        model = StressLog
        fields = ['stress_level', 'trigger', 'coping_method', 'notes']
        widgets = {
            'stress_level': forms.RadioSelect(),
            'trigger': forms.TextInput(attrs={'placeholder': 'What triggered your stress?'}),
            'coping_method': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What helped you cope?'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'stress_level': 'Stress level right now',
            'trigger': 'Possible trigger',
            'coping_method': 'What helped?',
            'notes': 'Anything else to remember',
        }


class PostpartumProfileForm(forms.ModelForm):
    class Meta:
        model = PostpartumProfile
        fields = ['delivery_date', 'delivery_type', 'baby_count']
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'baby_count': forms.NumberInput(attrs={'min': 1, 'max': 10}),
        }

    def clean_delivery_date(self):
        from django.utils import timezone
        delivery_date = self.cleaned_data.get('delivery_date')
        if delivery_date and delivery_date > timezone.localdate():
            raise forms.ValidationError('Delivery date cannot be in the future.')
        return delivery_date

    def clean_baby_count(self):
        baby_count = self.cleaned_data.get('baby_count')
        if baby_count is not None and not 1 <= baby_count <= 10:
            raise forms.ValidationError('Enter a baby count between 1 and 10.')
        return baby_count

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
        labels = {
            'q1_mood': 'Mood today',
            'q2_sleep': 'Hours slept in the last 24 hours',
            'q3_feeling': 'How have you been feeling emotionally?',
            'q4_writing': 'What has been on your mind?',
            'q5_drawing_desc': 'Describe an image that represents how you feel',
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['q1_mood'].required = True
        self.fields['q2_sleep'].required = True

    def clean_q2_sleep(self):
        sleep_hours = self.cleaned_data.get('q2_sleep')
        if sleep_hours is not None and not 0 <= sleep_hours <= 24:
            raise forms.ValidationError('Enter sleep between 0 and 24 hours.')
        return sleep_hours
