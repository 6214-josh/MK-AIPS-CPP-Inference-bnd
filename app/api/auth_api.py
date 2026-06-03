from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import json
from app.core.database import fetch_all, fetch_one, execute, execute_returning_id
from app.core.schema_guard import ensure_extra_schema

router = APIRouter()

DEFAULT_PERMISSIONS = {
    "dashboard": True,
    "hardware": True,
    "core": True,
    "ai": True,
    "admin": False
}

ROLE_PERMISSIONS = {
    "ADMIN": {"dashboard": True, "hardware": True, "core": True, "ai": True, "admin": True},
    "PLANNER": {"dashboard": True, "hardware": True, "core": True, "ai": True, "admin": False},
    "OPERATOR": {"dashboard": True, "hardware": True, "core": False, "ai": False, "admin": False},
    "VIEWER": {"dashboard": True, "hardware": False, "core": False, "ai": False, "admin": False},
}


def _normalize_user_row(row):
    if not row:
        return row
    if isinstance(row.get("permission_json"), str):
        try:
            row["permission_json"] = json.loads(row["permission_json"])
        except Exception:
            row["permission_json"] = {}
    return row

def _normalize_user_rows(rows):
    return [_normalize_user_row(dict(r)) for r in rows]

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreateRequest(BaseModel):
    username: str
    display_name: str
    role_name: str = "VIEWER"
    password_text: str = "123456"
    enabled_flag: bool = True
    permission_json: Optional[dict[str, Any]] = None

class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    role_name: Optional[str] = None
    password_text: Optional[str] = None
    enabled_flag: Optional[bool] = None
    permission_json: Optional[dict[str, Any]] = None

def _permissions(role_name: str, custom: Optional[dict[str, Any]] = None):
    if custom is not None:
        return custom
    return ROLE_PERMISSIONS.get((role_name or "VIEWER").upper(), DEFAULT_PERMISSIONS)

def _validate_username(username: str):
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="帳號不得為空")
    if len(username.strip()) < 3:
        raise HTTPException(status_code=400, detail="帳號至少 3 個字")
    return username.strip()

def _validate_role(role_name: str):
    role = (role_name or "VIEWER").upper()
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="角色只能是 ADMIN / PLANNER / OPERATOR / VIEWER")
    return role

@router.post("/login")
def login(data: LoginRequest, request: Request):
    ensure_extra_schema()
    user = fetch_one(
        """
        SELECT user_id, username, display_name, role_name, permission_json, enabled_flag, password_text
        FROM aips_user_account
        WHERE username = %s
        """,
        (data.username,),
    )

    ok = bool(user and user["enabled_flag"] and (user.get("password_text") or "123456") == data.password)
    status = "SUCCESS" if ok else "FAIL"
    message = "登入成功" if ok else "帳號或密碼錯誤"

    execute(
        """
        INSERT INTO aips_login_log (login_time, username, login_status, client_ip, user_agent, message)
        VALUES (NOW(), %s, %s, %s, %s, %s)
        """,
        (
            data.username,
            status,
            request.client.host if request.client else "",
            request.headers.get("user-agent", ""),
            message,
        ),
    )

    if not ok:
        return {"success": False, "message": message}

    execute("UPDATE aips_user_account SET last_login_time = NOW() WHERE user_id = %s", (user["user_id"],))

    return {
        "success": True,
        "message": message,
        "token": f"demo-token-{user['username']}",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role_name": user["role_name"],
            "permission_json": user["permission_json"],
        },
    }

@router.get("/users")
def users():
    ensure_extra_schema()
    rows = fetch_all(
        """
        SELECT
            user_id,
            username,
            display_name,
            role_name,
            permission_json,
            enabled_flag,
            created_at,
            last_login_time
        FROM aips_user_account
        ORDER BY user_id DESC
        LIMIT 200
        """
    )
    return _normalize_user_rows(rows)

@router.get("/users/{user_id}")
def get_user(user_id: int):
    ensure_extra_schema()
    user = fetch_one(
        """
        SELECT user_id, username, display_name, role_name, permission_json,
               enabled_flag, created_at, last_login_time, password_text
        FROM aips_user_account
        WHERE user_id = %s
        """,
        (user_id,),
    )
    if not user:
        raise HTTPException(status_code=404, detail="查無使用者")
    return _normalize_user_row(dict(user))

