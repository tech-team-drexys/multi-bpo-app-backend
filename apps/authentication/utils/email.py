from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

def send_confirmation_email_to_user(user):
    """
    Envia um e-mail de confirmação para o usuário com token único.
    """
    token = str(user.email_confirmation_token)
    confirmation_url = f"{settings.FRONTEND_URL}/confirm-email?token={token}"
    
    subject = 'Confirme seu e-mail - MULTI BPO ERP'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@multibpo.com.br')
    to_email = user.email

    text_content = f"Olá {user.email}, confirme seu e-mail clicando aqui: {confirmation_url}"

    html_content = render_to_string(
        'emails/confirmation_email.html',
        {
            'user': user, 
            'confirmation_url': confirmation_url,
            'site_url': settings.FRONTEND_URL
        }
    )

    email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    email.attach_alternative(html_content, "text/html")
    email.send()
