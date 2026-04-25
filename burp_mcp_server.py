# burp_mcp_server.py
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx
import asyncio
import os
from typing import Optional

# 配置：指向你的 BurpBridge 插件
BURP_BRIDGE_URL = os.getenv("BURP_BRIDGE_URL", "http://localhost:8090")

# --- 配置 MongoDB 连接（用于直接查询重放结果）---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("MONGO_DB_NAME", "burpbridge")
REPLAY_COLLECTION_NAME = "replays"

app = FastMCP("BurpBridge-MCP")

# 延迟初始化 MongoDB 客户端（避免模块加载时就连接）
_mongo_client = None
_replay_collection = None


def _get_replay_collection():
    """延迟获取 MongoDB collection，避免在模块加载时连接。"""
    global _mongo_client, _replay_collection
    if _replay_collection is None:
        from pymongo import MongoClient
        _mongo_client = MongoClient(MONGO_URI)
        db = _mongo_client[DATABASE_NAME]
        _replay_collection = db[REPLAY_COLLECTION_NAME]
    return _replay_collection


def _close_mongo_client():
    """关闭 MongoDB 连接。"""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


def _safe_get_field(data: dict, *field_names: str, default=None):
    """
    Safely get a field from a dict, trying multiple field name variations.
    Useful for handling potential camelCase/snake_case mismatches.

    Args:
        data: The dictionary to read from
        *field_names: Field names to try (in order of preference)
        default: Default value if no field is found

    Returns:
        The first non-None value found, or default
    """
    if data is None:
        return default

    for name in field_names:
        value = data.get(name)
        if value is not None:
            return value

    return default


def _extract_history_fields(data: dict) -> dict:
    """
    Extract fields from history API response with robust name mapping.
    Handles both camelCase (current Java) and snake_case (potential legacy) field names.

    Returns a dict with normalized field names (snake_case for Python output).
    """
    if data is None:
        return {}

    return {
        # ID - MongoDB _id or id field
        'id': _safe_get_field(data, 'id', '_id'),

        # URL - try camelCase first
        'url': _safe_get_field(data, 'url', 'URL'),

        # Method
        'method': _safe_get_field(data, 'method'),

        # Response status code - try multiple variations
        'response_status_code': _safe_get_field(data, 'responseStatusCode', 'response_status_code', 'statusCode', 'status_code'),

        # Timestamp
        'timestamp_ms': _safe_get_field(data, 'timestampMs', 'timestamp_ms'),
        'timestamp': _safe_get_field(data, 'timestamp'),

        # Request raw
        'request_raw': _safe_get_field(data, 'requestRaw', 'request_raw'),

        # Response summary
        'response_summary': _safe_get_field(data, 'responseSummary', 'response_summary'),

        # Response body info
        'has_large_response_body': _safe_get_field(data, 'hasLargeResponseBody', 'has_large_response_body'),
        'response_body_length': _safe_get_field(data, 'responseBodyLength', 'response_body_length'),
    }


class HealthCheckInput(BaseModel):
    """健康检查,输入参数:"""
    pass


@app.tool(
    name="check_burp_health",
    description="检查 BurpBridge 服务的健康状况和版本信息。无需参数。"
)
async def check_burp_health(input: HealthCheckInput) -> dict:
    """
    Checks the health status of the BurpBridge service.
    """
    # 使用 httpx 异步客户端向 BurpBridge 发送 GET 请求
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BURP_BRIDGE_URL}/health")
            resp.raise_for_status()         # 如果响应状态码不是 2xx，则抛出异常
            data = resp.json()
            return {
                "status": "success",
                "service": data.get("plugin"),
                "burp_version": data.get("burpVersion"),
                "raw_response": data
            }
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"Health check failed with status {e.response.status_code}",
                    "details": e.response.text}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during health check: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during health check: {str(e)}"}


