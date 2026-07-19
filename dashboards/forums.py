from django import forms
from .models import *

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class VisitOverrideForm(forms.Form):
    date = forms.DateField()

class MultipleFileField(forms.FileField):

    widget = MultipleFileInput

    def clean(self, data, initial=None):

        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):

            result = []

            for file in data:
                result.append(
                    single_file_clean(file, initial)
                )

            return result

        return single_file_clean(data, initial)

class PregnancyForm(forms.ModelForm):
    class Meta:
        model = Pregnancy
        fields = [
            "pregnancy_number",
            "is_active",
            "last_menstrual_period",
            "expected_delivery_date",
            "pre_pregnancy_weight",
            "is_high_risk",
        ]

class PregnancyProgressForm(forms.ModelForm):
    class Meta:
        model = PregnancyProgress
        fields = "__all__"
        exclude = ["pregnancy","id","recorded_by"]

class FetalHealthForm(forms.ModelForm):
    class Meta:
        model = FetalHealth
        fields = "__all__"
        exclude = ["pregnancy","id","recorded_by"]

class LabTestForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = LabTest
        fields = "__all__"
        exclude = ["pregnancy","id","recorded_by"]


# In forums.py

class ScheduleEventForm(forms.ModelForm):
    class Meta:
        model = ScheduleEvent
        fields = ['title', 'event_type', 'clinic', 'scheduled_date', 'scheduled_time', 
                 'location', 'notes', 'what_to_bring']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class ClinicForm(forms.ModelForm):
    class Meta:
        model = Clinics
        fields = ['name', 'description', 'location', 'date', 'time', 'capacity', 'is_active']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
        }


class TrimesterTaskForm(forms.ModelForm):
    class Meta:
        model = TrimesterTask
        fields = ['title', 'description', 'is_completed']

class RescheduleEventForm(forms.ModelForm):
    class Meta:
        model = ScheduleEvent
        fields = ['scheduled_date', 'scheduled_time', 'notes', 'location']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time'}),
        }

from django import forms
from .models import Pregnancy

class EndPregnancyForm(forms.ModelForm):
    class Meta:
        model = Pregnancy
        fields = ['actual_delivery_date']

    delivery_type = forms.ChoiceField(
        choices=[
            ('normal', 'Normal Vaginal Delivery'),
            ('c_section', 'Cesarean Section'),
            ('assisted', 'Assisted Delivery'),
            ('other', 'Other')
        ],
        label="Delivery Type"
    )

    baby_count = forms.IntegerField(
        min_value=1, 
        max_value=5, 
        initial=1,
        label="Number of Babies"
    )

class BabyDevelopmentForm(forms.ModelForm):
    class Meta:
        model = BabyDevelopmentRecord
        fields = [
            'age_in_weeks', 'weight_kg', 'height_cm', 
            'head_circumference_cm', 'feeding_type',
            'milestones_achieved', 'concerns', 'notes'
        ]
        widgets = {
            'milestones_achieved': forms.Textarea(attrs={'rows': 3}),
            'concerns': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }