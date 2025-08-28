# erp_multibpo_backend/apps/authentication/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import timedelta
import uuid
from .utils.email import send_confirmation_email_to_user


class User(AbstractUser):
    """
    Modelo de usuário customizado para o sistema MULTI BPO ERP
    Extende o modelo padrão do Django com campos específicos do negócio
    """

    # Campos básicos obrigatórios
    email = models.EmailField(
        unique=True,
        verbose_name="E-mail",
        help_text="E-mail único do usuário (usado para login)"
    )

    whatsapp = models.CharField(
        max_length=15,
        verbose_name="WhatsApp",
        help_text="Número do WhatsApp com formato (11) 99999-9999",
        validators=[RegexValidator(regex=r'^\(\d{2}\) \d{5}-\d{4}$', message="Formato esperado: (11) 99999-9999")]
    )

    # Confirmação de e-mail
    email_confirmed = models.BooleanField(
        default=False,
        verbose_name="E-mail Confirmado",
        help_text="Se o usuário confirmou seu e-mail"
    )

    email_confirmation_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        null=True,
        verbose_name="Token de Confirmação",
        help_text="Token único para confirmação de e-mail"
    )

    email_confirmation_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="E-mail de Confirmação Enviado",
        help_text="Quando o e-mail de confirmação foi enviado"
    )

    # Controle de perguntas Luca IA
    luca_questions_used = models.PositiveIntegerField(
        default=0,
        verbose_name="Perguntas Usadas (Luca IA)",
        help_text="Número de perguntas já feitas no período atual"
    )

    luca_last_reset = models.DateTimeField(
        default=timezone.now,
        verbose_name="Último Reset (Luca IA)",
        help_text="Data do último reset do contador de perguntas"
    )

    # Tipo de usuário / plano
    USER_TYPE_CHOICES = [
        ('anonymous', 'Anônimo'),
        ('registered', 'Cadastrado'),
        ('subscriber', 'Assinante'),
    ]

    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='registered',
        verbose_name="Tipo de Usuário",
        help_text="Tipo de usuário para controle de permissões"
    )

    # Método de cadastro
    REGISTRATION_METHOD_CHOICES = [
        ('email', 'E-mail'),
        ('google', 'Google'),
        ('facebook', 'Facebook'),
    ]

    registration_method = models.CharField(
        max_length=20,
        choices=REGISTRATION_METHOD_CHOICES,
        default='email',
        verbose_name="Método de Cadastro",
        help_text="Como o usuário se cadastrou no sistema"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Configuração para usar email como campo de login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'whatsapp']

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        db_table = 'auth_user_custom'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} ({self.get_user_type_display()})"

    def save(self, *args, **kwargs):
        """Override do save para garantir que usuários sociais não precisem de confirmação"""
        if self.registration_method in ['google', 'facebook']:
            self.email_confirmed = True
        super().save(*args, **kwargs)

    # ===== Luca IA =====
    def get_luca_questions_limit(self):
        limits = {
            'anonymous': 4,
            'registered': 11,
            'subscriber': float('inf')
        }
        return limits.get(self.user_type, 4)

    def get_luca_questions_remaining(self):
        self.check_and_reset_luca_counter()
        limit = self.get_luca_questions_limit()
        if limit == float('inf'):
            return None  # Para facilitar serialização JSON (interpretar None como ilimitado)
        return max(0, limit - self.luca_questions_used)

    def can_ask_luca_question(self):
        remaining = self.get_luca_questions_remaining()
        return remaining is None or remaining > 0

    def use_luca_question(self):
        if self.can_ask_luca_question():
            if self.luca_questions_used is not None:
                self.luca_questions_used += 1
            self.save(update_fields=['luca_questions_used'])
            return True
        return False

    def check_and_reset_luca_counter(self):
        if timezone.now() - self.luca_last_reset > timedelta(days=7):
            self.luca_questions_used = 0
            self.luca_last_reset = timezone.now()
            self.save(update_fields=['luca_questions_used', 'luca_last_reset'])

    def get_next_luca_reset(self):
        return self.luca_last_reset + timedelta(days=7)

    # ===== ERP =====
    def has_erp_access(self):
        return self.email_confirmed and self.user_type in ['registered', 'subscriber']

    def get_allowed_erp_modules(self):
        if not self.has_erp_access():
            return []
        if self.user_type == 'subscriber':
            return [
                'dashboard', 'drive', 'agenda', 'loja', 'utilitarios',
                'noticias', 'luca_ia', 'certificados', 'ideias',
                'contratos', 'central_atendimento'
            ]
        if self.user_type == 'registered':
            return [
                'dashboard', 'drive_limited', 'agenda_limited',
                'loja', 'utilitarios', 'noticias', 'luca_ia'
            ]
        return []

    def get_blocked_erp_modules(self):
        all_modules = [
            'dashboard', 'drive', 'agenda', 'loja', 'utilitarios',
            'noticias', 'luca_ia', 'certificados', 'ideias',
            'contratos', 'central_atendimento'
        ]
        allowed_base = [m.replace('_limited', '') for m in self.get_allowed_erp_modules()]
        return [m for m in all_modules if m not in allowed_base]

    def can_access_erp_module(self, module_name):
        allowed_modules = self.get_allowed_erp_modules()
        if module_name in allowed_modules:
            return True
        if f"{module_name}_limited" in allowed_modules:
            return 'limited'
        return False

    # ===== E-mail =====
    def send_confirmation_email(self):
        self.email_confirmation_token = uuid.uuid4()
        self.email_confirmation_sent_at = timezone.now()
        self.save(update_fields=['email_confirmation_token', 'email_confirmation_sent_at'])
        send_confirmation_email_to_user(self)

    def confirm_email(self, token):
        if str(self.email_confirmation_token) == str(token):
            self.email_confirmed = True
            self.email_confirmation_token = None  # Limpa token após confirmação
            self.save(update_fields=['email_confirmed', 'email_confirmation_token'])
            return True
        return False

    def is_email_confirmation_expired(self):
        if not self.email_confirmation_sent_at:
            return True
        return timezone.now() - self.email_confirmation_sent_at > timedelta(hours=24)


# ===== LucaQuestion =====
class LucaQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Usuário")
    question = models.TextField(verbose_name="Pergunta")
    answer = models.TextField(blank=True, verbose_name="Resposta")
    session_id = models.CharField(max_length=100, blank=True, verbose_name="ID da Sessão")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    response_time = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    class Meta:
        verbose_name = "Pergunta Luca IA"
        verbose_name_plural = "Perguntas Luca IA"
        ordering = ['-created_at']

    def __str__(self):
        user_display = self.user.email if self.user else f"Anônimo ({self.session_id[:8]})"
        return f"{user_display}: {self.question[:50]}..."


# ===== UserSession =====
class UserSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True, verbose_name="ID da Sessão")
    questions_used = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sessão de Usuário"
        verbose_name_plural = "Sessões de Usuário"
        ordering = ['-last_activity']

    def __str__(self):
        return f"Sessão {self.session_id[:8]}... ({self.questions_used}/4 perguntas)"

    def can_ask_question(self):
        return self.questions_used < 4

    def use_question(self):
        if self.can_ask_question():
            self.questions_used += 1
            self.save(update_fields=['questions_used'])
            return True
        return False

    def get_questions_remaining(self):
        return max(0, 4 - self.questions_used)
