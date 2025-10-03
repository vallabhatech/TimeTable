from django.urls import path
from .views import LoginView, RegisterView, ProfileView, ForgotPasswordView, ResetPasswordView, UsersListView, PublicDepartmentsView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('departments/', PublicDepartmentsView.as_view(), name='public_departments'),
    path('', UsersListView.as_view(), name='users_list'),
]