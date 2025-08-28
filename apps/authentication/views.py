from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import permissions
from django.db import transaction
from django.utils import timezone
from .models import LucaQuestion, UserSession
from .serializers import LucaQuestionCreateSerializer, UserSessionSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

import time

import logging

from .models import User
from .serializers import UserRegistrationSerializer, EmailConfirmationSerializer, UserSerializer
from .utils.email import send_confirmation_email_to_user

logger = logging.getLogger(__name__)


@api_view(['GET'])
def health_check(request):
    """
    Endpoint de saúde da API
    GET /api/v1/auth/health/
    """
    return Response({'status': 'ok'})


@api_view(['POST'])
def logout_view(request):
    """
    Logout do usuário (JWT)
    """
    return Response({'success': True, 'message': 'Logout realizado com sucesso.'})


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        return Response({'success': True, 'message': 'Social login stub'})

class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        return Response({'success': True, 'message': 'Password reset stub'})

class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        return Response({'success': True, 'message': 'User profile stub'})



class CustomTokenObtainPairView(TokenObtainPairView):
    """
    View de login customizada (JWT)
    """
    pass


class UserRegistrationView(APIView):
    """
    Cadastro de novos usuários e envio de e-mail de confirmação
    POST /api/auth/register/def health_check(request):
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()
                    self.send_confirmation_email(user)
                    logger.info(f"Novo usuário cadastrado: {user.email}")
                    return Response({
                        'success': True,
                        'message': 'Cadastro realizado com sucesso! Verifique seu e-mail para confirmar sua conta.',
                        'user': UserSerializer(user).data,
                        'email_sent': True
                    }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Erro no cadastro: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'Erro interno no servidor. Tente novamente.',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'success': False,
            'message': 'Dados inválidos.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def send_confirmation_email(self, user):
        """Envio seguro do e-mail de confirmação"""
        try:
            send_confirmation_email_to_user(user)
            logger.info(f"E-mail de confirmação enviado para: {user.email}")
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail de confirmação: {str(e)}")


class EmailConfirmationView(APIView):
    """
    Confirmação de e-mail via token
    POST /api/auth/confirm-email/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailConfirmationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                success = serializer.confirm_email()
                user = serializer.user
                if success:
                    logger.info(f"E-mail confirmado: {user.email}")
                    return Response({
                        'success': True,
                        'message': 'E-mail confirmado com sucesso! Agora você pode fazer login.',
                        'user': UserSerializer(user).data
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'message': 'Token inválido ou expirado.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Erro na confirmação de e-mail: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'Erro interno no servidor.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'success': False,
            'message': 'Token inválido.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ResendConfirmationEmailView(APIView):
    """
    Reenvio de e-mail de confirmação
    POST /api/auth/resend-confirmation/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        if not email:
            return Response({
                'success': False,
                'message': 'E-mail é obrigatório.'
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            if user.email_confirmed:
                return Response({
                    'success': False,
                    'message': 'Este e-mail já foi confirmado.'
                }, status=status.HTTP_400_BAD_REQUEST)
            # Reenvia e-mail
            send_confirmation_email_to_user(user)
            logger.info(f"E-mail de confirmação reenviado: {email}")
            return Response({
                'success': True,
                'message': 'E-mail de confirmação reenviado com sucesso!'
            })
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Usuário não encontrado.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Erro ao reenviar e-mail: {str(e)}")
            return Response({
                'success': False,
                'message': 'Erro interno no servidor.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LucaQuestionView(APIView):
    """
    View para criar perguntas à Luca IA
    POST /api/auth/luca/question/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LucaQuestionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Pergunta inválida.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        question_text = serializer.validated_data['question']
        session_id = serializer.validated_data.get('session_id')

        # Verifica permissão para perguntar
        can_ask, error_msg = self.check_question_permission(request, session_id)
        if not can_ask:
            return Response({
                'success': False,
                'message': error_msg,
                'limit_reached': True
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Registra uso
        self.register_question_usage(request, session_id)

        # Simula resposta IA
        start_time = time.time()
        ai_response = self.get_ai_response(question_text)
        response_time = round(time.time() - start_time, 3)

        # Salva pergunta no banco
        luca_question = LucaQuestion.objects.create(
            user=request.user if request.user.is_authenticated else None,
            question=question_text,
            answer=ai_response,
            session_id=session_id or '',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            response_time=response_time
        )

        # Dados do usuário ou sessão
        user_data = UserSerializer(request.user).data if request.user.is_authenticated else None
        session_data = None
        if not request.user.is_authenticated and session_id:
            session = UserSession.objects.filter(session_id=session_id).first()
            if session:
                session_data = UserSessionSerializer(session).data

        logger.info(f"Pergunta Luca IA processada: {question_text[:50]}...")

        return Response({
            'success': True,
            'question': question_text,
            'answer': ai_response,
            'response_time': response_time,
            'user': user_data,
            'session': session_data
        })

    def check_question_permission(self, request, session_id):
        """Verifica se o usuário/sessão pode fazer pergunta"""
        if request.user.is_authenticated:
            if not request.user.can_ask_luca_question():
                return False, "Você atingiu o limite de perguntas para este período."
            return True, None

        if session_id:
            session, created = UserSession.objects.get_or_create(
                session_id=session_id,
                defaults={'ip_address': self.get_client_ip(request)}
            )
            if not session.can_ask_question():
                return False, "Você atingiu o limite de 4 perguntas gratuitas."
            return True, None

        return False, "Sessão inválida."

    def register_question_usage(self, request, session_id):
        """Incrementa contador de perguntas"""
        if request.user.is_authenticated:
            request.user.use_luca_question()
        elif session_id:
            session = UserSession.objects.filter(session_id=session_id).first()
            if session:
                session.use_question()

    def get_ai_response(self, question):
        """Simula resposta da IA"""
        return f"Luca IA: Obrigada por perguntar sobre '{question}'. Resposta simulada."

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


class LucaStatusView(APIView):
    """
    View para consultar status e limites da Luca IA
    GET /api/auth/luca/status/?session_id=<id>
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        session_id = request.GET.get('session_id')
        if request.user.is_authenticated:
            return Response({
                'success': True,
                'user_type': 'authenticated',
                'questions_remaining': request.user.get_luca_questions_remaining(),
                'questions_limit': request.user.get_luca_questions_limit(),
                'next_reset': request.user.get_next_luca_reset(),
                'user': UserSerializer(request.user).data
            })

        if not session_id:
            return Response({
                'success': False,
                'message': 'Session ID é obrigatório para usuários anônimos.'
            }, status=status.HTTP_400_BAD_REQUEST)

        session, created = UserSession.objects.get_or_create(
            session_id=session_id,
            defaults={'ip_address': request.META.get('REMOTE_ADDR')}
        )

        return Response({
            'success': True,
            'user_type': 'anonymous',
            'questions_remaining': session.get_questions_remaining(),
            'questions_limit': 4,
            'session': UserSessionSerializer(session).data
        })