class SyncHistoryInput(BaseModel):
    """
    同步历史记录,输入参数:
    - host (str): 目标主机名 (必需)
    - methods (str, optional): 逗号分隔的 HTTP 方法 (e.g., "GET,POST")
    - path (str, optional): URL 路径前缀或通配符 (e.g., "/api/v1/*")
    - status (int, optional): 响应状态码 (e.g., 200)
    - require_response (bool, optional): 是否要求必须有响应 (默认 true)
    - exclude_mime (str, optional): 额外排除的 MIME 类型,逗号分隔 (e.g., "image/*,font/*")
    - include_html (bool, optional): 是否保留 HTML 响应 (默认排除)
    - no_default_mime (bool, optional): 是否禁用默认 MIME 排除列表 (默认 false)
    """
    host: str           #必填项
    methods: str | None = None
    path: str | None = None
    status: int | None = None
    require_response: bool | None = None
    exclude_mime: str | None = None
    include_html: bool | None = None
    no_default_mime: bool | None = None


@app.tool(
    name="sync_proxy_history_with_filters",
    description="从 Burp Proxy 手动同步匹配特定条件的历史请求到数据库。host 参数是必需的。"
)
async def sync_proxy_history_with_filters(input: SyncHistoryInput) -> dict:
    """
    根据过滤条件，从 Burp Suite 同步代理历史记录到数据库。
    """
    # 构建查询参数，只有当输入值不为 None 时才添加到参数中
    params = {"host": input.host}
    if input.methods is not None:
        params["methods"] = input.methods
    if input.path is not None:
        params["path"] = input.path
    if input.status is not None:
        params["status"] = str(input.status)    # 状态码需要转为字符串
    if input.require_response is not None:
        params["requireResponse"] = str(input.require_response).lower()
    # MIME 过滤参数
    if input.exclude_mime is not None:
        params["exclude_mime"] = input.exclude_mime
    if input.include_html is not None:
        params["include_html"] = str(input.include_html).lower()
    if input.no_default_mime is not None:
        params["no_default_mime"] = str(input.no_default_mime).lower()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 向 BurpBridge 的 /sync 端点发送 POST 请求，携带过滤参数
            resp = await client.post(f"{BURP_BRIDGE_URL}/sync", params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "ok":
                return {
                    "status": "success",
                    "synced_count": data.get("synced_count", 0),    # 同步的请求数量
                    "applied_filters": data.get("filters", {}),     # 实际应用的过滤器
                    "sync_timestamp": data.get("SyncTimestamp"),
                    "message": f"Successfully synced {data['synced_count']} requests."
                }
            else:
                return {"status": "warning", "message": "Request succeeded but returned an unexpected format.",
                        "raw_data": data}

        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Sync failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during sync: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during sync: {str(e)}"}


class ConfigureAutoSyncInput(BaseModel):
    """
    配置自动同步,输入参数:
    - enabled (bool): 是否启用自动同步
    - host (str, optional): 目标主机名过滤
    - methods (list[str], optional): HTTP 方法列表 (e.g., ["GET", "POST"])
    - path_pattern (str, optional): URL 路径通配符 (e.g., "/api/*")
    - status_code (int, optional): 响应状态码过滤
    - require_response (bool, optional): 是否要求必须有响应
    """
    enabled: bool
    host: str | None = None
    methods: list[str] | None = None
    path_pattern: str | None = None
    status_code: int | None = None
    require_response: bool | None = None


@app.tool(
    name="configure_auto_sync",
    description="配置自动同步功能。启用后，符合条件的代理请求会自动同步到数据库，无需手动调用 sync。"
)
async def configure_auto_sync(input: ConfigureAutoSyncInput) -> dict:
    """
    配置自动同步功能，启用/禁用自动将代理请求同步到数据库。
    """
    payload = {
        "enabled": input.enabled,
        "host": input.host or "",
        "methods": input.methods or [],
        "path_pattern": input.path_pattern or "",
        "status_code": input.status_code or 0,
        "require_response": input.require_response if input.require_response is not None else True
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{BURP_BRIDGE_URL}/sync/auto",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "ok":
                return {
                    "status": "success",
                    "auto_sync_enabled": data.get("auto_sync_enabled"),
                    "config": data.get("config"),
                    "message": f"Auto-sync {'enabled' if input.enabled else 'disabled'} successfully."
                }
            else:
                return {"status": "warning", "message": "Request succeeded but returned an unexpected format.",
                        "raw_data": data}

        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Auto-sync config failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}


class AutoSyncStatusInput(BaseModel):
    """获取自动同步状态,输入参数: 无"""
    pass


@app.tool(
    name="get_auto_sync_status",
    description="获取自动同步功能的当前状态、配置和统计信息。无需参数。"
)
async def get_auto_sync_status(input: AutoSyncStatusInput) -> dict:
    """
    获取自动同步的当前配置和统计信息。
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BURP_BRIDGE_URL}/sync/auto/status")
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "ok":
                return {
                    "status": "success",
                    "auto_sync_enabled": data.get("auto_sync_enabled"),
                    "synced_count": data.get("synced_count", 0),
                    "config": data.get("config"),
                    "message": f"Auto-sync is {'enabled' if data.get('auto_sync_enabled') else 'disabled'}. "
                               f"Total synced: {data.get('synced_count', 0)} requests."
                }
            else:
                return {"status": "warning", "message": "Request succeeded but returned an unexpected format.",
                        "raw_data": data}

        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Getting auto-sync status failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}


class ListHistoryInput(BaseModel):
    """
    列出历史记录,输入参数:
    - host (str, optional): 主机名
    - path (str, optional): 路径模式（支持 * 通配符）
    - method (str, optional): HTTP 方法
    - page (int, optional): 页码 (默认 1)
    - page_size (int, optional): 每页数量 (默认 20, 最大 100)
    """
    host: str | None = None
    path: str | None = None
    method: str | None = None
    page: int = 1
    page_size: int = 20


@app.tool(
    name="list_paginated_http_history",
    description="分页查询 Burp Proxy 历史记录。可按 host, path, method 过滤。"
)
async def list_paginated_http_history(input: ListHistoryInput) -> dict:
    """
    分页列出 Burp Proxy 的 HTTP 历史记录。
    """
    params = {}
    if input.host:
        params["host"] = input.host
    if input.path:
        params["path"] = input.path
    if input.method:
        params["method"] = input.method
    # 对页码和页面大小进行基本校验和限制
    params["page"] = max(1, input.page)
    params["page_size"] = min(max(1, input.page_size), 100)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 向 BurpBridge 的 /history 端点发送 GET 请求，获取分页数据
            resp = await client.get(f"{BURP_BRIDGE_URL}/history", params=params)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])

            # 使用健壮的字段提取
            processed_items = []
            for item in items:
                extracted = _extract_history_fields(item)
                processed_items.append({
                    'id': extracted['id'],
                    'url': extracted['url'],
                    'method': extracted['method'],
                    'response_status_code': extracted['response_status_code'],
                    'timestamp_ms': extracted['timestamp_ms'],
                })

            # 检测潜在的数据问题
            warnings = []
            if items:
                sample = items[0]
                available_fields = list(sample.keys())
                expected_fields = ['id', 'url', 'method', 'responseStatusCode', 'timestampMs']
                missing = [f for f in expected_fields if f not in available_fields]
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
                "full_items_raw": items,  # 保留原始数据用于调试
                "debug_warnings": warnings if warnings else None,
            }
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Listing history failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during listing: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during listing: {str(e)}"}


class GetHistoryDetailInput(BaseModel):
    """
    获取历史记录详情,输入参数:
    - history_id (str): MongoDB ObjectId 字符串 (e.g., "65f1a2b3c4d5e6f7a8b9c0d1")
    """
    history_id: str


@app.tool(
    name="get_http_request_detail",
    description="通过 ID 获取单条 HTTP 请求的完整详细信息，包括完整的原始请求报文。"
)
async def get_http_request_detail(input: GetHistoryDetailInput) -> dict:
    """
    Gets the full details of a single HTTP request by its ID.
    """
    history_id = input.history_id.strip()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 向 BurpBridge 的 /history/{id} 端点发送 GET 请求，获取具体请求详情
            resp = await client.get(f"{BURP_BRIDGE_URL}/history/{history_id}")
            if resp.status_code == 404:
                return {"status": "error", "message": f"History entry with ID '{history_id}' not found."}

            resp.raise_for_status()
            data = resp.json()

            # 使用健壮的字段提取
            extracted = _extract_history_fields(data)

            # 安全处理可能为 None 的字段
            request_raw = extracted.get('request_raw') or ""
            preview = request_raw[:200]
            if len(request_raw) > 200:
                preview += "..."

            # 检测潜在的数据问题
            warnings = []
            available_fields = list(data.keys())
            expected_fields = ['id', 'url', 'method', 'responseStatusCode', 'timestampMs', 'requestRaw']
            missing = [f for f in expected_fields if f not in available_fields]
            if missing:
                warnings.append(f"Expected fields not found: {missing}")
                warnings.append(f"Available fields: {available_fields}")

            # 检测默认值问题
            if extracted.get('response_status_code') in (0, None, -1):
                warnings.append(f"response_status_code appears to be default/missing: {extracted.get('response_status_code')}")
            if not extracted.get('url'):
                warnings.append("url field is empty")
            if not extracted.get('method'):
                warnings.append("method field is empty")
            if not extracted.get('request_raw'):
                warnings.append("request_raw field is empty")

            return {
                "status": "success",
                "id": extracted.get('id'),
                "url": extracted.get('url'),
                "method": extracted.get('method'),
                "response_status_code": extracted.get('response_status_code'),
                "response_status": extracted.get('response_status_code'),  # 别名，便于理解
                "timestamp_ms": extracted.get('timestamp_ms'),
                "timestamp": extracted.get('timestamp'),
                "request_raw_preview": preview,
                "request_raw": request_raw,  # 完整的原始请求报文
                "response_summary": extracted.get('response_summary'),
                "has_large_response_body": extracted.get('has_large_response_body'),
                "response_body_length": extracted.get('response_body_length'),
                # Debug information
                "debug_warnings": warnings if warnings else None,
                "debug_available_fields": available_fields,
            }
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Fetching detail failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during fetch: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during fetch: {str(e)}"}


class DebugRawHistoryInput(BaseModel):
    """
    调试：获取原始历史记录,输入参数:
    - history_id (str): MongoDB ObjectId 字符串
    """
    history_id: str


@app.tool(
    name="debug_raw_history_entry",
    description="调试工具：获取历史记录的原始 API 响应，不做任何字段转换。用于排查字段名不匹配问题。"
)
async def debug_raw_history_entry(input: DebugRawHistoryInput) -> dict:
    """
    Debug tool: Returns the raw API response for a history entry.
    No field mapping, no processing - just the raw data.
    """
    history_id = input.history_id.strip()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BURP_BRIDGE_URL}/history/{history_id}")
            if resp.status_code == 404:
                return {"status": "error", "message": f"History entry with ID '{history_id}' not found."}

            resp.raise_for_status()
            data = resp.json()

            return {
                "status": "success",
                "raw_response": data,
                "field_names": list(data.keys()) if isinstance(data, dict) else "Not a dict",
                "field_types": {k: type(v).__name__ for k, v in data.items()} if isinstance(data, dict) else "N/A",
            }
        except Exception as e:
            return {"status": "error", "message": f"Debug fetch failed: {str(e)}"}


class ConfigureAuthInput(BaseModel):
    """
    配置认证上下文,输入参数:
    - role (str): 用户角色 (e.g., "admin", "user")
    - headers (dict, optional): 要注入的 HTTP 头部 (e.g., {"Authorization": "Bearer token"})
    - cookies (dict, optional): 要注入的 Cookie (e.g., {"sessionid": "abc123"})
    """
    role: str
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None


@app.tool(
    name="configure_authentication_context",
    description="为特定角色配置认证上下文（如 Headers, Cookies）。"
)
async def configure_authentication_context(input: ConfigureAuthInput) -> dict:
    """
    为特定角色配置认证上下文（Headers, Cookies）
    """
    # 构建要发送给 BurpBridge 的 JSON 载荷
    payload = {
        "role": input.role,
        "headers": input.headers or {},
        "cookies": input.cookies or {}
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 向 BurpBridge 的 /auth/config 端点发送 POST 请求
            resp = await client.post(
                f"{BURP_BRIDGE_URL}/auth/config",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "ok":
                return {
                    "status": "success",
                    "configured_role": data.get("role"),
                    "message": f"Authentication context configured for role '{input.role}'."
                }
            else:
                return {"status": "warning", "message": "Request succeeded but returned an unexpected format.",
                        "raw_data": data}

        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Configuring auth failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during config: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during config: {str(e)}"}


class ListRolesInput(BaseModel):
    """列出已配置角色,输入参数: 无"""
    pass


@app.tool(
    name="list_configured_roles",
    description="列出所有已配置认证上下文的用户角色。无需参数。"
)
async def list_configured_roles(input: ListRolesInput) -> dict:
    """
    列出当前系统中已配置认证上下文的所有角色名称。
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BURP_BRIDGE_URL}/auth/roles")
            resp.raise_for_status()
            data = resp.json()

            roles = data.get("roles", [])
            return {
                "status": "success",
                "roles": roles,
                "count": len(roles),
                "message": f"Found {len(roles)} configured role(s)." if roles else "No roles configured yet."
            }
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Listing roles failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}


