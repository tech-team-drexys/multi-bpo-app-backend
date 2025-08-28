from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, LucaQuestion, UserSession
import re


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    captcha_token = serializers.CharField(write_only=True)
    accept_terms = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = [
            'email', 'whatsapp', 'password', 'password_confirm',
            'captcha_token', 'accept_terms', 'registration_method'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'whatsapp': {'required': True},
            'registration_method': {'default': 'email'}
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este e-mail já está cadastrado no sistema.")
        return value.lower().strip()

    def validate_whatsapp(self, value):
        numbers_only = re.sub(r'\D', '', value)
        if len(numbers_only) < 10 or len(numbers_only) > 11:
            raise serializers.ValidationError("WhatsApp deve ter 10 ou 11 dígitos (com ou sem DDD).")
        if len(numbers_only) == 11:
            formatted = f"({numbers_only[:2]}) {numbers_only[2:7]}-{numbers_only[7:]}"
        else:
            formatted = f"({numbers_only[:2]}) {numbers_only[2:6]}-{numbers_only[6:]}"
        return formatted

    def validate_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("É necessário aceitar os termos de uso e política de privacidade.")
        return value

    def validate_captcha_token(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("É necessário resolver o captcha de verificação.")
        # TODO: Implementar validação real com Cloudflare Turnstile
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': "As senhas não coincidem."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data.pop('captcha_token')
        validated_data.pop('accept_terms')

        password = validated_data.pop('password')
        user = User.objects.create_user(username=validated_data['email'], **validated_data)
        user.set_password(password)
        user.save()
        return user


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=['google', 'facebook'])
    access_token = serializers.CharField()
    email = serializers.EmailField()
    name = serializers.CharField(required=False)

    def validate_email(self, value):
        return value.lower().strip()

    def create_or_get_user(self):
        validated_data = self.validated_data
        email = validated_data['email']
        provider = validated_data['provider']

        try:
            user = User.objects.get(email=email)
            if user.registration_method == 'email':
                user.registration_method = provider
                user.email_confirmed = True
                user.save()
            return user
        except User.DoesNotExist:
            name_parts = validated_data.get('name', '').split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                whatsapp='',
                registration_method=provider,
                email_confirmed=True,
                user_type='registered'
            )
            return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    captcha_token = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs):
        captcha_token = attrs.get('captcha_token')
        if captcha_token:
            # TODO: validar token real com Cloudflare Turnstile
            pass

        data = super().validate(attrs)
        user = self.user
        if not user.email_confirmed and user.registration_method == 'email':
            raise serializers.ValidationError({
                'email': 'É necessário confirmar seu e-mail antes do primeiro login.'
            })

        data['user'] = UserSerializer(user).data
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['user_type'] = user.user_type
        token['email_confirmed'] = user.email_confirmed
        remaining = user.get_luca_questions_remaining()
        token['luca_questions_remaining'] = None if remaining == float('inf') else remaining
        return token


class UserSerializer(serializers.ModelSerializer):
    luca_questions_remaining = serializers.SerializerMethodField()
    luca_questions_limit = serializers.SerializerMethodField()
    next_luca_reset = serializers.SerializerMethodField()
    allowed_erp_modules = serializers.SerializerMethodField()
    blocked_erp_modules = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'whatsapp',
            'user_type', 'registration_method', 'email_confirmed',
            'created_at', 'luca_questions_remaining', 'luca_questions_limit',
            'next_luca_reset', 'allowed_erp_modules', 'blocked_erp_modules'
        ]
        read_only_fields = [
            'id', 'user_type', 'registration_method', 'email_confirmed', 'created_at'
        ]

    def get_luca_questions_remaining(self, obj):
        remaining = obj.get_luca_questions_remaining()
        return None if remaining == float('inf') else remaining

    def get_luca_questions_limit(self, obj):
        limit = obj.get_luca_questions_limit()
        return None if limit == float('inf') else limit

    def get_next_luca_reset(self, obj):
        return obj.get_next_luca_reset()

    def get_allowed_erp_modules(self, obj):
        return obj.get_allowed_erp_modules()

    def get_blocked_erp_modules(self, obj):
        return obj.get_blocked_erp_modules()


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    captcha_token = serializers.CharField(write_only=True)

    def validate_email(self, value):
        email = value.lower().strip()
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Não encontramos nenhuma conta com este e-mail.")
        return email

    def validate_captcha_token(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("É necessário resolver o captcha de verificação.")
        return value


class EmailConfirmationSerializer(serializers.Serializer):
    token = serializers.UUIDField()

    def validate_token(self, value):
        try:
            user = User.objects.get(email_confirmation_token=value)
            if user.email_confirmed:
                raise serializers.ValidationError("Este e-mail já foi confirmado.")
            if user.is_email_confirmation_expired():
                raise serializers.ValidationError("Token de confirmação expirou.")
            self.user = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Token de confirmação inválido.")

    def confirm_email(self):
        return self.user.confirm_email(self.validated_data['token'])


class LucaQuestionSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = LucaQuestion
        fields = ['id', 'question', 'answer', 'created_at', 'response_time', 'user_display']
        read_only_fields = ['id', 'created_at', 'user_display']

    def get_user_display(self, obj):
        if obj.user:
            return f"{obj.user.email}"
        return f"Anônimo ({obj.session_id[:8]}...)" if obj.session_id else "Anônimo"


class LucaQuestionCreateSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)
    session_id = serializers.CharField(required=False, max_length=100)

    def validate_question(self, value):
        question = value.strip()
        if len(question) < 3:
            raise serializers.ValidationError("A pergunta deve ter pelo menos 3 caracteres.")
        return question


class UserSessionSerializer(serializers.ModelSerializer):
    questions_remaining = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = ['session_id', 'questions_used', 'questions_remaining', 'created_at', 'last_activity']
        read_only_fields = ['created_at', 'last_activity']

    def get_questions_remaining(self, obj):
        return obj.get_questions_remaining()


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'whatsapp']

    def validate_whatsapp(self, value):
        if not value:
            return value
        numbers_only = re.sub(r'\D', '', value)
        if len(numbers_only) < 10 or len(numbers_only) > 11:
            raise serializers.ValidationError("WhatsApp deve ter 10 ou 11 dígitos (com ou sem DDD).")
        if len(numbers_only) == 11:
            formatted = f"({numbers_only[:2]}) {numbers_only[2:7]}-{numbers_only[7:]}"
        else:
            formatted = f"({numbers_only[:2]}) {numbers_only[2:6]}-{numbers_only[6:]}"
        return formatted
