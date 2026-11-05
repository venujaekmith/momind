from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(User)
admin.site.register(MotherProfile)
admin.site.register(FatherProfile)
admin.site.register(MidwifeProfile)
admin.site.register(HospitalProfile)
admin.site.register(DoctorProfile)
admin.site.register(Family)
admin.site.register(MotherDetails)
