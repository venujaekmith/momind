from django import forms

from .models import (
    ForumPost,
    ForumComment,
    GroupPost,
    GroupComment,
    HospitalGroup,
    ForumCommentAnonymous,
    ClinicSchedule,
)


# =========================================
# MULTIPLE FILE SUPPORT
# =========================================

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


# =========================================
# FORUM POST FORM
# =========================================

class ForumPostForm(forms.ModelForm):

    attachments = MultipleFileField(required=False)

    class Meta:
        model = ForumPost

        fields = [
            'category',
            'title',
            'content',
            'is_anonymous'
        ]


# =========================================
# FORUM COMMENT FORM
# =========================================

class ForumCommentForm(forms.ModelForm):

    class Meta:
        model = ForumComment
        fields = ['content']


# =========================================
# GROUP FORM
# =========================================

class GroupForm(forms.ModelForm):

    class Meta:
        model = HospitalGroup
        fields = ['name', 'description']


# =========================================
# GROUP POST FORM
# =========================================

class GroupPostForm(forms.ModelForm):

    attachments = MultipleFileField(required=False)

    class Meta:
        model = GroupPost
        fields = ['content']


# =========================================
# GROUP COMMENT FORM
# =========================================

class GroupCommentForm(forms.ModelForm):

    class Meta:
        model = GroupComment
        fields = ['content']


# =========================================
# ANONYMOUS FORUM COMMENT FORM
# =========================================

class ForumCommentAnonymousForm(forms.ModelForm):
    
    author_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Your name (optional)',
            'class': 'form-control'
        })
    )

    class Meta:
        model = ForumCommentAnonymous
        fields = ['content', 'author_name']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your thoughts...'
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        author_name = cleaned_data.get('author_name')
        if not author_name:
            cleaned_data['author_name'] = "Anonymous"
        return cleaned_data


# =========================================
# CLINIC SCHEDULE FORM
# =========================================

class ClinicScheduleForm(forms.ModelForm):
    
    class Meta:
        model = ClinicSchedule
        fields = [
            'title',
            'description',
            'scheduled_date',
            'start_time',
            'end_time',
            'location',
            'specialization',
            'max_patients'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'max_patients': forms.NumberInput(attrs={'class': 'form-control'}),
        }