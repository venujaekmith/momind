from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


app_name='accounts'

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("select-role/", views.select_role, name="select_role"),
    path('logout/', views.logout_view, name='logout'),
    path('mother_details/',views.mother_details,name="mother_details"),
    path('father-details/', views.father_details, name='father_details'),
    path('midwife-details/', views.midwife_details, name='midwife_details'),
    path('doctor-details/', views.doctor_details, name='doctor_details'),
    path('hospital-details/', views.hospital_details, name='hospital_details'),
    path('hospital-staff-details/', views.hospital_staff_details, name='hospital_staff_details'),
]