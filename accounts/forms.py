from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

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
    

class RegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class MotherDetailsForm(forms.ModelForm):
    class Meta:
        model = MotherDetails
        fields = [
            "height_cm",
            "blood_group",
            "has_diabetes",
            "has_hypertension",
            "previous_pregnancies",
            "home_latitude",
            "home_longitude",
        ]
        widgets = {
            "home_latitude": forms.HiddenInput(),
            "home_longitude": forms.HiddenInput(),
        }

    def clean_height_cm(self):
        value = self.cleaned_data.get('height_cm')
        if value is not None and not 50 <= value <= 250:
            raise forms.ValidationError("Enter a height between 50 and 250 cm.")
        return value

    def clean_previous_pregnancies(self):
        value = self.cleaned_data.get('previous_pregnancies')
        if value is not None and not 0 <= value <= 30:
            raise forms.ValidationError("Enter a value between 0 and 30.")
        return value

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get('home_latitude')
        longitude = cleaned.get('home_longitude')
        if latitude is not None and not -90 <= latitude <= 90:
            self.add_error('home_latitude', "Latitude must be between -90 and 90.")
        if longitude is not None and not -180 <= longitude <= 180:
            self.add_error('home_longitude', "Longitude must be between -180 and 180.")
        return cleaned

class FatherDetailsForm(forms.ModelForm):
    class Meta:
        model = FatherProfile  # or create a separate FatherDetails model
        fields = ['linked_mother']  # add more fields if needed

class MidwifeDetailsForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = MidwifeProfile
        fields = ['license_no', 'phm_area', 'moh_area']

class DoctorDetailsForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = DoctorProfile
        fields = ['designation', 'hospital']

class HospitalDetailsForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = HospitalProfile
        fields = ['name', 'address', 'contact_number', 'district']


class HospitalStaffDetailsForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = HospitalStaffProfile
        fields = ['hospital', 'role_title']
