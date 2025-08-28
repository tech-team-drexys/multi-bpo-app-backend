from django.urls import path
from . import views

urlpatterns = [
    # Saúde da API
    path('health/', views.health_check, name='auth_health'),
    
    # Registro e autenticação
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('social-login/', views.SocialLoginView.as_view(), name='social_login'),
    
    # Confirmação de email
    path('confirm-email/', views.EmailConfirmationView.as_view(), name='confirm_email'),
    path('resend-confirmation/', views.ResendConfirmationEmailView.as_view(), name='resend_confirmation'),
    
    # Reset de senha
    path('password-reset/', views.PasswordResetView.as_view(), name='password_reset'),
    
    # Perfil do usuário
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    
    # Luca IA
    path('luca/question/', views.LucaQuestionView.as_view(), name='luca_question'),
    path('luca/status/', views.LucaStatusView.as_view(), name='luca_status'),
]
