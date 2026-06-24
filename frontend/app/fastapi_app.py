from __future__ import annotations

from .services import ServiceContainer


def create_app(services: ServiceContainer):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("FastAPI dependencies are not installed") from error

    app = FastAPI(title="Anju Housing Service", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return services.health_payload()

    @app.get("/api/reviews")
    def list_reviews(
        houseTitle: str = "",
        limit: int | None = None,
        page: int = 1,
        pageSize: int = 20,
    ):
        return services.get_reviews(
            house_title=houseTitle,
            limit=limit,
            page=page,
            page_size=pageSize,
        )

    @app.post("/api/reviews", status_code=201)
    def create_review(payload: dict):
        try:
            return services.create_review(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/houses")
    def list_houses(
        category: str = "",
        keyword: str = "",
        cityName: str = "",
        page: int = 1,
        pageSize: int = 20,
    ):
        return services.get_houses(
            category=category,
            keyword=keyword,
            city_name=cityName,
            page=page,
            page_size=pageSize,
        )

    @app.get("/api/houses/{house_id}")
    def get_house(house_id: str):
        payload = services.get_house_detail(house_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="房源不存在")
        return payload

    @app.post("/api/ai/recommend")
    def recommend(payload: dict):
        try:
            return services.recommend(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/ai/history")
    def list_ai_history(limit: int = 20):
        return services.list_ai_history(limit=limit)

    @app.post("/api/ai/history", status_code=201)
    def save_ai_history(payload: dict):
        try:
            return services.save_ai_history(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/search")
    def search(payload: dict):
        try:
            return services.recommend(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/favorites")
    def list_favorites():
        return services.list_favorites()

    @app.post("/api/favorites", status_code=201)
    def add_favorite(payload: dict):
        try:
            return services.add_favorite(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.delete("/api/favorites/{house_id}")
    def remove_favorite(house_id: str):
        try:
            return services.remove_favorite(house_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/ingest/crawl", status_code=202)
    def run_collection(payload: dict):
        return services.run_collection(payload)

    @app.post("/api/ingest/embed")
    def rebuild_embeddings(payload: dict):
        try:
            return services.rebuild_embeddings(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/collections")
    def list_collection_runs(limit: int = 20):
        return services.list_collection_runs(limit=limit)

    return app