class DeleteRoleInput(BaseModel):
    """
    删除角色认证上下文,输入参数:
    - role (str): 要删除的角色名称
    """
    role: str


class ImportPlaywrightCookiesInput(BaseModel):
    """
    从 Playwright 导入 cookies,输入参数:
    - role (str): 要配置的角色名称
    - cookies (list[dict]): Playwright 格式的 cookies 列表
      格式示例: [{"name": "session", "value": "abc123", "domain": ".example.com", ...}]
    - merge_with_existing (bool, optional): 是否与现有 cookies 合并 (默认 True)
    """
    role: str
    cookies: list[dict]
    merge_with_existing: bool = True


@app.tool(
    name="import_playwright_cookies",
    description="从 Playwright 浏览器会话导入 cookies 到 BurpBridge 认证上下文。"
                "Playwright cookies 格式: [{\"name\": \"session\", \"value\": \"abc\", \"domain\": \".example.com\", ...}]"
)
async def import_playwright_cookies(input: ImportPlaywrightCookiesInput) -> dict:
    """
    将 Playwright 格式的 cookies 导入到 BurpBridge 认证上下文。
    """
    # 将 Playwright 格式转换为 BurpBridge 格式
    # Playwright: [{"name": "session", "value": "abc", "domain": ".example.com", ...}]
    # BurpBridge: {"session": "abc", ...}
    burpbridge_cookies = {}
    for cookie in input.cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value:
            burpbridge_cookies[name] = value

    if not burpbridge_cookies:
        return {
            "status": "warning",
            "message": "No valid cookies found in Playwright format.",
            "imported_count": 0
        }

    # 构建请求载荷
    payload = {
        "role": input.role,
        "headers": {},
        "cookies": burpbridge_cookies
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 先获取现有配置（如果需要合并）
            if input.merge_with_existing:
                existing_resp = await client.get(f"{BURP_BRIDGE_URL}/auth/roles")
                # 注：当前 API 不支持获取单个角色的详细信息，这里简化处理

            # 向 BurpBridge 的 /auth/config 端点发送 POST 请求
            resp = await client.post(
                f"{BURP_BRIDGE_URL}/auth/config",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "ok":
                return {
                    "status": "success",
                    "configured_role": input.role,
                    "imported_cookies_count": len(burpbridge_cookies),
                    "imported_cookies": list(burpbridge_cookies.keys()),
                    "message": f"Successfully imported {len(burpbridge_cookies)} cookies for role '{input.role}'."
                }
            else:
                return {"status": "warning", "message": "Request succeeded but returned an unexpected format.",
                        "raw_data": data}

        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Import failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during import: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during import: {str(e)}"}


@app.tool(
    name="delete_authentication_context",
    description="删除指定角色的认证上下文配置。"
)
async def delete_authentication_context(input: DeleteRoleInput) -> dict:
    """
    删除某个角色的认证凭据配置。
    """
    role = input.role.strip()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.delete(f"{BURP_BRIDGE_URL}/auth/roles/{role}")
            if resp.status_code == 404:
                return {"status": "not_found", "message": f"Role '{role}' not found."}

            resp.raise_for_status()
            data = resp.json()

            return {
                "status": "success",
                "deleted_role": data.get("deleted_role"),
                "message": f"Authentication context for role '{role}' has been deleted."
            }
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Deleting role failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}


class ReplayRequestInput(BaseModel):
    """
    重放请求,输入参数:
    - history_entry_id (str, optional): 历史记录的 MongoDB ObjectId（从历史记录重放）
    - replay_id (str, optional): 已重放记录的 ID（从重放记录再次重放）
    - target_role (str): 用于重放的角色
    - modifications (dict, optional): 请求修改配置
    
    注意: history_entry_id 和 replay_id 二选一，不能同时使用。
    """
    history_entry_id: str | None = None
    replay_id: str | None = None
    target_role: str
    modifications: dict | None = None


@app.tool(
    name="replay_http_request_as_role",
    description="使用指定角色凭据重放请求。支持两种模式：(1) 从历史记录重放（传入 history_entry_id）；(2) 从重放记录再次重放（传入 replay_id）。可选传入 modifications 进行请求修改。返回 replay_id 用于查询结果。"
)
async def replay_http_request_as_role(input: ReplayRequestInput) -> dict:
    """
    Replays a captured HTTP request using credentials for a specific role.
    Supports two modes: from history entry or from previous replay record.
    Returns a replay_id which can be used to get the result later.
    """
    has_history_id = input.history_entry_id is not None and input.history_entry_id.strip() != ""
    has_replay_id = input.replay_id is not None and input.replay_id.strip() != ""
    
    if not has_history_id and not has_replay_id:
        return {"status": "error", "message": "Missing required field: history_entry_id or replay_id"}
    if has_history_id and has_replay_id:
        return {"status": "error", "message": "Only one of history_entry_id or replay_id is allowed"}
    
    payload = {"target_role": input.target_role}
    if has_history_id:
        payload["history_entry_id"] = input.history_entry_id.strip()
    else:
        payload["replay_id"] = input.replay_id.strip()
    
    if input.modifications is not None:
        payload["modifications"] = input.modifications

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{BURP_BRIDGE_URL}/scan/single",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            mode_desc = "history entry" if has_history_id else "replay record"
            source_id = input.history_entry_id if has_history_id else input.replay_id

            return {
                "status": "success",
                "replay_id": data.get("replay_id"),
                "queue_status": data.get("status"),
                "source_mode": mode_desc,
                "message": f"Replay initiated with ID '{data.get('replay_id')}' from {mode_desc} '{source_id}' as role '{input.target_role}'. Use the replay_id to check results."
            }

        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"error_text": e.response.text}
            return {"status": "error", "message": f"Replay request failed with status {e.response.status_code}",
                    "details": error_detail}
        except httpx.RequestError as e:
            return {"status": "error", "message": f"Request error during replay: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error during replay: {str(e)}"}


