from django.urls import path

from . import views


urlpatterns = [
    path("profile/", views.UserProfileView.as_view(), name="profile"),
    path("sign-up/", views.SignUpView.as_view(), name="sign-up"),
    path("sign-out/", views.SignOutView.as_view(), name="sign-out"),
]
