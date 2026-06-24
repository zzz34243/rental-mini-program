from __future__ import annotations

from app.config import get_settings
from app.fastapi_app import create_app
from app.http_app import create_server
from app.services import ServiceContainer


def run_fastapi(services: ServiceContainer, *, host: str, port: int) -> None:
    import uvicorn

    app = create_app(services)
    uvicorn.run(app, host=host, port=port, log_level="info")


def run_stdlib(services: ServiceContainer, *, host: str, port: int) -> None:
    server = create_server(host, port, services)
    print(f"Anju housing service running at http://{host}:{port} (stdlib mode)")
    server.serve_forever()


def main() -> None:
    settings = get_settings()
    services = ServiceContainer(settings)

    if settings.server_mode == "stdlib":
        run_stdlib(services, host=settings.host, port=settings.port)
        return

    if settings.server_mode == "fastapi":
        run_fastapi(services, host=settings.host, port=settings.port)
        return

    try:
        run_fastapi(services, host=settings.host, port=settings.port)
    except Exception as error:  # pragma: no cover
        print(f"FastAPI mode unavailable, falling back to stdlib server: {error}")
        run_stdlib(services, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

