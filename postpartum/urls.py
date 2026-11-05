from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'postpartum'

urlpatterns = [
    path('dashboard/', views.postpartum_dashboard, name='postpartum_dashboard'),
    path('log-mood/', views.log_mood, name='log_mood'),
    path('journal/', views.journal, name='journal'),
    path('stress-log/', views.stress_log, name='stress_log'),
    path('breathing/<int:exercise_id>/', views.breathing_exercise, name='breathing_exercise'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('history/', views.wellness_history, name='wellness_history'),

    path('ai-assessment/', views.ai_stress_assessment, name='ai_stress_assessment'),
    path('ai-assessment/result/<int:assessment_id>/', views.assessment_result, name='assessment_result'),

    path('companion/', views.dashboard, name='ai_dash'),
    path('ai_asses', RedirectView.as_view(pattern_name='postpartum:ai_dash', permanent=False)),
    path('chat/', views.chat_view, name='chat'),
    path('chat/send/', views.send_message, name='send_message'),
    path('chat/new/', views.new_conversation, name='new_conversation'),
    path('draw/', views.draw_view, name='draw'),
    path('draw/analyze/', views.analyze_drawing, name='analyze_drawing'),
    path('wellness/', views.wellness_view, name='wellness'),
]
