#!/usr/bin/env python
"""Django command-line entry point for the v2 platform."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "education_experiment_platform.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is not installed or the virtual environment is not activated."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
