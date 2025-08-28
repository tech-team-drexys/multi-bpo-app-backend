from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import User, LucaQuestion, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Interface administrativa personalizada para o modelo User
    """
    
    # Campos exibidos na lista de usuários
    list_display = [
        'email', 'get_full_name', 'user_type', 'registration_method',
        'email_confirmed', 'is_active', 'luca_questions_status',
        'created_at', 'last_login'
    ]
    
    # Filtros laterais
    list_filter = [
        'user_type', 'registration_method', 'email_confirmed', 
        'is_active', 'is_staff', 'created_at', 'last_login'
    ]
    
    # Campos de busca
    search_fields = ['email', 'first_name', 'last_name', 'whatsapp']
    
    # Ordenação padrão
    ordering = ['-created_at']
    
    # Campos somente leitura
    readonly_fields = [
        'email_confirmation_token', 'created_at', 'updated_at',
        'last_login', 'date_joined', 'luca_questions_display',
        'allowed_modules_display', 'registration_info'
    ]
    
    # Configuração dos fieldsets (seções no formulário de edição)
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('email', 'whatsapp', 'first_name', 'last_name')
        }),
        ('Status da Conta', {
            'fields': (
                'is_active', 'email_confirmed', 'user_type', 
                'registration_method', 'registration_info'
            )
        }),
        ('Permissões', {
            'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Luca IA', {
            'fields': ('luca_questions_display',),
            'classes': ('collapse',)
        }),
        ('Módulos ERP', {
            'fields': ('allowed_modules_display',),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Confirmação de E-mail', {
            'fields': ('email_confirmation_token', 'email_confirmation_sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Campos para criação de novo usuário
    add_fieldsets = (
        ('Criar Usuário', {
            'classes': ('wide',),
            'fields': (
                'email', 'whatsapp', 'password1', 'password2',
                'first_name', 'last_name', 'user_type'
            ),
        }),
    )
    
    # Actions personalizadas
    actions = ['confirm_email', 'reset_luca_questions', 'upgrade_to_subscriber']
    
    def get_full_name(self, obj):
        """Retorna nome completo ou email se nome não preenchido"""
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email
    get_full_name.short_description = 'Nome'
    
    def luca_questions_status(self, obj):
        """Status das perguntas Luca IA"""
        remaining = obj.get_luca_questions_remaining()
        limit = obj.get_luca_questions_limit()
        
        if limit == float('inf'):
            return mark_safe('<span style="color: green;">♾️ Ilimitadas</span>')
        
        used = obj.luca_questions_used
        color = 'green' if remaining > 2 else 'orange' if remaining > 0 else 'red'
        
        return mark_safe(
            f'<span style="color: {color};">'
            f'{remaining}/{limit} restantes '
            f'({used} usadas)</span>'
        )
    luca_questions_status.short_description = 'Status Luca IA'
    
    def luca_questions_display(self, obj):
        """Exibe informações detalhadas das perguntas Luca IA"""
        remaining = obj.get_luca_questions_remaining()
        limit = obj.get_luca_questions_limit()
        next_reset = obj.get_next_luca_reset()
        
        html = f"""
        <strong>Perguntas restantes:</strong> {remaining if limit != float('inf') else '♾️'}<br>
        <strong>Limite total:</strong> {limit if limit != float('inf') else 'Ilimitado'}<br>
        <strong>Usadas no período:</strong> {obj.luca_questions_used}<br>
        <strong>Último reset:</strong> {obj.luca_last_reset.strftime('%d/%m/%Y %H:%M')}<br>
        <strong>Próximo reset:</strong> {next_reset.strftime('%d/%m/%Y %H:%M')}<br>
        """
        
        # Link para perguntas do usuário
        questions_url = reverse('admin:authentication_lucaquestion_changelist')
        html += f'<br><a href="{questions_url}?user__id__exact={obj.id}" target="_blank">Ver perguntas →</a>'
        
        return mark_safe(html)
    luca_questions_display.short_description = 'Informações Luca IA'
    
    def allowed_modules_display(self, obj):
        """Exibe módulos permitidos/bloqueados"""
        allowed = obj.get_allowed_erp_modules()
        blocked = obj.get_blocked_erp_modules()
        
        html = "<strong>Módulos Permitidos:</strong><br>"
        html += "<br>".join([f"✅ {module}" for module in allowed])
        
        if blocked:
            html += "<br><br><strong>Módulos Bloqueados:</strong><br>"
            html += "<br>".join([f"❌ {module}" for module in blocked])
        
        return mark_safe(html)
    allowed_modules_display.short_description = 'Módulos ERP'
    
    def registration_info(self, obj):
        """Informações do registro"""
        html = f"""
        <strong>Método:</strong> {obj.get_registration_method_display()}<br>
        <strong>E-mail confirmado:</strong> {'✅ Sim' if obj.email_confirmed else '❌ Não'}<br>
        <strong>Data de registro:</strong> {obj.created_at.strftime('%d/%m/%Y %H:%M')}<br>
        """
        
        if obj.email_confirmation_sent_at:
            expired = obj.is_email_confirmation_expired()
            status = '⏰ Expirado' if expired else '⏳ Pendente'
            html += f"<strong>Confirmação enviada:</strong> {obj.email_confirmation_sent_at.strftime('%d/%m/%Y %H:%M')} ({status})<br>"
        
        return mark_safe(html)
    registration_info.short_description = 'Info do Registro'
    
    # Actions personalizadas
    def confirm_email(self, request, queryset):
        """Confirma email de usuários selecionados"""
        count = queryset.filter(email_confirmed=False).update(email_confirmed=True)
        self.message_user(request, f'{count} usuários tiveram o e-mail confirmado.')
    confirm_email.short_description = "Confirmar e-mail dos usuários selecionados"
    
    def reset_luca_questions(self, request, queryset):
        """Reset das perguntas Luca IA"""
        for user in queryset:
            user.luca_questions_used = 0
            user.luca_last_reset = timezone.now()
            user.save(update_fields=['luca_questions_used', 'luca_last_reset'])
        
        self.message_user(request, f'Reset de perguntas Luca IA aplicado a {queryset.count()} usuários.')
    reset_luca_questions.short_description = "Reset perguntas Luca IA"
    
    def upgrade_to_subscriber(self, request, queryset):
        """Upgrade para assinante"""
        count = queryset.exclude(user_type='subscriber').update(user_type='subscriber')
        self.message_user(request, f'{count} usuários foram promovidos a assinantes.')
    upgrade_to_subscriber.short_description = "Promover a assinante"


@admin.register(LucaQuestion)
class LucaQuestionAdmin(admin.ModelAdmin):
    """
    Interface administrativa para perguntas Luca IA
    """
    
    list_display = [
        'id', 'user_display', 'question_preview', 'answer_preview',
        'response_time', 'created_at'
    ]
    
    list_filter = [
        'created_at', 'response_time'
    ]
    
    search_fields = [
        'question', 'answer', 'user__email', 'session_id'
    ]
    
    readonly_fields = [
        'created_at', 'user', 'session_id', 'ip_address', 'user_agent'
    ]
    
    ordering = ['-created_at']
    
    # Configuração de campos
    fields = [
        'user', 'session_id', 'question', 'answer', 
        'response_time', 'ip_address', 'user_agent', 'created_at'
    ]
    
    def user_display(self, obj):
        """Exibe usuário ou sessão anônima"""
        if obj.user:
            user_url = reverse('admin:authentication_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', user_url, obj.user.email)
        return f"Anônimo ({obj.session_id[:8]}...)" if obj.session_id else "Anônimo"
    user_display.short_description = 'Usuário'
    
    def question_preview(self, obj):
        """Preview da pergunta"""
        return obj.question[:50] + "..." if len(obj.question) > 50 else obj.question
    question_preview.short_description = 'Pergunta'
    
    def answer_preview(self, obj):
        """Preview da resposta"""
        if obj.answer:
            return obj.answer[:50] + "..." if len(obj.answer) > 50 else obj.answer
        return "-"
    answer_preview.short_description = 'Resposta'
    
    def get_queryset(self, request):
        """Otimiza queries"""
        return super().get_queryset(request).select_related('user')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """
    Interface administrativa para sessões de usuários anônimos
    """
    
    list_display = [
        'session_id_short', 'questions_used', 'questions_remaining_display',
        'ip_address', 'created_at', 'last_activity'
    ]
    
    list_filter = [
        'questions_used', 'created_at', 'last_activity'
    ]
    
    search_fields = [
        'session_id', 'ip_address'
    ]
    
    readonly_fields = [
        'session_id', 'created_at', 'last_activity'
    ]
    
    ordering = ['-last_activity']
    
    def session_id_short(self, obj):
        """Exibe versão curta do session_id"""
        return f"{obj.session_id[:8]}..."
    session_id_short.short_description = 'Sessão'
    
    def questions_remaining_display(self, obj):
        """Exibe perguntas restantes com cores"""
        remaining = obj.get_questions_remaining()
        color = 'green' if remaining > 2 else 'orange' if remaining > 0 else 'red'
        
        return mark_safe(
            f'<span style="color: {color};">{remaining}/4 restantes</span>'
        )
    questions_remaining_display.short_description = 'Restantes'
    
    actions = ['reset_questions']
    
    def reset_questions(self, request, queryset):
        """Reset das perguntas para sessões selecionadas"""
        count = queryset.update(questions_used=0)
        self.message_user(request, f'Reset aplicado a {count} sessões.')
    reset_questions.short_description = "Reset perguntas das sessões"


# Configurações adicionais do Admin
admin.site.site_header = "MULTI BPO ERP - Sistema de Autenticação"
admin.site.site_title = "MULTI BPO ERP"
admin.site.index_title = "Painel de Administração - Autenticação"

# Estatísticas personalizadas para o dashboard
def get_admin_stats():
    """Retorna estatísticas para exibir no admin"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    stats = {
        'total_users': User.objects.count(),
        'users_this_week': User.objects.filter(created_at__date__gte=week_ago).count(),
        'confirmed_users': User.objects.filter(email_confirmed=True).count(),
        'questions_today': LucaQuestion.objects.filter(created_at__date=today).count(),
        'active_sessions': UserSession.objects.filter(
            last_activity__gte=timezone.now() - timedelta(hours=24)
        ).count(),
    }
    
    return stats