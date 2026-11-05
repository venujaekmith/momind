from django import forms
from django.utils import timezone
from .models import *

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class VisitOverrideForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

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
            "last_menstrual_period",
            "expected_delivery_date",
            "pre_pregnancy_weight",
        ]
        widgets = {
            "last_menstrual_period": forms.DateInput(attrs={'type': 'date'}),
            "expected_delivery_date": forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        lmp = cleaned.get("last_menstrual_period")
        due = cleaned.get("expected_delivery_date")
        today = timezone.localdate()
        if lmp and lmp > today:
            self.add_error("last_menstrual_period", "This date cannot be in the future.")
        if lmp and due and due <= lmp:
            self.add_error("expected_delivery_date", "The due date must be after the last menstrual period.")
        weight = cleaned.get("pre_pregnancy_weight")
        if weight is not None and not 20 <= weight <= 300:
            self.add_error("pre_pregnancy_weight", "Enter a weight between 20 and 300 kg.")
        return cleaned

class PregnancyProgressForm(forms.ModelForm):
    class Meta:
        model = PregnancyProgress
        fields = "__all__"
        exclude = ["pregnancy","id","recorded_by"]

    def clean_week(self):
        value = self.cleaned_data['week']
        if not 0 <= value <= 45:
            raise forms.ValidationError("Pregnancy week must be between 0 and 45.")
        return value

class FetalHealthForm(forms.ModelForm):
    class Meta:
        model = FetalHealth
        fields = "__all__"
        exclude = ["pregnancy","id","recorded_by"]

    def clean_week(self):
        value = self.cleaned_data['week']
        if not 0 <= value <= 45:
            raise forms.ValidationError("Pregnancy week must be between 0 and 45.")
        return value

class LabTestForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = LabTest
        fields = "__all__"
        exclude = ["pregnancy","id","recorded_by"]
        widgets = {
            "taken_date": forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_taken_date(self):
        value = self.cleaned_data['taken_date']
        if value > timezone.localdate():
            raise forms.ValidationError("The test date cannot be in the future.")
        return value


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

    def clean_scheduled_date(self):
        value = self.cleaned_data['scheduled_date']
        if value < timezone.localdate():
            raise forms.ValidationError("The event date cannot be in the past.")
        return value


class ClinicForm(forms.ModelForm):
    class Meta:
        model = Clinics
        fields = ['name', 'description', 'location', 'date', 'time', 'capacity', 'is_active']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
        }


    def clean_date(self):
        value = self.cleaned_data['date']
        if value < timezone.localdate():
            raise forms.ValidationError("The clinic date cannot be in the past.")
        return value

    def clean_capacity(self):
        value = self.cleaned_data['capacity']
        if value < 1:
            raise forms.ValidationError("Clinic capacity must be at least 1.")
        return value


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
        widgets = {
            'actual_delivery_date': forms.DateInput(attrs={'type': 'date'}),
        }

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

    def clean_actual_delivery_date(self):
        value = self.cleaned_data["actual_delivery_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("Delivery date cannot be in the future.")
        return value

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
