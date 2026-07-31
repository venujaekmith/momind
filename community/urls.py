from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    # Forum paths
    path('', views.forum_home, name='forum_home'),
    path('post/new/', views.create_post, name='create_post'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('forum/<int:forum_id>/subscribe/', views.subscribe_forum, name='subscribe_forum'),
    path('forum/<int:forum_id>/unsubscribe/', views.unsubscribe_forum, name='unsubscribe_forum'),
    
    # Hospital Group paths
    path('groups/', views.group_list, name='group_list'),
    path('groups/new/', views.create_group, name='create_group'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:group_id>/manage/', views.manage_group, name='manage_group'),
    path('groups/<int:group_id>/members/<int:member_id>/remove/', views.remove_group_member, name='remove_group_member'),
    path('groups/<int:pk>/join/', views.join_group, name='join_group'),
    path('groups/<int:group_id>/subscribe/', views.subscribe_group, name='subscribe_group'),
    path('groups/<int:group_id>/unsubscribe/', views.unsubscribe_group, name='unsubscribe_group'),
    
    # Clinic Schedule paths
    path('groups/<int:group_id>/schedules/', views.clinic_schedules, name='clinic_schedules'),
    path('groups/<int:group_id>/schedule/new/', views.create_clinic_schedule, name='create_clinic_schedule'),
    
    # Notifications
    path('notifications/', views.view_notifications, name='view_notifications'),
    # Hospital staff dashboard & actions
    path('hospital/dashboard/', views.hospital_staff_dashboard, name='hospital_dashboard'),
    path('hospital/clinic/<int:clinic_id>/announce/', views.create_clinic_announcement, name='create_clinic_announcement'),
    path('hospital/group/create_add/', views.create_group_and_add_members, name='create_group_and_add_members'),
    path('hospital/appointment/<int:appointment_id>/reschedule/', views.reschedule_appointment, name='reschedule_appointment'),
]
