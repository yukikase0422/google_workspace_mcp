"""
Raw Google API Tool

Provides direct access to any Google API endpoint via the Discovery API.
Complements the staged `gws` tool by covering operations not defined as actions.
"""

import logging
from typing import Any, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.server import server
from auth.service_decorator import (
    _should_use_oauth21,
    _authenticate_service,
    _override_oauth21_user_email,
    get_access_token,
    get_context,
    SERVICE_CONFIGS,
)
from auth.scopes import TOOL_SCOPES_MAP, has_required_scopes
from auth.oauth_config import is_oauth21_enabled
from core.config import USER_GOOGLE_EMAIL as _ENV_USER_EMAIL

logger = logging.getLogger(__name__)

# Services available via this tool, with their broadest write scopes
_SERVICE_SCOPES: Dict[str, Dict[str, Any]] = {}
for svc_key, svc_conf in SERVICE_CONFIGS.items():
    scopes = TOOL_SCOPES_MAP.get(svc_key, [])
    _SERVICE_SCOPES[svc_key] = {
        "service": svc_conf["service"],
        "version": svc_conf["version"],
        "scopes": scopes,
    }


def _list_services() -> str:
    """Return a compact list of available services."""
    lines = ["Available services (pass as `service` parameter):\n"]
    for key, info in sorted(_SERVICE_SCOPES.items()):
        lines.append(f"  {key}: {info['service']} {info['version']}")
    lines.append(
        "\nUsage: gws_raw_api(service='drive', resource='files', method='list', params={...})"
    )
    return "\n".join(lines)


def _discover_resources(service_obj: Any, prefix: str = "") -> list[str]:
    """Walk a discovery service object and return available resource.method paths."""
    paths = []
    # List methods on current resource
    try:
        for method_name in dir(service_obj):
            if method_name.startswith("_"):
                continue
            attr = getattr(service_obj, method_name, None)
            if callable(attr):
                full = f"{prefix}.{method_name}" if prefix else method_name
                paths.append(full)
    except Exception:
        pass
    return paths


def _navigate_resource(service_obj: Any, resource_path: str) -> Any:
    """Navigate a dot-separated resource path on a service object.

    E.g. 'files' -> service.files(), 'spreadsheets.values' -> service.spreadsheets().values()
    """
    current = service_obj
    for part in resource_path.split("."):
        accessor = getattr(current, part, None)
        if accessor is None:
            raise ValueError(
                f"Resource '{part}' not found. Check the API reference for valid resources."
            )
        current = accessor()
    return current


@server.tool()
async def gws_raw_api(
    service: str = "",
    resource: str = "",
    method: str = "",
    params: Optional[Dict[str, Any]] = None,
    user_google_email: str = "",
) -> str:
    """Call any Google Workspace API endpoint directly via the Discovery API.

    Staged usage:
      1. gws_raw_api() -> list available services
      2. gws_raw_api(service="drive") -> show top-level resources
      3. gws_raw_api(service="drive", resource="files", method="list", params={...}) -> execute
    """
    # Stage 0: no service specified -> list services
    if not service:
        return _list_services()

    # Validate service
    svc_info = _SERVICE_SCOPES.get(service)
    if not svc_info:
        return f"Unknown service '{service}'. " + _list_services()

    # Resolve email
    email = user_google_email or _ENV_USER_EMAIL or ""

    # Authenticate
    try:
        use_oauth21 = await _should_use_oauth21("gws_raw_api")
        mcp_session_id = None
        authenticated_user = None

        if use_oauth21:
            try:
                ctx = get_context()
                mcp_session_id = getattr(ctx, "session_id", None) if ctx else None
            except Exception:
                pass
            try:
                token = get_access_token()
                if token and hasattr(token, "claims"):
                    authenticated_user = token.claims.get("email")
            except Exception:
                pass

            email, _ = _override_oauth21_user_email(
                use_oauth21, authenticated_user, email, ()
            )

        google_service, actual_email = await _authenticate_service(
            use_oauth21=use_oauth21,
            service_name=svc_info["service"],
            service_version=svc_info["version"],
            tool_name="gws_raw_api",
            user_google_email=email,
            resolved_scopes=svc_info["scopes"],
            mcp_session_id=mcp_session_id,
            authenticated_user=authenticated_user,
        )
    except Exception as e:
        return f"Authentication failed: {e}"

    # Stage 1: service only -> list resources
    if not resource and not method:
        try:
            paths = _discover_resources(google_service)
            resource_names = sorted(
                set(p for p in paths if not p.startswith("_") and p != "new_batch_http_request")
            )
            lines = [f"Resources and methods for {service} ({svc_info['service']} {svc_info['version']}):\n"]
            for name in resource_names:
                lines.append(f"  {name}")
            lines.append(
                f"\nUsage: gws_raw_api(service='{service}', resource='<resource>', method='<method>', params={{...}})"
            )
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing resources: {e}"

    # Stage 2: service + resource (no method) -> list methods on that resource
    if resource and not method:
        try:
            res_obj = _navigate_resource(google_service, resource)
            methods = [m for m in dir(res_obj) if not m.startswith("_") and callable(getattr(res_obj, m, None))]
            lines = [f"Methods on {service}.{resource}:\n"]
            for m in sorted(methods):
                lines.append(f"  {m}")
            lines.append(
                f"\nUsage: gws_raw_api(service='{service}', resource='{resource}', method='<method>', params={{...}})"
            )
            return "\n".join(lines)
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Error listing methods: {e}"

    # Stage 3: execute
    if not resource:
        return "Error: `resource` is required when `method` is specified."

    call_params = params or {}
    try:
        res_obj = _navigate_resource(google_service, resource)
        api_method = getattr(res_obj, method, None)
        if api_method is None:
            available = [m for m in dir(res_obj) if not m.startswith("_") and callable(getattr(res_obj, m, None))]
            return f"Method '{method}' not found on {service}.{resource}. Available: {', '.join(sorted(available))}"

        request = api_method(**call_params)
        result = request.execute()
        return str(result)
    except HttpError as e:
        return f"API error: {e.status_code} {e.reason}\n{e.error_details if hasattr(e, 'error_details') else ''}"
    except TypeError as e:
        return f"Parameter error: {e}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
