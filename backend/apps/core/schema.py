def add_trace_response_header(result, **kwargs):
    for methods in result.get("paths", {}).values():
        for method, operation in methods.items():
            if method not in {
                "get", "put", "post", "delete", "options", "head", "patch", "trace"
            }:
                continue
            for response in operation.get("responses", {}).values():
                headers = response.setdefault("headers", {})
                headers.setdefault(
                    "X-Trace-Id",
                    {
                        "description": "Trace ID for the current request.",
                        "schema": {"type": "string"},
                    },
                )
    return result
