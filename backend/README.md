# 后端服务

该目录包含租房小程序的后端服务代码，提供房源数据采集、标准化入库、推荐算法、评价收藏和 HTTP API。

## 模块说明

- `app/collectors.py`：数据源采集器。
- `app/normalizers.py`：房源字段标准化与向量文本构建。
- `app/repositories.py`：JSON 文件仓库。
- `app/search.py`：结构化过滤、词法匹配、语义匹配和混合排序。
- `app/embeddings.py`：Ollama / hash embedding 向量服务。
- `app/demand_parser.py`：自然语言需求解析。
- `app/answer_generator.py`：推荐说明生成。
- `app/services.py`：业务服务编排。
- `app/http_app.py`：标准库 HTTP 服务。
- `app/fastapi_app.py`：FastAPI 服务。

## 接口

- `GET /health`
- `GET /api/houses`
- `GET /api/houses/{id}`
- `GET /api/reviews`
- `POST /api/reviews`
- `POST /api/search`
- `POST /api/ai/recommend`
- `GET /api/ai/history`
- `POST /api/ai/history`
- `GET /api/favorites`
- `POST /api/favorites`
- `DELETE /api/favorites/{houseId}`
- `POST /api/ingest/crawl`
- `POST /api/ingest/embed`
- `GET /api/collections`

## 启动

```powershell
python -m pip install -r requirements.txt
python server.py
```

服务默认监听 `0.0.0.0:5000`。

## 配置

复制示例配置：

```powershell
Copy-Item local.env.example local.env
```

真实 `local.env` 不应提交到 GitHub。
