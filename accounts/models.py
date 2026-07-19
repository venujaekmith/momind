import uuid
import random
from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date
import uuid
#import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files import File


# ------------------------
# ROLE ENUM
# ------------------------
class Role(models.TextChoices):
    MOTHER = "MOTHER"
    FATHER = "FATHER"
    MIDWIFE = "MIDWIFE"
    DOCTOR = "DOCTOR"
    HOSPITAL = "HOSPITAL"
    HOSPITAL_STAFF = "HOSPITAL_STAFF"

# ------------------------
# CUSTOM USER
# ------------------------
class User(AbstractUser):
    
    email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=Role.choices, null=True, blank=True)
    is_role_selected = models.BooleanField(default=False)


# ------------------------
# ROLE PROFILES
# ------------------------

# =========================
# MOTHER PROFILE
# =========================

class MotherProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_mother"
    )

    mother_id = models.CharField(max_length=20, unique=True)
    pregnancy_week = models.IntegerField(default=0)

    """qr_code = models.ImageField(
        upload_to='qr_codes/mothers/',
        blank=True,
        null=True
    )

    qr_token = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):

        if not self.mother_id:
            self.mother_id = f"MOM-{uuid.uuid4().hex[:8].upper()}"

        if not self.qr_token:
            self.qr_token = self.mother_id

        super().save(*args, **kwargs)

        if not self.qr_code:

            qr = qrcode.make(f"FAMQR:{self.qr_token}")

            buffer = BytesIO()
            qr.save(buffer, format='PNG')

            filename = f"mother_{self.mother_id}.png"

            self.qr_code.save(
                filename,
                File(buffer),
                save=False
            )

            super().save(update_fields=['qr_code'])

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.mother_id}"""


# =========================
# FATHER PROFILE
# =========================

class FatherProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_father"
    )

    father_id = models.CharField(max_length=20, unique=True)

    linked_mother = models.ForeignKey(
        MotherProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="father"
    )

    """qr_code = models.ImageField(
        upload_to='qr_codes/fathers/',
        blank=True,
        null=True
    )

    qr_token = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):

        if not self.father_id:
            self.father_id = f"DAD-{uuid.uuid4().hex[:8].upper()}"

        if not self.qr_token:
            self.qr_token = self.father_id

        super().save(*args, **kwargs)

        if not self.qr_code:

            qr = qrcode.make(f"FAMQR:{self.qr_token}")

            buffer = BytesIO()
            qr.save(buffer, format='PNG')

            filename = f"father_{self.father_id}.png"

            self.qr_code.save(
                filename,
                File(buffer),
                save=False
            )

            super().save(update_fields=['qr_code'])

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.father_id}"""


# =========================
# MIDWIFE PROFILE
# =========================

class MidwifeProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_midwife"
    )

    license_no = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    midwife_id = models.CharField(max_length=20, unique=True)

    is_verified = models.BooleanField(default=False)

    phm_area = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

    moh_area = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

"""qr_code = models.ImageField(
        upload_to='qr_codes/midwives/',
        blank=True,
        null=True
    )

    qr_token = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):

        if not self.midwife_id:
            self.midwife_id = f"MID-{uuid.uuid4().hex[:8].upper()}"

        if not self.qr_token:
            self.qr_token = self.midwife_id

        super().save(*args, **kwargs)

        if not self.qr_code:

            qr = qrcode.make(f"FAMQR:{self.qr_token}")

            buffer = BytesIO()
            qr.save(buffer, format='PNG')

            filename = f"midwife_{self.midwife_id}.png"

            self.qr_code.save(
                filename,
                File(buffer),
                save=False
            )

            super().save(update_fields=['qr_code'])

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.midwife_id}"""


# =========================
# HOSPITAL PROFILE
# =========================

class HospitalProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_hospital"
    )

    hospital_id = models.CharField(max_length=20, unique=True)

    name = models.CharField(max_length=255)

    is_verified = models.BooleanField(default=False)

    contact_number = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    district = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    address = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    """qr_code = models.ImageField(
        upload_to='qr_codes/hospitals/',
        blank=True,
        null=True
    )

    qr_token = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):

        if not self.hospital_id:
            self.hospital_id = f"HOS-{uuid.uuid4().hex[:8].upper()}"

        if not self.qr_token:
            self.qr_token = self.hospital_id

        super().save(*args, **kwargs)

        if not self.qr_code:

            qr = qrcode.make(f"FAMQR:{self.qr_token}")

            buffer = BytesIO()
            qr.save(buffer, format='PNG')

            filename = f"hospital_{self.hospital_id}.png"

            self.qr_code.save(
                filename,
                File(buffer),
                save=False
            )

            super().save(update_fields=['qr_code'])

    def __str__(self):
        return f"{self.name} - {self.hospital_id}"""


# =========================
# HOSPITAL STAFF PROFILE

class HospitalStaffProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_hospital_staff"
    )

    staff_id = models.CharField(max_length=20, unique=True)
    hospital = models.ForeignKey(
        HospitalProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_members"
    )
    role_title = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.staff_id}"


# =========================
# DOCTOR PROFILE
# =========================

class DoctorProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_doctor"
    )

    doctor_id = models.CharField(max_length=20, unique=True)

    hospital = models.ForeignKey(
        HospitalProfile,
        null=True,
        on_delete=models.SET_NULL
    )

    is_verified = models.BooleanField(default=False)

    designation = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    """qr_code = models.ImageField(
        upload_to='qr_codes/doctors/',
        blank=True,
        null=True
    )

    qr_token = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):

        if not self.doctor_id:
            self.doctor_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"

        if not self.qr_token:
            self.qr_token = self.doctor_id

        super().save(*args, **kwargs)

        if not self.qr_code:

            qr = qrcode.make(f"FAMQR:{self.qr_token}")

            buffer = BytesIO()
            qr.save(buffer, format='PNG')

            filename = f"doctor_{self.doctor_id}.png"

            self.qr_code.save(
                filename,
                File(buffer),
                save=False
            )

            super().save(update_fields=['qr_code'])

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username} - {self.doctor_id}"""

from dashboards.models import Pregnancy

class Family(models.Model):
    pregnancy = models.ForeignKey(Pregnancy,null=True,blank=True,on_delete=models.CASCADE,related_name="preg_fam")
    mother = models.ForeignKey(MotherProfile, null=True, blank=True, on_delete=models.SET_NULL,related_name="mom_familiy")
    father = models.ForeignKey(FatherProfile, null=True, blank=True, on_delete=models.SET_NULL,related_name="father_familiy")
    midwife = models.ForeignKey(MidwifeProfile, null=True, blank=True, on_delete=models.SET_NULL,related_name="midwife_familiy")
    doctor = models.ForeignKey(DoctorProfile, null=True, blank=True, on_delete=models.SET_NULL,related_name="doctor_familiy")
    hospital = models.ForeignKey(HospitalProfile,null=True, blank=True, on_delete=models.SET_NULL,related_name="hospital_familiy")

class FamilyInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    family = models.ForeignKey('Family', on_delete=models.CASCADE, related_name='invitations')
    
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations')
    
    role = models.CharField(max_length=20)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.role} invitation from {self.invited_by}"

class MotherDetails(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="details")

    mother = models.OneToOneField("accounts.MotherProfile",on_delete=models.CASCADE,related_name="mother_details")

    height_cm = models.FloatField(null=True, blank=True)

    blood_group = models.CharField(max_length=5, null=True, blank=True)

    has_diabetes = models.BooleanField(default=False)
    has_hypertension = models.BooleanField(default=False)
    previous_pregnancies = models.IntegerField(default=0)
    
   
    home_latitude = models.FloatField(null=True, blank=True)
    home_longitude = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

class VerifyDoc(models.Model):

    profile = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attachments_verify'
    )

    file = models.FileField(upload_to="VerifyDocs/")

    uploaded_at = models.DateTimeField(auto_now_add=True)