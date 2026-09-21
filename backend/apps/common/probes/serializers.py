from rest_framework import serializers


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    checks = serializers.DictField(
        child=serializers.CharField(),
        required=False,
    )


class HealthResponseSerializer(serializers.Serializer):
    data = HealthCheckSerializer()
    meta = serializers.DictField(child=serializers.CharField())
