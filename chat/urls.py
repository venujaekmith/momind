from django.urls import path
from . import views

app_name= 'chat'

urlpatterns = [
    path("chatbot/",views.chatbot,name="chatbot"),
    path("chat/start/", views.start_session),
    path("chat/send/", views.send_message),
    path("chat/messages/<int:session_id>/", views.get_messages),
]