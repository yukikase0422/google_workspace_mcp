"""
Raw Google API Tool

Provides direct access to any Google API endpoint via the Discovery API.
Complements the staged `gws` tool by covering operations not defined as actions.
"""

import logging
from typing import Any, Dict, Optional

from googleapiclient.errors import HttpError

from core.server import server
from auth.service_decorator import SERVICE_CONFIGS
from auth.google_auth import (
    get_authenticated_google_service,
    GoogleAuthenticationError,
)
from auth.oauth_config import is_oauth21_enabled
from auth.scopes import TOOL_SCOPES_MAP
from core.config import USER_GOOGLE_EMAIL as _ENV_USER_EMAIL

logger = logging.getLogger(__name__)

# Build service info dynamically from existing configs
_SERVICE_INFO: Dict[str, Dict[str, Any]] = {}
for svc_key, svc_conf in SERVICE_CONFIGS.items():
    _SERVICE_INFO[svc_key] = {
        "service": svc_conf["service"],
        "version": svc_conf["version"],
        "scopes": TOOL_SCOPES_MAP.get(svc_key, []),
    }


def _list_services() -> str:
    lines = ["Available services (pass as `service`):\n"]
    for key, info in sorted(_SERVICE_INFO.items()):
        lines.append(f"  {key}: {info['service']} {info['version']}")
    lines.append(
        "\nUsage: gws_raw_api(service='drive', resource='files', method='list', params={...})"
    )
    return "\n".join(lines)


def _discover_resources(service_obj: Any) -> list[str]:
    """List available resource/method names on a service object."""
    return sorted(
        name for name in dir(service_obj)
        if not name.startswith("_") and name != "new_batch_http_request" and callable(getattr(service_obj, name, None))
    )


def _navigate_resource(service_obj: Any, resource_path: str) -> Any:
    """Navigate a dot-separated resource path (e.g. 'spreadsheets.values')."""
    current = service_obj
    for part in resource_path.split("."):
        accessor = getattr(current, part, None)
        if accessor is None:
            raise ValueError(
                f"Resource '{part}' not found. Check the API reference for valid resources."
            )
        current = accessor()
    return current


async def _get_service(svc_info: dict, email: str, tool_name: str = "gws_raw_api"):
    """Authenticate and return (google_service, actual_email).

    Uses OAuth 2.1 when enabled (claude.ai custom connector path),
    otherwise falls back to legacy OAuth 2.0.
    """
    if is_oauth21_enabled():
        from auth.service_decorator import get_authenticated_google_service_oauth21
        from fastmcp.server.dependencies import get_access_token

        auth_token_email = None
        try:
            token = get_access_token()
            if token and hasattr(token, "claims"):
                auth_token_email = token.claims.get("email")
        except Exception:
            pass

        resolved_email = auth_token_email or email
        return await get_authenticated_google_service_oauth21(
            service_name=svc_info["service"],
            version=svc_info["version"],
            tool_name=tool_name,
            user_google_email=resolved_email,
            required_scopes=svc_info["scopes"],
            auth_token_email=auth_token_email,
        )
    else:
        return await get_authenticated_google_service(
            service_name=svc_info["service"],
            version=svc_info["version"],
            tool_name=tool_name,
            user_google_email=email,
            required_scopes=svc_info["scopes"],
        )


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
    # Stage 0: list services
    if not service:
        return _list_services()

    svc_info = _SERVICE_INFO.get(service)
    if not svc_info:
        return f"Unknown service '{service}'. " + _list_services()

    email = user_google_email or _ENV_USER_EMAIL or ""

    # Authenticate
    try:
        google_service, actual_email = await _get_service(svc_info, email)
    except GoogleAuthenticationError as e:
        return f"Authentication failed: {e}"
    except Exception as e:
        return f"Authentication failed: {type(e).__name__}: {e}"

    # Stage 1: list resources
    if not resource and not method:
        try:
            names = _discover_resources(google_service)
            lines = [f"Resources/methods for {service} ({svc_info['service']} {svc_info['version']}):\n"]
            for name in names:
                lines.append(f"  {name}")
            lines.append(f"\nUsage: gws_raw_api(service='{service}', resource='<name>', method='<method>', params={{...}})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing resources: {e}"

    # Stage 2: list methods on a resource
    if resource and not method:
        try:
            res_obj = _navigate_resource(google_service, resource)
            methods = sorted(
                m for m in dir(res_obj)
                if not m.startswith("_") and callable(getattr(res_obj, m, None))
            )
            lines = [f"Methods on {service}.{resource}:\n"]
            for m in methods:
                lines.append(f"  {m}")
            lines.append(f"\nUsage: gws_raw_api(service='{service}', resource='{resource}', method='<method>', params={{...}})")
            return "\n".join(lines)
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Error: {e}"

    # Stage 3: execute
    if not resource:
        return "Error: `resource` is required when `method` is specified."

    call_params = params or {}
    try:
        res_obj = _navigate_resource(google_service, resource)
        api_method = getattr(res_obj, method, None)
        if api_method is None:
            available = sorted(
                m for m in dir(res_obj)
                if not m.startswith("_") and callable(getattr(res_obj, m, None))
            )
            return f"Method '{method}' not found on {service}.{resource}. Available: {', '.join(available)}"

        request = api_method(**call_params)
        result = request.execute()
        return str(result)
    except HttpError as e:
        return f"API error: {e.status_code} {e.reason}\n{getattr(e, 'error_details', '')}"
    except TypeError as e:
        return f"Parameter error: {e}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
