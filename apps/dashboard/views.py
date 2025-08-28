# apps/dashboard/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
import django

@api_view(['GET'])
@permission_classes([AllowAny])
def backend_status(request):
    """
    Endpoint para verificar status do backend Django
    GET /api/v1/status/
    """
    try:
        # Teste de conexão com o banco
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = "error"

    return Response({
        "success": True,
        "message": "ERP MULTIBPO Backend Online",
        "data": {
            "backend_status": "online",
            "database_status": db_status,
            "django_version": django.get_version(),
            "apps": ["authentication", "dashboard", "documents", "clients", "chat", "utilities"]
        }
    }, status=status.HTTP_200_OK)