class ReplayRequestsInput(BaseModel):
    """
    统一重放请求工具,输入参数:
    - history_entry_ids (list[str], optional): 历史记录 ID 列表（从历史记录重放）
    - replay_ids (list[str], optional): 重放记录 ID 列表（从重放记录再次重放）
    - target_roles (list[str]): 目标角色列表
    - modifications (dict, optional): 请求修改配置（对所有请求生效）
    - stop_on_error (bool, optional): 遇到错误是否停止 (默认 False)
    
    注意: history_entry_ids 和 replay_ids 二选一，不能同时使用。
    """
    history_entry_ids: list[str] | None = None
    replay_ids: list[str] | None = None
    target_roles: list[str]
    modifications: dict | None = None
    stop_on_error: bool = False


@app.tool(
    name="replay_requests",
    description="统一重放请求工具。支持多请求 × 多角色笛卡尔积重放。"
                "输入 history_entry_ids 或 replay_ids（二选一），以及 target_roles 列表。"
                "可选 modifications 对所有请求生效。返回每个组合的重放结果。"
)
async def replay_requests(input: ReplayRequestsInput) -> dict:
    """
    统一重放请求工具，支持笛卡尔积重放。
    通过并发调用 /scan/single 实现多请求 × 多角色重放。
    """
    has_history_ids = input.history_entry_ids is not None and len(input.history_entry_ids) > 0
    has_replay_ids = input.replay_ids is not None and len(input.replay_ids) > 0
    
    if not has_history_ids and not has_replay_ids:
        return {"status": "error", "message": "Missing required field: history_entry_ids or replay_ids"}
    if has_history_ids and has_replay_ids:
        return {"status": "error", "message": "Only one of history_entry_ids or replay_ids is allowed"}
    
    if not input.target_roles or len(input.target_roles) == 0:
        return {"status": "error", "message": "target_roles must be a non-empty list"}
    
    request_ids = input.history_entry_ids if has_history_ids else input.replay_ids
    id_type = "history_entry_id" if has_history_ids else "replay_id"
    source_type = "history" if has_history_ids else "replay"
    
    # 计算笛卡尔积：requests × roles
    tasks = []
    for req_id in request_ids:
        for role in input.target_roles:
            tasks.append((req_id, role))
    
    total_combinations = len(tasks)
    
    async def replay_single(req_id: str, role: str) -> dict:
        payload = {
            id_type: req_id,
            "target_role": role
        }
        if input.modifications is not None:
            payload["modifications"] = input.modifications
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    f"{BURP_BRIDGE_URL}/scan/single",
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "request_id": req_id,
                    "role": role,
                    "replay_id": data.get("replay_id"),
                    "status": "success"
                }
            except httpx.HTTPStatusError as e:
                error_msg = ""
                try:
                    error_msg = e.response.json().get("error", e.response.text)
                except:
                    error_msg = e.response.text
                return {
                    "request_id": req_id,
                    "role": role,
                    "status": "error",
                    "error": error_msg,
                    "http_status": e.response.status_code
                }
            except Exception as e:
                return {
                    "request_id": req_id,
                    "role": role,
                    "status": "error",
                    "error": str(e)
                }
    
    # 并发执行所有重放任务
    if input.stop_on_error:
        # 串行执行，遇到错误停止
        results = []
        successful = 0
        failed = 0
        stopped_early = False
        
        for req_id, role in tasks:
            result = await replay_single(req_id, role)
            results.append(result)
            if result["status"] == "success":
                successful += 1
            else:
                failed += 1
                stopped_early = True
                break
    else:
        # 并发执行所有任务
        results = await asyncio.gather(*[replay_single(req_id, role) for req_id, role in tasks])
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "error")
    
    return {
        "status": "completed",
        "source_type": source_type,
        "total_requests": len(request_ids),
        "total_roles": len(input.target_roles),
        "total_combinations": total_combinations,
        "successful": successful,
        "failed": failed,
        "modifications_applied": input.modifications is not None,
        "results": results,
        "message": f"Replay completed: {successful}/{total_combinations} successful. "
                   f"({len(request_ids)} requests × {len(input.target_roles)} roles)"
    }