@router.post("/users")
def create_user(data: UserCreateRequest):
    ensure_extra_schema()
    username = _validate_username(data.username)
    role = _validate_role(data.role_name)
    existed = fetch_one("SELECT user_id FROM aips_user_account WHERE username = %s", (username,))
    if existed:
        raise HTTPException(status_code=409, detail="帳號已存在")

    user_id = execute_returning_id(
        """
        INSERT INTO aips_user_account (
            username, display_name, role_name, permission_json, enabled_flag, password_text
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        RETURNING user_id
        """,
        (
            username,
            data.display_name.strip() if data.display_name else username,
            role,
            json.dumps(_permissions(role, data.permission_json)),
            data.enabled_flag,
            data.password_text or "123456",
        ),
        "user_id",
    )
    return {"success": True, "user_id": user_id, "message": "使用者已新增", "latest": users()}

@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdateRequest):
    ensure_extra_schema()
    user = fetch_one("SELECT * FROM aips_user_account WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="查無使用者")

    username = _validate_username(data.username) if data.username is not None else user["username"]
    role = _validate_role(data.role_name) if data.role_name is not None else user["role_name"]

    duplicated = fetch_one(
        "SELECT user_id FROM aips_user_account WHERE username = %s AND user_id <> %s",
        (username, user_id),
    )
    if duplicated:
        raise HTTPException(status_code=409, detail="帳號已被其他使用者使用")

    display_name = data.display_name if data.display_name is not None else user["display_name"]
    enabled_flag = data.enabled_flag if data.enabled_flag is not None else user["enabled_flag"]
    password_text = data.password_text if data.password_text not in (None, "") else user.get("password_text")
    permission_json = data.permission_json if data.permission_json is not None else _permissions(role)

    execute(
        """
        UPDATE aips_user_account
        SET username = %s,
            display_name = %s,
            role_name = %s,
            permission_json = %s::jsonb,
            enabled_flag = %s,
            password_text = %s,
            updated_at = NOW()
        WHERE user_id = %s
        """,
        (
            username,
            display_name,
            role,
            json.dumps(permission_json),
            enabled_flag,
            password_text,
            user_id,
        ),
    )
    return {"success": True, "user_id": user_id, "message": "使用者已更新", "latest": users()}

@router.patch("/users/{user_id}/toggle")
def toggle_user(user_id: int):
    ensure_extra_schema()
    user = fetch_one("SELECT user_id, username, enabled_flag FROM aips_user_account WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="查無使用者")
    if user["username"] == "admin" and user["enabled_flag"]:
        raise HTTPException(status_code=400, detail="admin 不可停用")
    execute("UPDATE aips_user_account SET enabled_flag = NOT enabled_flag WHERE user_id = %s", (user_id,))
    return {"success": True, "message": "啟用狀態已切換", "latest": users()}

@router.patch("/users/{user_id}/reset-password")
def reset_password(user_id: int):
    ensure_extra_schema()
    user = fetch_one("SELECT user_id FROM aips_user_account WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="查無使用者")
    execute("UPDATE aips_user_account SET password_text = '123456' WHERE user_id = %s", (user_id,))
    return {"success": True, "message": "密碼已重設為 123456", "latest": users()}

@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    ensure_extra_schema()
    user = fetch_one("SELECT user_id, username, role_name FROM aips_user_account WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="查無使用者")
    if user["username"] == "admin":
        raise HTTPException(status_code=400, detail="admin 不可刪除")

    if user["role_name"] == "ADMIN":
        admin_count = fetch_one("SELECT COUNT(*) AS cnt FROM aips_user_account WHERE role_name = 'ADMIN' AND enabled_flag = TRUE")
        if admin_count and int(admin_count["cnt"]) <= 1:
            raise HTTPException(status_code=400, detail="至少需保留一位啟用中的 ADMIN")

    execute("DELETE FROM aips_user_account WHERE user_id = %s", (user_id,))
    return {"success": True, "user_id": user_id, "message": "使用者已刪除", "latest": users()}

@router.get("/login-logs")
def login_logs():
    ensure_extra_schema()
    return fetch_all("SELECT * FROM aips_login_log ORDER BY login_id DESC LIMIT 100")

@router.post("/users/demo")
def create_user_demo():
    ensure_extra_schema()
    username = "demo_user_" + str(int(__import__("time").time()))
    user_id = execute_returning_id(
        """
        INSERT INTO aips_user_account (username, display_name, role_name, permission_json, enabled_flag, password_text)
        VALUES (
            %s,
            'Demo 使用者',
            'VIEWER',
            '{"dashboard":true}'::jsonb,
            TRUE,
            '123456'
        )
        RETURNING user_id
        """,
        (username,),
        "user_id",
    )
    return {"success": True, "user_id": user_id, "message": "Demo 使用者已新增", "latest": users()}
