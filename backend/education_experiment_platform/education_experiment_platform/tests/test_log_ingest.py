from education_experiment_platform.log_ingest import redact


def test_redact_masks_sensitive_fields_recursively() -> None:
    source = {
        "Authorization": "Bearer private",
        "nested": {"csrf_token": "private", "safe": "visible"},
        "message": "request rejected token=private-value",
    }

    assert redact(source) == {
        "message": "request rejected token=[REDACTED]",
        "Authorization": "[REDACTED]",
        "nested": {"csrf_token": "[REDACTED]", "safe": "visible"},
    }
