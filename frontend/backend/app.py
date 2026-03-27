from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
USER_DIR = BASE_DIR / "user"
USER_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(company: str, name: str) -> str:
    raw = f"{company.strip()}__{name.strip()}"
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in raw)
    return f"{safe}.json"


def _iter_user_files() -> list[Path]:
    return sorted(USER_DIR.glob("*.json"))


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_user(company: str, name: str) -> dict | None:
    for path in _iter_user_files():
        data = _load_json(path)
        if data.get("company") == company and data.get("name") == name:
            return data
    return None


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok"}, 200


@app.post("/register")
def register() -> tuple[dict, int]:
    payload = request.get_json(silent=True) or {}
    company = str(payload.get("company", "")).strip()
    name = str(payload.get("name", "")).strip()
    password = str(payload.get("password", ""))

    if not company or not name or not password:
        return {"message": "company/name/password 不能为空"}, 400

    if _find_user(company, name) is not None:
        return {"message": "用户已存在"}, 409

    user = {
        "id": str(uuid.uuid4()),
        "company": company,
        "name": name,
        "password_hash": generate_password_hash(password),
        "email": payload.get("xemail", ""),
        "role": payload.get("role", "user"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    user_file = USER_DIR / _safe_filename(company, name)
    with user_file.open("w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"message": "注册成功", "user": safe_user}, 201


@app.post("/login")
def login() -> tuple[dict, int]:
    payload = request.get_json(silent=True) or {}
    company = str(payload.get("company", "")).strip()
    name = str(payload.get("name", "")).strip()
    password = str(payload.get("password", ""))

    if not company or not name or not password:
        return {"message": "company/name/password 不能为空"}, 400

    user = _find_user(company, name)
    if user is None:
        return {"message": "用户不存在"}, 404

    if not check_password_hash(str(user.get("password_hash", "")), password):
        return {"message": "密码错误"}, 401

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"message": "登录成功", "user": safe_user}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1515, debug=True)
