from rest_framework import serializers


class WorkspaceTokenVerifyRequestSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    task_public_id = serializers.CharField(required=True)
    student = serializers.DictField(required=True)
    instance = serializers.DictField(required=True)


class WorkspaceTokenVerifyResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField(required=True)
    task_public_id = serializers.CharField(required=True)
    student = serializers.DictField(required=True)
    instance = serializers.DictField(required=True)
    revoked = serializers.BooleanField(required=True)
