from rest_framework import serializers


class WorkspaceSessionCreateRequestSerializer(serializers.Serializer):
    student_public_id = serializers.CharField(required=True)
    instance_public_id = serializers.CharField(required=True)


class WorkspaceSessionCreateResponseSerializer(serializers.Serializer):
    session_public_id = serializers.CharField(required=True)
    task_public_id = serializers.CharField(required=True)
    student_public_id = serializers.CharField(required=True)
    instance_public_id = serializers.CharField(required=True)
    token = serializers.CharField(required=False, allow_blank=True)
    replayed = serializers.BooleanField(required=True)


class WorkspaceSessionRenewRequestSerializer(serializers.Serializer):
    task_public_id = serializers.CharField(required=True)
    student_public_id = serializers.CharField(required=True)
    instance_public_id = serializers.CharField(required=True)


class WorkspaceSessionRenewResponseSerializer(serializers.Serializer):
    session_public_id = serializers.CharField(required=True)
    task_public_id = serializers.CharField(required=True)
    student_public_id = serializers.CharField(required=True)
    instance_public_id = serializers.CharField(required=True)
    token = serializers.CharField(required=True)


class WorkspaceSessionRevokeRequestSerializer(serializers.Serializer):
    student_public_id = serializers.CharField(required=True)


class WorkspaceSessionRevokeResponseSerializer(serializers.Serializer):
    session_public_id = serializers.CharField(required=True)
    revoked = serializers.BooleanField(required=True)
    audit_recorded = serializers.BooleanField(required=True)


class WorkspaceSnapshotRequestSerializer(serializers.Serializer):
    client_seq = serializers.IntegerField(min_value=0, required=True)
    payload = serializers.JSONField(required=False, default=dict)


class WorkspaceSnapshotResponseSerializer(serializers.Serializer):
    confirmed_seq = serializers.IntegerField(required=True)
    idempotent_replay = serializers.BooleanField(required=True)


class WorkspaceTokenVerifyRequestSerializer(serializers.Serializer):
    token_hash = serializers.RegexField(regex=r"^[a-f0-9]{64}$", required=True)
    task_public_id = serializers.CharField(required=True)
    student_public_id = serializers.CharField(required=True)
    instance_public_id = serializers.CharField(required=True)


class WorkspaceTokenVerifyResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField(required=True)
    task_public_id = serializers.CharField(required=True)
    student_public_id = serializers.CharField(required=True)
    instance_public_id = serializers.CharField(required=True)
    revoked = serializers.BooleanField(required=True)
