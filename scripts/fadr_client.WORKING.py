from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests


class FadrError(RuntimeError):
    """Raised when a Fadr API operation cannot be completed."""


def _first(obj: Any, *paths: str) -> Any:
    for path in paths:
        current = obj
        try:
            for part in path.split("."):
                current = current[int(part)] if isinstance(current, list) else current[part]
            if current not in (None, ""):
                return current
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return None


class FadrClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.base_url = os.getenv("FADR_API_BASE", "https://api.fadr.com").rstrip("/")
        self.api_key = (api_key or os.getenv("FADR_API_KEY", "")).strip()
        if not self.api_key:
            raise FadrError("FADR_API_KEY is not set")

        self.poll_seconds = float(os.getenv("FADR_POLL_SECONDS", "5"))
        self.timeout_seconds = float(os.getenv("FADR_TIMEOUT_SECONDS", "900"))
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        attempts: int = 4,
        timeout: int = 60,
        **kwargs: Any,
    ) -> requests.Response:
        method = method.upper()
        safe_to_retry = method in {"GET", "HEAD", "OPTIONS"}
        max_attempts = attempts if safe_to_retry else 1
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                response = self.session.request(
                    method,
                    self._url(path),
                    timeout=timeout,
                    **kwargs,
                )
                if (
                    safe_to_retry
                    and response.status_code in {429, 500, 502, 503, 504}
                    and attempt + 1 < max_attempts
                ):
                    time.sleep(min(2**attempt, 10))
                    continue
                if not response.ok:
                    details = response.text[:2000]
                    raise FadrError(
                        f"Fadr {method} {path} returned HTTP "
                        f"{response.status_code}: {details}"
                    )
                return response
            except FadrError:
                raise
            except requests.RequestException as error:
                last_error = error
                if attempt + 1 >= max_attempts:
                    break
                time.sleep(min(2**attempt, 10))

        raise FadrError(f"Fadr {method} {path} failed: {last_error}")

    def process(self, source: Path, out: Path) -> dict[str, Any]:
        source = source.expanduser().resolve()
        out = out.expanduser().resolve()
        if not source.is_file():
            raise FadrError(f"Source file does not exist: {source}")

        extension = source.suffix.lstrip(".").lower()
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"

        upload_info = self.request(
            "POST",
            os.getenv("FADR_UPLOAD_PATH", "/assets/upload2"),
            json={"name": source.name, "extension": extension},
        ).json()
        upload_url = _first(upload_info, "url", "data.url")
        s3_path = _first(upload_info, "s3Path", "s3path", "data.s3Path", "data.s3path")
        if not upload_url:
            raise FadrError(f"Upload response did not contain a URL: {upload_info}")
        if not s3_path:
            raise FadrError(f"Upload response did not contain s3Path: {upload_info}")

        with source.open("rb") as source_file:
            response = requests.put(
                upload_url,
                data=source_file,
                headers={"Content-Type": mime_type},
                timeout=300,
            )
            response.raise_for_status()

        asset = self.request(
            "POST",
            os.getenv("FADR_ASSET_PATH", "/assets"),
            json={"name": source.name, "extension": extension, "s3Path": s3_path},
        ).json()
        asset_id = _first(asset, "_id", "id", "asset._id", "asset.id", "data._id", "data.id")
        if not asset_id:
            raise FadrError(f"Asset response did not contain an ID: {asset}")

        task = self.request(
            "POST",
            os.getenv("FADR_STEM_TASK_PATH", "/assets/analyze/stem"),
            json={"_id": asset_id, "model": "main"},
        ).json()
        task_id = _first(task, "_id", "id", "task._id", "task.id", "data._id", "data.id")
        if not task_id:
            raise FadrError(f"Task response did not contain an ID: {task}")

        task_template = os.getenv(
            "FADR_TASK_PATH",
            "/tasks/{task_id}"
        )

        deadline = time.monotonic() + self.timeout_seconds
        final_task: dict[str, Any] | None = None

        while time.monotonic() < deadline:

            final_task = self.request(
                "GET",
                task_template.format(task_id=task_id)
            ).json()

            status_message = str(
                _first(
                    final_task,
                    "task.status.msg",
                    "status.msg",
                    "data.status.msg"
                ) or ""
            ).lower()

            progress = _first(
                final_task,
                "task.status.progress",
                "status.progress",
                "data.status.progress"
            )

            complete = bool(
                _first(
                    final_task,
                    "task.status.complete",
                    "status.complete",
                    "data.status.complete"
                )
            )

            if complete:
                break

            if status_message in {
                "failed",
                "error",
                "cancelled",
                "canceled"
            }:
                raise FadrError(
                    f"Fadr task failed: {final_task}"
                )

            time.sleep(self.poll_seconds)

        else:
            raise FadrError(
                f"Fadr task timed out after "
                f"{self.timeout_seconds:g} seconds"
            )

        if final_task is None:
            raise FadrError("Fadr task returned no status document")

        asset_data = _first(final_task, "asset", "data.asset", "task.asset")
        if not isinstance(asset_data, dict):
            asset_data = final_task

        output_assets: list[tuple[str, str, Any]] = []
        for category in ("stems", "midi"):
            for item in asset_data.get(category, []):
                file_id = item if isinstance(item, str) else item.get("_id") or item.get("id")
                if file_id:
                    output_assets.append((category, str(file_id), item))

        out.mkdir(parents=True, exist_ok=True)
        downloaded_files: list[str] = []
        download_template = os.getenv(
            "FADR_DOWNLOAD_PATH", "/assets/download/{asset_id}/{type}"
        )
        for category, file_id, item in output_assets:
            asset_type = "midi" if category == "midi" else "audio"
            download_info = self.request(
                "GET",
                download_template.format(asset_id=file_id, type=asset_type),
            ).json()
            download_url = _first(download_info, "url", "downloadUrl", "download_url", "data.url")
            if not download_url:
                continue

            item_name = item.get("name") if isinstance(item, dict) else None
            suffix = ".mid" if category == "midi" else ".wav"
            target = out / Path(item_name or f"{category}_{file_id}{suffix}").name
            with requests.get(download_url, stream=True, timeout=300) as response:
                response.raise_for_status()
                with target.open("wb") as output_file:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            output_file.write(chunk)
            downloaded_files.append(str(target))

        return {
            "task": final_task,
            "files": downloaded_files,
            "asset_id": str(asset_id),
            "task_id": str(task_id),
        }

