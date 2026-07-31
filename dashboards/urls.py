from django.urls import path
from . import views

app_name = 'dashboards'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('link_member/',views.link_member_view,name="link_member"),
    path('family/remove/', views.remove_family_member, name='remove_family_member'),
    path('family/leave/<int:family_id>/', views.leave_family, name='leave_family'),
    path('link-request/<int:link_id>/respond/', views.respond_link_request, name='respond_link_request'),
    path('log-water/', views.log_water, name='log_water'),
    path('log-kicks/', views.log_kicks, name='log_kicks'),
    path('start_pregnancy/',views.start_pregnancy,name="start_pregnancy"),

    # Pregnancy Progress
    path("pregnancy/<int:pregnancy_id>/progress/add/",
         views.add_pregnancy_progress,
         name="add_progress"),

    # Fetal Health
    path("pregnancy/<int:pregnancy_id>/fetal/add/",
         views.add_fetal_health,
         name="add_fetal"),

    # Lab Tests
    path("pregnancy/<int:pregnancy_id>/lab/add/",
         views.add_lab_test,
         name="add_lab"),
     
         # Scheduling
    path("pregnancy/<int:pregnancy_id>/schedule/add/",
         views.add_schedule_event, name="add_schedule"),
    path("event/<int:event_id>/complete/", 
         views.complete_event, name="complete_event"),
    path("task/<int:task_id>/complete/", 
         views.complete_task, name="complete_task"),
     
     path("event/<int:event_id>/reschedule/", 
     views.reschedule_event, name="reschedule_event"),

     path("end_pregnancy/<int:id>/",views.end_pregnancy,name="end_pregnancy"),

    path('midwife/mother/<int:pregnancy_id>/', views.midwife_mother_detail, name='midwife_mother_detail'),
    path('pregnancy/<int:pregnancy_id>/record/', views.midwife_mother_detail, name='pregnancy_detail'),
    path('midwife/add-visit-note/<int:pregnancy_id>/', views.add_visit_note, name='add_visit_note'),
    path('add-baby-development/<int:pregnancy_id>/', views.add_baby_development,name='add_baby_development'),
    path('baby_ai/<int:id>/',views.babyai,name='babyai'),
    path('clinic-directory/', views.clinic_directory, name='clinic_directory'),
    path('clinic/<int:clinic_id>/', views.clinic_detail, name='clinic_detail'),
    path('hospital/clinic/create/', views.create_hospital_clinic, name='create_hospital_clinic'),
    path('hospital/clinic/<int:clinic_id>/edit/', views.create_hospital_clinic, name='edit_hospital_clinic'),
    path('hospital/clinic/assign-staff/<int:clinic_id>/', views.assign_clinic_staff, name='assign_clinic_staff'),
    path('hospital/clinic/add-appointment/<int:clinic_id>/', views.add_clinic_appointment, name='add_clinic_appointment'),
    path('hospital/staff/', views.hospital_staff_dashboard, name='hospital_staff_dashboard'),
]
