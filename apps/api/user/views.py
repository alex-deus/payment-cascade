import logging

from django.contrib.auth import logout
from django.utils.translation import gettext_lazy as _
from django_essentials_kit import get_object_or_none
from djoser.utils import login_user
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token as DRFToken
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt import views as simplejwt_views
from rest_framework_simplejwt.serializers import TokenRefreshSerializer, TokenVerifySerializer

from apps.users.utils import blacklist_refresh_token, issue_token_pair
from apps.users.models import User
from . import serializers

__all__ = ["SignOutView", "SignUpView", "TokenRefreshView", "TokenVerifyView", "UserProfileView"]

logger = logging.getLogger("django.request")


class SignUpView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        request_body=serializers.SignUpRequestSerializer(),
        responses={
            status.HTTP_201_CREATED: serializers.SignUpResponseSerializer(),
            status.HTTP_202_ACCEPTED: serializers.SignUpResponseSerializer(),
        },
    )
    def post(self, request, format=None):
        # Validate request data
        serializer = serializers.SignUpRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Get or create user by id
        user: User = serializer.create(serializer.validated_data)

        # Create Auth Token (legacy, сохранён на переходный период)
        token: DRFToken = login_user(request, user)

        # Выпуск пары JWT-токенов
        token_pair: dict[str, str] = issue_token_pair(user)

        # Validate response data
        response_data = {"token": token.key, **token_pair}
        serializer = serializers.SignUpResponseSerializer(data=response_data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status.HTTP_201_CREATED)


class SignOutView(APIView):
    @swagger_auto_schema(
        request_body=serializers.SignOutRequestSerializer(),
        responses={status.HTTP_202_ACCEPTED: openapi.Response(description=_("Empty response"))},
    )
    def post(self, request, format=None):
        serializer = serializers.SignOutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh: str = serializer.validated_data.get("refresh")
        if refresh:
            is_revoked: bool = blacklist_refresh_token(refresh)
            if not is_revoked:
                logger.warning(f"UserID={request.user.id} provided invalid refresh token on sign-out")

        token: DRFToken | None = get_object_or_none(DRFToken, user=request.user)
        if token:
            token.delete()
        else:
            logger.warning(f"UserID={request.user.id} has not token")

        logout(request)

        return Response({}, status.HTTP_202_ACCEPTED)


class UserProfileView(APIView):
    @swagger_auto_schema(responses={status.HTTP_200_OK: serializers.UserProfileRetrieveSerializer()})
    def get(self, request, format=None):
        serializer = serializers.UserProfileRetrieveSerializer(instance=request.user, context={"request": request})

        return Response(serializer.data)

    @swagger_auto_schema(
        query_serializer=serializers.UserProfileUpdateSerializer(),
        responses={status.HTTP_202_ACCEPTED: serializers.UserProfileRetrieveSerializer()},
    )
    def patch(self, request, *args, **kwargs):
        serializer = serializers.UserProfileUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.update(request.user, serializer.validated_data)

        request.user.refresh_from_db()
        serializer = serializers.UserProfileRetrieveSerializer(instance=request.user)

        return Response(serializer.data, status.HTTP_202_ACCEPTED)

    @swagger_auto_schema(responses={status.HTTP_204_NO_CONTENT: openapi.Response(description=_("Empty response"))})
    def delete(self, request, *args, **kwargs):
        request.user.delete()

        return Response({}, status.HTTP_204_NO_CONTENT)


class TokenRefreshView(simplejwt_views.TokenRefreshView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        request_body=TokenRefreshSerializer,
        responses={status.HTTP_200_OK: serializers.TokenPairSerializer()},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TokenVerifyView(simplejwt_views.TokenVerifyView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        request_body=TokenVerifySerializer,
        responses={status.HTTP_200_OK: openapi.Response(description=_("Empty response"))},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
