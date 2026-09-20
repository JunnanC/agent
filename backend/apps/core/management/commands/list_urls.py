from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


class Command(BaseCommand):
    help = "List registered URL patterns, HTTP methods, and path parameters."

    def handle(self, *args, **options):
        self.stdout.write("METHOD\tURL\tPARAMETERS\tNAME")
        for method, url, parameters, name in self._patterns(
            get_resolver().url_patterns
        ):
            self.stdout.write(
                f"{method}\t{url}\t{','.join(parameters) or '-'}\t{name or '-'}"
            )

    def _patterns(self, patterns, prefix=""):
        for pattern in patterns:
            current = prefix + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                yield from self._patterns(pattern.url_patterns, current)
                continue
            if not isinstance(pattern, URLPattern):
                continue

            view = getattr(pattern.callback, "cls", pattern.callback)
            methods = [
                method.upper()
                for method in ("get", "post", "put", "patch", "delete")
                if callable(getattr(view, method, None))
            ]
            parameters = list(pattern.pattern.converters)
            for method in methods:
                yield method, current, parameters, pattern.name
