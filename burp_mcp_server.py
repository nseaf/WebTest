# burp_mcp_server.py
from __future__ import annotations

import asyncio
import os
import platform
import signal
import sys
from typing import Optional

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

BURP_BRIDGE_URL = os.getenv("BURP_BRIDGE_URL", "http://localhost:8090")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("MONGO_DB_NAME", "burpbridge")
REPLAY_COLLECTION_NAME = "replays"

app = FastMCP("BurpBridge-MCP")

_mongo_client = None
_replay_collection = None


def _get_replay_collection():
    global _mongo_client, _replay_collection
    if _replay_collection is None:
        from pymongo import MongoClient

        _mongo_client = MongoClient(MONGO_URI)
        db = _mongo_client[DATABASE_NAME]
        _replay_collection = db[REPLAY_COLLECTION_NAME]
    return _replay_collection


def _close_mongo_client():
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


def _safe_get_field(data: dict, *field_names: str, default=None):
    if data is None:
        return default

    for name in field_names:
        value = data.get(name)
        if value is not None:
            return value
    return default


def _extract_history_fields(data: dict) -> dict:
    if data is None:
        return {}

    return {
        "id": _safe_get_field(data, "id", "_id"),
        "url": _safe_get_field(data, "url", "URL"),
        "method": _safe_get_field(data, "method"),
        "response_status_code": _safe_get_field(
            data, "responseStatusCode", "response_status_code", "statusCode", "status_code"
        ),
        "timestamp_ms": _safe_get_field(data, "timestampMs", "timestamp_ms"),
        "timestamp": _safe_get_field(data, "timestamp"),
        "request_raw": _safe_get_field(data, "requestRaw", "request_raw"),
        "response_summary": _safe_get_field(data, "responseSummary", "response_summary"),
        "has_large_response_body": _safe_get_field(
            data, "hasLargeResponseBody", "has_large_response_body"
        ),
        "response_body_length": _safe_get_field(
            data, "responseBodyLength", "response_body_length"
        ),
        "capture_source": _safe_get_field(data, "captureSource", "capture_source"),
        "intercepted": _safe_get_field(data, "intercepted"),
        "dropped": _safe_get_field(data, "dropped"),
        "intercept_rule": _safe_get_field(data, "interceptRule", "intercept_rule"),
        "intercept_task_id": _safe_get_field(data, "interceptTaskId", "intercept_task_id"),
    }


async def _request_json(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    timeout: float = 10.0,
) -> tuple[httpx.Response, dict]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method=method,
            url=f"{BURP_BRIDGE_URL}{path}",
            params=params,
            json=json_body,
        )
        data = {}
        try:
            data = response.json()
        except Exception:
            data = {}
        return response, data


class SyncHistoryInput(BaseModel):
    host: str
    methods: str | None = None
    path: str | None = None
    status: int | None = None
    require_response: bool | None = None
    exclude_mime: str | None = None
    include_html: bool | None = None
    no_default_mime: bool | None = None


class ConfigureAutoSyncInput(BaseModel):
    enabled: bool
    host: str | None = None
    methods: list[str] | None = None
    path_pattern: str | None = None
    status_code: int | None = None
    require_response: bool | None = None


class ListHistoryInput(BaseModel):
    host: str | None = None
    path: str | None = None
    method: str | None = None
    page: int = 1
    page_size: int = 20


class GetHistoryDetailInput(BaseModel):
    history_id: str


class ConfigureAuthInput(BaseModel):
    role: str
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None


class DeleteRoleInput(BaseModel):
    role: str


class ImportPlaywrightCookiesInput(BaseModel):
    role: str
    cookies: list[dict]
    merge_with_existing: bool = True


class ReplayRequestInput(BaseModel):
    history_entry_id: str | None = None
    replay_id: str | None = None
    target_role: str
    modifications: dict | None = None


