"""本机 Bearer 令牌。不是 OAuth。

规则：

- ``ORCA_MVC_AUTH`` 只接受 ``optional``（默认）和 ``required``。
- ``ORCA_MVC_API_TOKEN`` 未设置，且 ``optional``，且 ``ORCA_MVC_HOST`` 是回环地址：
  保持开放，启动时打警告。
- 设置了令牌：受保护接口必须带 ``Authorization: Bearer <token>``。
- ``ORCA_MVC_AUTH=required``，或绑定地址不是回环：必须校验令牌。
  没配置令牌时接口返回 401，不假装已经保护好。
- ``GET /api/v1/events`` 额外接受查询参数 ``token``，因为浏览器 EventSource
  不能设置 Authorization。其它路径不读查询参数，避免令牌进访问日志。
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class AuthPolicy:
    mode: str
    token: str | None
    required: bool
    loopback: bool

    @classmethod
    def open(cls) -> AuthPolicy:
        return cls(mode="optional", token=None, required=False, loopback=True)

    @classmethod
    def from_env(cls) -> AuthPolicy:
        raw = os.environ.get("ORCA_MVC_AUTH", "optional").strip().lower() or "optional"
        if raw not in {"optional", "required"}:
            raise ValueError(f"未知 ORCA_MVC_AUTH={raw!r}，只接受 optional 或 required")
        token = os.environ.get("ORCA_MVC_API_TOKEN", "").strip() or None
        host = os.environ.get("ORCA_MVC_HOST", "127.0.0.1").strip() or "127.0.0.1"
        loopback = host in _LOOPBACK
        if raw == "required" or not loopback:
            required = True
        else:
            required = token is not None
        return cls(mode=raw, token=token, required=required, loopback=loopback)

    def startup_warning(self) -> str | None:
        if self.required and not self.token:
            return "认证已要求但未设置 ORCA_MVC_API_TOKEN，受保护接口会返回 401"
        if not self.required:
            return "控制面未启用认证（未设置 ORCA_MVC_API_TOKEN）。只应绑定 127.0.0.1"
        return None

    def health_fields(self) -> dict[str, object]:
        return {
            "auth": "bearer" if self.required else "none",
            "auth_required": self.required,
            "auth_configured": (not self.required) or bool(self.token),
        }

    def allows(self, authorization: str | None, query_token: str | None = None) -> tuple[bool, str]:
        if not self.required:
            return True, ""
        if not self.token:
            return False, "认证已要求，但未设置 ORCA_MVC_API_TOKEN"
        presented = _presented_token(authorization, query_token)
        if presented is None:
            return False, "需要 Authorization: Bearer <ORCA_MVC_API_TOKEN>"
        if not _const_eq(presented, self.token):
            return False, "令牌不正确"
        return True, ""


def _presented_token(authorization: str | None, query_token: str | None) -> str | None:
    if authorization:
        scheme, _, rest = authorization.partition(" ")
        if scheme.lower() == "bearer" and rest.strip():
            return rest.strip()
        return None
    if query_token and query_token.strip():
        return query_token.strip()
    return None


def _const_eq(presented: str, expected: str) -> bool:
    if len(presented) != len(expected):
        return False
    return hmac.compare_digest(presented, expected)
