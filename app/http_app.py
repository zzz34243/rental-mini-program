from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .services import ServiceContainer


def create_server(host: str, port: int, services: ServiceContainer) -> ThreadingHTTPServer:
    handler_cls = create_handler(services)
    return ThreadingHTTPServer((host, port), handler_cls)


def create_handler(services: ServiceContainer) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._write_json(200, {"ok": True})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/health":
                self._write_json(200, services.health_payload())
                return

            if path == "/api/reviews":
                limit = self._parse_optional_int(query.get("limit", [""])[0])
                page = self._parse_positive_int(query.get("page", ["1"])[0], default=1)
                page_size = self._parse_positive_int(query.get("pageSize", ["20"])[0], default=20)
                payload = services.get_reviews(
                    house_title=query.get("houseTitle", [""])[0].strip(),
                    limit=limit,
                    page=page,
                    page_size=page_size,
                )
                self._write_json(200, payload)
                return

            if path == "/api/houses":
                page = self._parse_positive_int(query.get("page", ["1"])[0], default=1)
                page_size = self._parse_positive_int(query.get("pageSize", ["20"])[0], default=20)
                payload = services.get_houses(
                    category=query.get("category", [""])[0].strip(),
                    keyword=query.get("keyword", [""])[0].strip(),
                    city_name=query.get("cityName", [""])[0].strip(),
                    page=page,
                    page_size=page_size,
                )
                self._write_json(200, payload)
                return

            if path.startswith("/api/houses/"):
                house_id = path.removeprefix("/api/houses/").strip()
                payload = services.get_house_detail(house_id)
                if payload is None:
                    self._write_json(404, {"ok": False, "message": "房源不存在"})
                    return
                self._write_json(200, payload)
                return

            if path == "/api/ai/history":
                limit = self._parse_positive_int(query.get("limit", ["20"])[0], default=20)
                self._write_json(200, services.list_ai_history(limit=limit))
                return

            if path == "/api/favorites":
                self._write_json(200, services.list_favorites())
                return

            if path == "/api/collections":
                limit = self._parse_positive_int(query.get("limit", ["20"])[0], default=20)
                self._write_json(200, services.list_collection_runs(limit=limit))
                return

            self._write_json(404, {"ok": False, "message": "接口不存在"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            payload = self._read_json_body()
            if payload is None:
                self._write_json(400, {"ok": False, "message": "请求体不是合法 JSON"})
                return

            try:
                if parsed.path == "/api/reviews":
                    self._write_json(201, services.create_review(payload))
                    return

                if parsed.path == "/api/ai/recommend":
                    self._write_json(200, services.recommend(payload))
                    return

                if parsed.path == "/api/ai/history":
                    self._write_json(201, services.save_ai_history(payload))
                    return

                if parsed.path == "/api/search":
                    self._write_json(200, services.recommend(payload))
                    return

                if parsed.path == "/api/favorites":
                    self._write_json(201, services.add_favorite(payload))
                    return

                if parsed.path == "/api/ingest/crawl":
                    self._write_json(202, services.run_collection(payload))
                    return

                if parsed.path == "/api/ingest/embed":
                    self._write_json(200, services.rebuild_embeddings(payload))
                    return

            except ValueError as error:
                self._write_json(400, {"ok": False, "message": str(error)})
                return

            self._write_json(404, {"ok": False, "message": "接口不存在"})

        def do_DELETE(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)

            try:
                if parsed.path.startswith("/api/favorites/"):
                    house_id = parsed.path.removeprefix("/api/favorites/").strip()
                    self._write_json(200, services.remove_favorite(house_id))
                    return
            except ValueError as error:
                self._write_json(400, {"ok": False, "message": str(error)})
                return

            self._write_json(404, {"ok": False, "message": "接口不存在"})

        def log_message(self, format_string: str, *args) -> None:
            message = format_string % args
            print(f"[{self.log_date_time_string()}] {self.client_address[0]} {message}")

        def _read_json_body(self) -> dict | None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                content_length = 0

            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            try:
                parsed = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else {}

        def _write_json(self, status_code: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        @staticmethod
        def _parse_positive_int(value: str, *, default: int) -> int:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return default
            return parsed if parsed > 0 else default

        @staticmethod
        def _parse_optional_int(value: str) -> int | None:
            if not value:
                return None
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            return parsed if parsed > 0 else None

    return RequestHandler
