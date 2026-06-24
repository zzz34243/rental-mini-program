# API Reference

## Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | 服务健康检查。 |

## Houses

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/houses` | 查询房源列表。 |
| GET | `/api/houses/{id}` | 查询单套房源详情。 |

## Reviews

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/reviews` | 查询评价列表。 |
| POST | `/api/reviews` | 新增评价。 |

## Recommendation

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/search` | 自然语言房源搜索与推荐。 |
| POST | `/api/ai/recommend` | AI 推荐接口。 |
| GET | `/api/ai/history` | 查询 AI 推荐历史。 |
| POST | `/api/ai/history` | 保存 AI 推荐历史。 |

## Favorites

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/favorites` | 查询收藏列表。 |
| POST | `/api/favorites` | 新增收藏。 |
| DELETE | `/api/favorites/{houseId}` | 取消收藏。 |

## Ingestion

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ingest/crawl` | 触发房源采集。 |
| POST | `/api/ingest/embed` | 重建房源向量。 |
| GET | `/api/collections` | 查询采集运行记录。 |
