# Flask 登录后端示例

该目录提供一个最小可用的 Flask API：

- `POST /register`：注册用户（JSON）
- `POST /login`：登录校验（JSON）
- `GET /health`：健康检查

用户数据文件保存在 `backend/user` 目录下，每个用户一个 JSON 文件。

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 启动服务

```bash
python app.py
```

默认监听：`0.0.0.0:1515`

## 3. 登录请求示例

```json
{
  "company": "示例公司",
  "name": "admin",
  "password": "123456"
}
```

## 4. 注册请求示例

```json
{
  "company": "示例公司",
  "name": "admin",
  "password": "123456",
  "email": "admin@example.com",
  "role": "analyst"
}
```

> 注意：用户文件中保存的是 `password_hash`，不是明文密码。
