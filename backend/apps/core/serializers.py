"""Serializers for core routes."""

from rest_framework import serializers


class DownloadGrantRequestSerializer(serializers.Serializer):
    use = serializers.ChoiceField(
        choices=["REPORT_DOWNLOAD", "ARCHIVE_EXPORT"],
    )


class DownloadGrantResponseSerializer(serializers.Serializer):
    asset_id = serializers.CharField(required=True)
    one_time_token = serializers.CharField(required=True)
    expires_at = serializers.DateTimeField(required=True)
    max_uses = serializers.IntegerField(required=True)
