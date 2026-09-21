from rest_framework import serializers


class TraceMetaSerializer(serializers.Serializer):
    trace_id = serializers.CharField()


class HealthDataSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    version = serializers.CharField()
    openapi_revision = serializers.CharField()
    git_revision = serializers.CharField()
    portal = serializers.CharField(allow_null=True)


class HealthResponseSerializer(serializers.Serializer):
    data = HealthDataSerializer()
    meta = TraceMetaSerializer()


class ReadinessChecksSerializer(serializers.Serializer):
    mysql = serializers.CharField()


class ReadinessDataSerializer(serializers.Serializer):
    status = serializers.CharField()
    checks = ReadinessChecksSerializer()


class ReadinessResponseSerializer(serializers.Serializer):
    data = ReadinessDataSerializer()
    meta = TraceMetaSerializer()


class ErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    detail = serializers.DictField()
    trace_id = serializers.CharField()
    retryable = serializers.BooleanField()


class ErrorEnvelopeSerializer(serializers.Serializer):
    error = ErrorBodySerializer()
