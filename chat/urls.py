from django.urls import path
from . import views

app_name= 'chat'

urlpatterns = [
    path("chatbot/",views.chatbot,name="chatbot"),
    path("checkup-bot/", views.checkup_bot, name="checkup_bot"),
    path("checkup-summary/<int:pregnancy_id>/", views.checkup_summary, name="checkup_summary"),
    path("chat/start/", views.start_session, name="start_session"),
    path("chat/send/", views.send_message, name="send_message"),
    path("chat/messages/<int:session_id>/", views.get_messages, name="get_messages"),
    path("professional/", views.professional_chat, name="professional_chat"),
    path("professional/conversation/<int:request_id>/", views.professional_conversation, name="professional_conversation"),
    path("checkup/start/", views.start_checkup_session, name="start_checkup_session"),
    path("checkup/send/", views.send_checkup_message, name="send_checkup_message"),
    path("checkups/<int:pregnancy_id>/trigger/", views.trigger_checkup, name="trigger_checkup"),
    path("checkups/<int:pregnancy_id>/questions/add/", views.add_checkup_question, name="add_checkup_question"),
]
