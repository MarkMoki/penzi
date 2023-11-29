from django.urls import path
from . import views

urlpatterns = [
    path('message-receive/', views.message_receive_view, name="message_receive_view"),
]
