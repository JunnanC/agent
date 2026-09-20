"""Serializers for core object-asset routes."""

from rest_framework import serializers


class DownloadGrantRequestSerializer(serializers.Serializer):
    use = serializers.ChoiceField(
        choices=["REPORT_DOWNLOAD", "ARCHIVE_EXPORT"],
    )
