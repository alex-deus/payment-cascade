from drf_dynamic_fields import DynamicFieldsMixin
from rest_framework import serializers

from apps.users.models import User


__all__ = [
    "SignOutRequestSerializer",
    "SignUpRequestSerializer",
    "SignUpResponseSerializer",
    "TokenPairSerializer",
    "UserProfileRetrieveSerializer",
    "UserProfileUpdateSerializer",
]


class SignUpRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["name"]


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(required=True)
    refresh = serializers.CharField(required=True)


class SignUpResponseSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=40, max_length=40, required=True)
    access = serializers.CharField(required=True)
    refresh = serializers.CharField(required=True)


class SignOutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True)


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["name"]


class UserProfileRetrieveSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "role", "email", "name"]
