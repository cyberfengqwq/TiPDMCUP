# TiPDMCUP — 上市公司财报智能查询助手

## 概览
TiPDMCUP 是一个面向竞赛的上市公司财报智能查询助手。该系统能将自然语言问题转换为结构化的 SQL 查询，并通过用户专属记忆支持个性化检索，同时按公司对企业数据进行隔离。后端采用模块化架构（存储层、服务层、RAG层）构建，并使用基于 Flutter 的前端进行交互。

## 核心能力
- **Text-to-SQL 生成**：使用检索增强提示词将财务问题转换为可执行的 SQL。
- **双重检索 (RAG)**：结合历史 SQL 示例与数据库表结构字段，以实现准确的查询构建。
- **单公司数据隔离**：支持为每家公司提供专属的检索存储库。
- **用户专属的长期记忆**：从聊天记录中提取用户偏好，并存入向量记忆库中。
- **基于会话的身份验证**：提供无状态的 HTTP 接口，使用会话令牌（session tokens）及基于角色的公司成员身份管理。

## 架构
系统的设计围绕清晰的关注点分离原则展开：

- **存储层 (Stores)**：具备原子写入与索引功能的 JSON 持久化。
- **服务层 (Services)**：身份验证、用户画像摘要提取以及公司注册表。
- **RAG 层**：基于 FAISS 实现表结构和用户记忆的检索。
- **代理层 (Agent Layer)**：提示词组装及调用大语言模型（LLM）生成 SQL。
- **Web API**：用于登录、聊天、登出的 FastAPI 端点。

## 技术栈
**后端**
- Python 3.12
- FastAPI + Uvicorn
- FAISS (向量索引)
- HuggingFace Embeddings (LangChain 集成)
- Pydantic（用于请求/响应数据模式）

**前端**
- Flutter (Material UI)
- 用于 API 访问的 HTTP 客户端

## 项目结构
```
TiPDMCUP/
  core/
    agent/
      pipeline.py
    rag/
      sql_retriever.py
      memery_retrieval.py
    services/
      auth_service.py
      profile_service.py
      company_registry.py
    stores/
      base_json_store.py
      user_store.py
      company_store.py
      membership_store.py
      session_store.py
      chat_store.py
      profile_store.py
    infra/
      clock.py
      id_generator.py
  web/
    webAPI.py
  data/
    users/
    companies/
    sessions/
  frontend/
    lib/
      screens/
      services/
```

## 数据布局
- `data/users/`  
  用户记录、用户画像和记忆向量。
- `data/companies/`  
  公司元数据、成员映射关系以及公司专属资源。
- `data/sessions/`  
  用于登录令牌的会话持久化数据。

## API 概览
- `POST /login`  
  请求: `{ "user_id": "...", "password": "...", "company_id": "..." }`  
  响应: `session_id`, `roles`, `expires_at`
- `POST /chat`  
  请求头: `Authorization: Bearer <session_id>`  
  请求: `{ "prompt": "...", "chat_id": "...", "is_end": false }`  
  响应: `{ "answer": "..." }`
- `POST /logout`  
  请求头: `Authorization: Bearer <session_id>`
- `GET /me`  
  请求头: `Authorization: Bearer <session_id>`

## 运行后端
根据您的环境，使用 Conda 或 pip：

```
conda env create -f environment.yml
conda activate ticup
python -m web.webAPI
```

或者：

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m web.webAPI
```

## 运行前端
```
cd frontend
flutter pub get
flutter run
```

## 注意事项
- 向量存储库会持久化至磁盘，以便在不同会话中快速重用。
- 用户画像提取过程为异步运行，并写入用户专属记忆库中。
- 如果您使用 FRP 或反向代理，请确保前端的 `baseUrl` 与转发的端点相匹配。

## 许可证
本项目仅供竞赛和研究使用。