class ReplayRequestsInput(BaseModel):
    history_entry_ids: list[str] | None = None
    replay_ids: list[str] | None = None
    target_roles: list[str]
    modifications: dict | None = None
    stop_on_error: bool = False


class GetReplayResultInput(BaseModel):
    replay_id: str


class StartInterceptInput(BaseModel):
    path: str


def _query_replay_result_sync(replay_id_str: str) -> dict:
    from bson import ObjectId

    collection = _get_replay_collection()
    try:
        query_filter = {"_id": ObjectId(replay_id_str)}
    except Exception:
        query_filter = {"replayId": replay_id_str}

    document = collection.find_one(query_filter)
    if document:
        doc_id = str(document.get("_id"))
        document.pop("_id", None)
        document["id"] = doc_id
        return {
            "status": "success",
            "found_document_id": doc_id,
            "replay_data": document,
            "message": f"Found replay result for ID '{replay_id_str}'.",
        }
    return {
        "status": "not_found",
        "message": (
            f"No replay result found for ID '{replay_id_str}' "
            f"in the '{DATABASE_NAME}.{REPLAY_COLLECTION_NAME}' collection."
        ),
    }


@app.tool(
    name="check_burp_health",
    description="Check BurpBridge service health and Burp version information.",
)
async def check_burp_health() -> dict:
    try:
        response, data = await _request_json("GET", "/health", timeout=10.0)
        response.raise_for_status()
        return {
            "status": "success",
            "service": data.get("plugin"),
            "burp_version": data.get("burpVersion"),
            "raw_response": data,
        }
    except httpx.HTTPStatusError as e:
        return {
            "status": "error",
            "message": f"Health check failed with status {e.response.status_code}",
            "details": e.response.text,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during health check: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during health check: {str(e)}"}


@app.tool(
    name="sync_proxy_history_with_filters",
    description="Sync filtered Burp Proxy history records to BurpBridge storage.",
)
async def sync_proxy_history_with_filters(
    host: str,
    methods: str | None = None,
    path: str | None = None,
    status: int | None = None,
    require_response: bool | None = None,
    exclude_mime: str | None = None,
    include_html: bool | None = None,
    no_default_mime: bool | None = None,
) -> dict:
    validated = SyncHistoryInput(
        host=host,
        methods=methods,
        path=path,
        status=status,
        require_response=require_response,
        exclude_mime=exclude_mime,
        include_html=include_html,
        no_default_mime=no_default_mime,
    )

    params = {"host": validated.host}
    if validated.methods is not None:
        params["methods"] = validated.methods
    if validated.path is not None:
        params["path"] = validated.path
    if validated.status is not None:
        params["status"] = str(validated.status)
    if validated.require_response is not None:
        params["requireResponse"] = str(validated.require_response).lower()
    if validated.exclude_mime is not None:
        params["exclude_mime"] = validated.exclude_mime
    if validated.include_html is not None:
        params["include_html"] = str(validated.include_html).lower()
    if validated.no_default_mime is not None:
        params["no_default_mime"] = str(validated.no_default_mime).lower()

    try:
        response, data = await _request_json("POST", "/sync", params=params, timeout=30.0)
        response.raise_for_status()
        if data.get("status") == "ok":
            return {
                "status": "success",
                "synced_count": data.get("synced_count", 0),
                "applied_filters": data.get("filters", {}),
                "sync_timestamp": data.get("SyncTimestamp"),
                "message": f"Successfully synced {data.get('synced_count', 0)} requests.",
            }
        return {
            "status": "warning",
            "message": "Request succeeded but returned an unexpected format.",
            "raw_data": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Sync failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during sync: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during sync: {str(e)}"}


@app.tool(
    name="configure_auto_sync",
    description="Enable or disable BurpBridge auto-sync with optional filters.",
)
async def configure_auto_sync(
    enabled: bool,
    host: str | None = None,
    methods: list[str] | None = None,
    path_pattern: str | None = None,
    status_code: int | None = None,
    require_response: bool | None = None,
) -> dict:
    validated = ConfigureAutoSyncInput(
        enabled=enabled,
        host=host,
        methods=methods,
        path_pattern=path_pattern,
        status_code=status_code,
        require_response=require_response,
    )

    payload = {
        "enabled": validated.enabled,
        "host": validated.host or "",
        "methods": validated.methods or [],
        "path_pattern": validated.path_pattern or "",
        "status_code": validated.status_code or 0,
        "require_response": (
            validated.require_response if validated.require_response is not None else True
        ),
    }

    try:
        response, data = await _request_json("POST", "/sync/auto", json_body=payload, timeout=10.0)
        response.raise_for_status()
        if data.get("status") == "ok":
            return {
                "status": "success",
                "auto_sync_enabled": data.get("auto_sync_enabled"),
                "config": data.get("config"),
                "message": f"Auto-sync {'enabled' if validated.enabled else 'disabled'} successfully.",
            }
        return {
            "status": "warning",
            "message": "Request succeeded but returned an unexpected format.",
            "raw_data": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Auto-sync config failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@app.tool(
    name="get_auto_sync_status",
    description="Get the current BurpBridge auto-sync status and counters.",
)
async def get_auto_sync_status() -> dict:
    try:
        response, data = await _request_json("GET", "/sync/auto/status", timeout=10.0)
        response.raise_for_status()
        if data.get("status") == "ok":
            return {
                "status": "success",
                "auto_sync_enabled": data.get("auto_sync_enabled"),
                "synced_count": data.get("synced_count", 0),
                "config": data.get("config"),
                "message": (
                    f"Auto-sync is {'enabled' if data.get('auto_sync_enabled') else 'disabled'}. "
                    f"Total synced: {data.get('synced_count', 0)} requests."
                ),
            }
        return {
            "status": "warning",
            "message": "Request succeeded but returned an unexpected format.",
            "raw_data": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Getting auto-sync status failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@app.tool(
    name="list_paginated_http_history",
    description="List paginated BurpBridge HTTP history with optional filters.",
)
async def list_paginated_http_history(
    host: str | None = None,
    path: str | None = None,
    method: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    validated = ListHistoryInput(
        host=host, path=path, method=method, page=page, page_size=page_size
    )

    params = {}
    if validated.host:
        params["host"] = validated.host
    if validated.path:
        params["path"] = validated.path
    if validated.method:
        params["method"] = validated.method
    params["page"] = max(1, validated.page)
    params["page_size"] = min(max(1, validated.page_size), 100)

    try:
        response, data = await _request_json("GET", "/history", params=params, timeout=10.0)
        response.raise_for_status()
        items = data.get("items", [])

        processed_items = []
        for item in items:
            extracted = _extract_history_fields(item)
            processed_items.append(
                {
                    "id": extracted["id"],
                    "url": extracted["url"],
                    "method": extracted["method"],
                    "response_status_code": extracted["response_status_code"],
                    "timestamp_ms": extracted["timestamp_ms"],
                    "capture_source": extracted["capture_source"],
                    "intercepted": extracted["intercepted"],
                    "dropped": extracted["dropped"],
                }
            )

        warnings = []
        if items:
            sample = items[0]
            available_fields = list(sample.keys())
            expected_fields = ["id", "url", "method", "responseStatusCode", "timestampMs"]
            missing = [field for field in expected_fields if field not in available_fields]
            if missing:
                warnings.append(f"Expected fields not found: {missing}")
                warnings.append(f"Available fields: {available_fields}")

        return {
            "status": "success",
            "total_records": data.get("total", 0),
            "current_page": data.get("page", 1),
            "page_size": data.get("page_size", 20),
            "returned_items_count": len(items),
            "items_preview": processed_items,
            "full_items_raw": items,
            "debug_warnings": warnings if warnings else None,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Listing history failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during listing: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during listing: {str(e)}"}


@app.tool(
    name="get_http_request_detail",
    description="Get a full HTTP history entry detail by BurpBridge history ID.",
)
async def get_http_request_detail(history_id: str) -> dict:
    validated = GetHistoryDetailInput(history_id=history_id)
    trimmed_history_id = validated.history_id.strip()

    try:
        response, data = await _request_json("GET", f"/history/{trimmed_history_id}", timeout=10.0)
        if response.status_code == 404:
            return {
                "status": "error",
                "message": f"History entry with ID '{trimmed_history_id}' not found.",
            }

        response.raise_for_status()
        extracted = _extract_history_fields(data)
        request_raw = extracted.get("request_raw") or ""
        preview = request_raw[:200] + ("..." if len(request_raw) > 200 else "")

        warnings = []
        available_fields = list(data.keys())
        expected_fields = ["id", "url", "method", "responseStatusCode", "timestampMs", "requestRaw"]
        missing = [field for field in expected_fields if field not in available_fields]
        if missing:
            warnings.append(f"Expected fields not found: {missing}")
            warnings.append(f"Available fields: {available_fields}")

        if extracted.get("response_status_code") in (0, None, -1):
            warnings.append(
                f"response_status_code appears to be default/missing: {extracted.get('response_status_code')}"
            )
        if not extracted.get("url"):
            warnings.append("url field is empty")
        if not extracted.get("method"):
            warnings.append("method field is empty")
        if not extracted.get("request_raw"):
            warnings.append("request_raw field is empty")

        return {
            "status": "success",
            "id": extracted.get("id"),
            "url": extracted.get("url"),
            "method": extracted.get("method"),
            "response_status_code": extracted.get("response_status_code"),
            "response_status": extracted.get("response_status_code"),
            "timestamp_ms": extracted.get("timestamp_ms"),
            "timestamp": extracted.get("timestamp"),
            "request_raw_preview": preview,
            "request_raw": request_raw,
            "response_summary": extracted.get("response_summary"),
            "has_large_response_body": extracted.get("has_large_response_body"),
            "response_body_length": extracted.get("response_body_length"),
            "capture_source": extracted.get("capture_source"),
            "intercepted": extracted.get("intercepted"),
            "dropped": extracted.get("dropped"),
            "intercept_rule": extracted.get("intercept_rule"),
            "intercept_task_id": extracted.get("intercept_task_id"),
            "debug_warnings": warnings if warnings else None,
            "debug_available_fields": available_fields,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Fetching detail failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during fetch: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during fetch: {str(e)}"}


@app.tool(
    name="debug_raw_history_entry",
    description="Debug helper that returns the raw BurpBridge history entry payload.",
)
async def debug_raw_history_entry(history_id: str) -> dict:
    validated = GetHistoryDetailInput(history_id=history_id)
    trimmed_history_id = validated.history_id.strip()

    try:
        response, data = await _request_json("GET", f"/history/{trimmed_history_id}", timeout=10.0)
        if response.status_code == 404:
            return {
                "status": "error",
                "message": f"History entry with ID '{trimmed_history_id}' not found.",
            }

        response.raise_for_status()
        return {
            "status": "success",
            "raw_response": data,
            "field_names": list(data.keys()) if isinstance(data, dict) else "Not a dict",
            "field_types": (
                {key: type(value).__name__ for key, value in data.items()}
                if isinstance(data, dict)
                else "N/A"
            ),
        }
    except Exception as e:
        return {"status": "error", "message": f"Debug fetch failed: {str(e)}"}


@app.tool(
    name="configure_authentication_context",
    description="Configure BurpBridge authentication context for a role.",
)
async def configure_authentication_context(
    role: str,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> dict:
    validated = ConfigureAuthInput(role=role, headers=headers, cookies=cookies)
    payload = {
        "role": validated.role,
        "headers": validated.headers or {},
        "cookies": validated.cookies or {},
    }

    try:
        response, data = await _request_json("POST", "/auth/config", json_body=payload, timeout=10.0)
        response.raise_for_status()
        if data.get("status") == "ok":
            return {
                "status": "success",
                "configured_role": data.get("role"),
                "message": f"Authentication context configured for role '{validated.role}'.",
            }
        return {
            "status": "warning",
            "message": "Request succeeded but returned an unexpected format.",
            "raw_data": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Configuring auth failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during config: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during config: {str(e)}"}


@app.tool(
    name="list_configured_roles",
    description="List configured BurpBridge authentication roles.",
)
async def list_configured_roles() -> dict:
    try:
        response, data = await _request_json("GET", "/auth/roles", timeout=10.0)
        response.raise_for_status()
        roles = data.get("roles", [])
        return {
            "status": "success",
            "roles": roles,
            "count": len(roles),
            "message": f"Found {len(roles)} configured role(s)." if roles else "No roles configured yet.",
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Listing roles failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@app.tool(
    name="import_playwright_cookies",
    description="Import Playwright-format cookies into a BurpBridge authentication role.",
)
async def import_playwright_cookies(
    role: str,
    cookies: list[dict],
    merge_with_existing: bool = True,
) -> dict:
    validated = ImportPlaywrightCookiesInput(
        role=role, cookies=cookies, merge_with_existing=merge_with_existing
    )

    burpbridge_cookies = {}
    for cookie in validated.cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value:
            burpbridge_cookies[name] = value

    if not burpbridge_cookies:
        return {
            "status": "warning",
            "message": "No valid cookies found in Playwright format.",
            "imported_count": 0,
        }

    payload = {"role": validated.role, "headers": {}, "cookies": burpbridge_cookies}

    try:
        if validated.merge_with_existing:
            await _request_json("GET", "/auth/roles", timeout=10.0)

        response, data = await _request_json("POST", "/auth/config", json_body=payload, timeout=10.0)
        response.raise_for_status()
        if data.get("status") == "ok":
            return {
                "status": "success",
                "configured_role": validated.role,
                "imported_cookies_count": len(burpbridge_cookies),
                "imported_cookies": list(burpbridge_cookies.keys()),
                "message": (
                    f"Successfully imported {len(burpbridge_cookies)} cookies for role "
                    f"'{validated.role}'."
                ),
            }
        return {
            "status": "warning",
            "message": "Request succeeded but returned an unexpected format.",
            "raw_data": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Import failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during import: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during import: {str(e)}"}


@app.tool(
    name="delete_authentication_context",
    description="Delete a BurpBridge authentication role configuration.",
)
async def delete_authentication_context(role: str) -> dict:
    validated = DeleteRoleInput(role=role)
    trimmed_role = validated.role.strip()

    try:
        response, data = await _request_json(
            "DELETE", f"/auth/roles/{trimmed_role}", timeout=10.0
        )
        if response.status_code == 404:
            return {"status": "not_found", "message": f"Role '{trimmed_role}' not found."}

        response.raise_for_status()
        return {
            "status": "success",
            "deleted_role": data.get("deleted_role"),
            "message": f"Authentication context for role '{trimmed_role}' has been deleted.",
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Deleting role failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@app.tool(
    name="replay_http_request_as_role",
    description=(
        "Replay a captured request as a target role, from either history_entry_id or replay_id."
    ),
)
async def replay_http_request_as_role(
    target_role: str,
    history_entry_id: str | None = None,
    replay_id: str | None = None,
    modifications: dict | None = None,
) -> dict:
    validated = ReplayRequestInput(
        history_entry_id=history_entry_id,
        replay_id=replay_id,
        target_role=target_role,
        modifications=modifications,
    )

    has_history_id = validated.history_entry_id is not None and validated.history_entry_id.strip() != ""
    has_replay_id = validated.replay_id is not None and validated.replay_id.strip() != ""

    if not has_history_id and not has_replay_id:
        return {"status": "error", "message": "Missing required field: history_entry_id or replay_id"}
    if has_history_id and has_replay_id:
        return {"status": "error", "message": "Only one of history_entry_id or replay_id is allowed"}

    payload = {"target_role": validated.target_role}
    if has_history_id:
        payload["history_entry_id"] = validated.history_entry_id.strip()
    else:
        payload["replay_id"] = validated.replay_id.strip()
    if validated.modifications is not None:
        payload["modifications"] = validated.modifications

    try:
        response, data = await _request_json("POST", "/scan/single", json_body=payload, timeout=15.0)
        response.raise_for_status()
        mode_desc = "history entry" if has_history_id else "replay record"
        source_id = validated.history_entry_id if has_history_id else validated.replay_id
        return {
            "status": "success",
            "replay_id": data.get("replay_id"),
            "queue_status": data.get("status"),
            "source_mode": mode_desc,
            "message": (
                f"Replay initiated with ID '{data.get('replay_id')}' from {mode_desc} "
                f"'{source_id}' as role '{validated.target_role}'. Use the replay_id to check results."
            ),
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Replay request failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during replay: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during replay: {str(e)}"}


@app.tool(
    name="replay_requests",
    description="Replay multiple requests across one or more target roles.",
)
async def replay_requests(
    target_roles: list[str],
    history_entry_ids: list[str] | None = None,
    replay_ids: list[str] | None = None,
    modifications: dict | None = None,
    stop_on_error: bool = False,
) -> dict:
    validated = ReplayRequestsInput(
        history_entry_ids=history_entry_ids,
        replay_ids=replay_ids,
        target_roles=target_roles,
        modifications=modifications,
        stop_on_error=stop_on_error,
    )

    has_history_ids = validated.history_entry_ids is not None and len(validated.history_entry_ids) > 0
    has_replay_ids = validated.replay_ids is not None and len(validated.replay_ids) > 0

    if not has_history_ids and not has_replay_ids:
        return {"status": "error", "message": "Missing required field: history_entry_ids or replay_ids"}
    if has_history_ids and has_replay_ids:
        return {"status": "error", "message": "Only one of history_entry_ids or replay_ids is allowed"}
    if not validated.target_roles:
        return {"status": "error", "message": "target_roles must be a non-empty list"}

    request_ids = validated.history_entry_ids if has_history_ids else validated.replay_ids
    id_type = "history_entry_id" if has_history_ids else "replay_id"
    source_type = "history" if has_history_ids else "replay"

    tasks = [(req_id, role) for req_id in request_ids for role in validated.target_roles]
    total_combinations = len(tasks)

    async def replay_single(req_id: str, role: str) -> dict:
        payload = {id_type: req_id, "target_role": role}
        if validated.modifications is not None:
            payload["modifications"] = validated.modifications

        try:
            response, data = await _request_json(
                "POST", "/scan/single", json_body=payload, timeout=15.0
            )
            response.raise_for_status()
            return {
                "request_id": req_id,
                "role": role,
                "replay_id": data.get("replay_id"),
                "status": "success",
            }
        except httpx.HTTPStatusError as e:
            try:
                error_msg = e.response.json().get("error", e.response.text)
            except Exception:
                error_msg = e.response.text
            return {
                "request_id": req_id,
                "role": role,
                "status": "error",
                "error": error_msg,
                "http_status": e.response.status_code,
            }
        except Exception as e:
            return {"request_id": req_id, "role": role, "status": "error", "error": str(e)}

    if validated.stop_on_error:
        results = []
        successful = 0
        failed = 0
        for req_id, role in tasks:
            result = await replay_single(req_id, role)
            results.append(result)
            if result["status"] == "success":
                successful += 1
            else:
                failed += 1
                break
    else:
        results = await asyncio.gather(
            *[replay_single(req_id, role) for req_id, role in tasks]
        )
        successful = sum(1 for result in results if result["status"] == "success")
        failed = sum(1 for result in results if result["status"] == "error")

    return {
        "status": "completed",
        "source_type": source_type,
        "total_requests": len(request_ids),
        "total_roles": len(validated.target_roles),
        "total_combinations": total_combinations,
        "successful": successful,
        "failed": failed,
        "modifications_applied": validated.modifications is not None,
        "results": results,
        "message": (
            f"Replay completed: {successful}/{total_combinations} successful. "
            f"({len(request_ids)} requests x {len(validated.target_roles)} roles)"
        ),
    }


@app.tool(
    name="get_replay_scan_result",
    description="Get a replay result document directly from MongoDB by replay_id.",
)
async def get_replay_scan_result(replay_id: str) -> dict:
    validated = GetReplayResultInput(replay_id=replay_id)
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _query_replay_result_sync, validated.replay_id)
    except Exception as e:
        return {"status": "error", "message": f"Failed to execute query: {str(e)}"}


@app.tool(
    name="start_one_shot_intercept",
    description="Start a one-shot BurpBridge intercept-once task for a path.",
)
async def start_one_shot_intercept(path: str) -> dict:
    validated = StartInterceptInput(path=path)
    try:
        response, data = await _request_json(
            "POST",
            "/intercept/once/start",
            json_body={"path": validated.path},
            timeout=10.0,
        )
        response.raise_for_status()
        return {
            "status": "success",
            "enabled": data.get("enabled"),
            "task_id": data.get("task_id"),
            "path": data.get("path"),
            "created_at_ms": data.get("created_at_ms"),
            "raw_response": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Starting intercept failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during intercept start: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during intercept start: {str(e)}"}


@app.tool(
    name="stop_one_shot_intercept",
    description="Stop the current one-shot BurpBridge intercept task if one is active.",
)
async def stop_one_shot_intercept() -> dict:
    try:
        response, data = await _request_json("POST", "/intercept/once/stop", json_body={}, timeout=10.0)
        response.raise_for_status()
        return {
            "status": "success",
            "enabled": data.get("enabled"),
            "task_id": data.get("task_id"),
            "path": data.get("path"),
            "matched": data.get("matched"),
            "stop_reason": data.get("stop_reason"),
            "raw_response": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Stopping intercept failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during intercept stop: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during intercept stop: {str(e)}"}


@app.tool(
    name="get_one_shot_intercept_status",
    description="Get the current or last-known BurpBridge one-shot intercept status.",
)
async def get_one_shot_intercept_status() -> dict:
    try:
        response, data = await _request_json("GET", "/intercept/once/status", timeout=10.0)
        response.raise_for_status()
        return {
            "status": "success",
            "enabled": data.get("enabled"),
            "task_id": data.get("task_id"),
            "path": data.get("path"),
            "matched": data.get("matched"),
            "matched_history_id": data.get("matched_history_id"),
            "matched_method": data.get("matched_method"),
            "matched_path": data.get("matched_path"),
            "stop_reason": data.get("stop_reason"),
            "raw_response": data,
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = {"error_text": e.response.text}
        return {
            "status": "error",
            "message": f"Getting intercept status failed with status {e.response.status_code}",
            "details": error_detail,
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": f"Request error during intercept status: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during intercept status: {str(e)}"}


if __name__ == "__main__":
    def log(msg: str):
        print(msg, file=sys.stderr)

    log("Starting BurpBridge MCP Server (stdio mode)...")
    log(f"This server proxies requests to: {BURP_BRIDGE_URL}")
    log(
        f"MongoDB (lazy init): {MONGO_URI}, Database: {DATABASE_NAME}, "
        f"Collection: {REPLAY_COLLECTION_NAME}"
    )

    def signal_handler(sig, frame):
        _close_mongo_client()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        app.run()
    finally:
        _close_mongo_client()