class GetReplayResultInput(BaseModel):
    """
    获取重放结果,输入参数:
    - replay_id (str): 由 replay_http_request_as_role 调用返回的 replay_id
    """
    replay_id: str


def _query_replay_result_sync(replay_id_str: str) -> dict:
    """同步查询 MongoDB（在线程池中运行）。"""
    from bson import ObjectId

    collection = _get_replay_collection()
    query_filter = {}

    # 尝试将 replay_id 转换为 ObjectId 进行精确查询
    try:
        query_filter = {"_id": ObjectId(replay_id_str)}
    except Exception:
        # 如果转换失败，则按普通字符串字段 "replay_id" 查询
        query_filter = {"replayId": replay_id_str}

    document = collection.find_one(query_filter)

    if document:
        doc_id = str(document.get('_id'))
        document.pop('_id', None)
        document['id'] = doc_id
        return {
            "status": "success",
            "found_document_id": doc_id,
            "replay_data": document,
            "message": f"Found replay result for ID '{replay_id_str}'."
        }
    else:
        return {
            "status": "not_found",
            "message": f"No replay result found for ID '{replay_id_str}' in the '{DATABASE_NAME}.{REPLAY_COLLECTION_NAME}' collection."
        }


@app.tool(
    name="get_replay_scan_result",
    description="通过 replay_id 直接从 MongoDB 数据库获取单次重放扫描的详细结果。"
)
async def get_replay_scan_result(input: GetReplayResultInput) -> dict:
    """
    通过其 ID 直接从 MongoDB 数据库获取重放扫描的详细结果。
    此函数在线程池中执行同步 MongoDB 查询，避免阻塞事件循环。
    """
    try:
        # 在线程池中运行同步 MongoDB 查询
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _query_replay_result_sync, input.replay_id)
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to execute query: {str(e)}"
        }


if __name__ == "__main__":
    import signal
    import sys
    import platform

    # stdio 模式下不能打印到 stdout，否则会破坏 MCP 协议
    # 所有日志输出到 stderr
    def log(msg: str):
        import sys
        print(msg, file=sys.stderr)

    log("Starting BurpBridge MCP Server (stdio mode)...")
    log(f"This server proxies requests to: {BURP_BRIDGE_URL}")
    log(f"MongoDB (lazy init): {MONGO_URI}, Database: {DATABASE_NAME}, Collection: {REPLAY_COLLECTION_NAME}")

    def signal_handler(sig, frame):
        _close_mongo_client()
        sys.exit(0)

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        app.run()
    finally:
        _close_mongo_client()