from collections import defaultdict
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema
from apps.core.permissions import effective_permission_codenames
from apps.customers.services import effective_customer_permissions, get_customer_membership
from .serializers import MeSerializer, RefreshTokenSerializer, CurrentPermissionsSerializer
class MeView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer
    def get(self, request): return Response(MeSerializer(request.user).data)
class CurrentPermissionsView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrentPermissionsSerializer
    def get(self, request):
        matrix = defaultdict(dict)
        membership = get_customer_membership(request.user)
        codes = effective_customer_permissions(request.user, membership) if membership else effective_permission_codenames(request.user)
        for codename in codes:
            module, action = codename.split(".", 1); matrix[module][action] = True
        return Response({"is_superuser": request.user.is_superuser, "permissions": matrix})
class LogoutView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RefreshTokenSerializer
    @extend_schema(request={"application/json": {"type": "object", "properties": {"refresh": {"type": "string"}}, "required": ["refresh"]}})
    def post(self, request):
        try: RefreshToken(request.data["refresh"]).blacklist()
        except (KeyError, TokenError): return Response({"success": False, "message": "Invalid refresh token."}, status=400)
        return Response({"success": True, "message": "Logged out successfully."})
