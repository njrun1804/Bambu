"""Meshy Pro API client for hybrid-lane head meshes and concept sheets."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from bambu.mesh_lane import mesh_intake, write_mesh_provenance


MESHY_BASE_URL = "https://api.meshy.ai/openapi"
TEST_MODE_API_KEY = "msy_dummy_api_key_for_test_mode_12345678"
DEFAULT_POLL_INTERVAL_S = 3.0
DEFAULT_POLL_TIMEOUT_S = 600.0

FDM_HEAD_PAYLOAD_BASE = {
    "ai_model": "meshy-6",
    "should_texture": False,
    "should_remesh": True,
    "target_polycount": 50000,
    "decimation_mode": 3,
    "target_formats": ["stl", "glb"],
    "image_enhancement": False,
    "model_type": "standard",
}

DIORAMA_CONCEPT_PROMPT = (
    "Chibi collectible figurine diorama concept sheet, seated scene, "
    "toy caricature proportions, single-color PLA figurine, clean silhouette, "
    "front three-quarter view on white background"
)


class MeshyError(Exception):
    """Meshy API or configuration error."""


@dataclass(frozen=True)
class MeshyClient:
    """Async-task Meshy client with polling and test-mode support."""

    api_key: str
    base_url: str = MESHY_BASE_URL
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S
    poll_timeout_s: float = DEFAULT_POLL_TIMEOUT_S

    @property
    def test_mode(self) -> bool:
        return self.api_key == TEST_MODE_API_KEY

    @classmethod
    def from_env(cls) -> MeshyClient:
        key = os.environ.get("MESHY_API_KEY", "").strip()
        if not key:
            raise MeshyError(
                "MESHY_API_KEY is not set. Export it in your shell; never commit API keys. "
                f"Test mode: export MESHY_API_KEY={TEST_MODE_API_KEY}"
            )
        return cls(api_key=key)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:
            raise MeshyError(
                "httpx is required for Meshy API calls. Install with: uv sync --extra meshy"
            ) from exc

        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=120.0) as client:
            response = client.request(method, url, headers=headers, json=json_body, params=params)
        if response.status_code == 402:
            raise MeshyError("Meshy credits exhausted (402). Check balance with: bambu meshy balance")
        if response.status_code == 429:
            raise MeshyError("Meshy rate limit (429). Pro tier: 20 req/min, 10 concurrent tasks.")
        if response.status_code >= 400:
            raise MeshyError(f"Meshy API error {response.status_code}: {response.text[:500]}")
        if not response.content:
            return {}
        return response.json()

    def create_task(self, path: str, payload: dict[str, Any]) -> str:
        """POST a task and return task id."""

        data = self._request("POST", path, json_body=payload)
        task_id = data.get("result") or data.get("id") or data.get("task_id")
        if not task_id:
            raise MeshyError(f"Meshy task id missing in response: {data}")
        return str(task_id)

    def get_task(self, path: str, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"{path}/{task_id}")

    def poll_task(
        self,
        path: str,
        task_id: str,
        *,
        success_status: str = "SUCCEEDED",
    ) -> dict[str, Any]:
        """Poll until task succeeds or fails."""

        deadline = time.monotonic() + self.poll_timeout_s
        while time.monotonic() < deadline:
            task = self.get_task(path, task_id)
            status = str(task.get("status", "")).upper()
            if status == success_status:
                return task
            if status in {"FAILED", "CANCELED", "CANCELLED"}:
                raise MeshyError(f"Meshy task {task_id} {status}: {task.get('task_error', task)}")
            time.sleep(self.poll_interval_s)
        raise MeshyError(f"Meshy task {task_id} timed out after {self.poll_timeout_s}s")

    def balance(self) -> dict[str, Any]:
        return self._request("GET", "v1/balance")

    def image_data_uri(self, image_path: Path | str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(path)
        suffix = path.suffix.lower().lstrip(".")
        mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix or 'png'}"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def run_figure_prototype(self, image_path: Path | str) -> dict[str, Any]:
        task_id = self.create_task(
            "creative-lab/figure/v1/prototype",
            {"image_url": self.image_data_uri(image_path)},
        )
        return self.poll_task("creative-lab/figure/v1/prototype", task_id)

    def run_image_to_3d(self, image_path: Path | str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {**FDM_HEAD_PAYLOAD_BASE, "image_url": self.image_data_uri(image_path), **(extra or {})}
        task_id = self.create_task("v1/image-to-3d", payload)
        return self.poll_task("v1/image-to-3d", task_id)

    def run_text_to_image(self, prompt: str) -> dict[str, Any]:
        task_id = self.create_task("v1/text-to-image", {"prompt": prompt, "ai_model": "meshy-5"})
        return self.poll_task("v1/text-to-image", task_id)

    def analyze_printability(self, *, input_task_id: str | None = None, model_url: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if input_task_id:
            body["input_task_id"] = input_task_id
        if model_url:
            body["model_url"] = model_url
        task_id = self.create_task("v1/print/analyze", body)
        return self.poll_task("v1/print/analyze", task_id)

    def repair_printability(self, *, input_task_id: str) -> dict[str, Any]:
        task_id = self.create_task("v1/print/repair", {"input_task_id": input_task_id})
        return self.poll_task("v1/print/repair", task_id)

    def remesh(self, *, input_task_id: str, target_polycount: int = 30000) -> dict[str, Any]:
        task_id = self.create_task(
            "v1/remesh",
            {"input_task_id": input_task_id, "target_polycount": target_polycount},
        )
        return self.poll_task("v1/remesh", task_id)

    def download_url(self, url: str, dest: Path) -> Path:
        try:
            import httpx
        except ImportError as exc:
            raise MeshyError("httpx is required to download Meshy artifacts") from exc

        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            dest.write_bytes(response.content)
        return dest

    def extract_model_urls(self, task: dict[str, Any]) -> dict[str, str]:
        urls: dict[str, str] = {}
        model_urls = task.get("model_urls") or {}
        if isinstance(model_urls, dict):
            for fmt, url in model_urls.items():
                if url:
                    urls[str(fmt)] = str(url)
        image_urls = task.get("image_urls")
        if isinstance(image_urls, list) and image_urls:
            urls["image_url"] = str(image_urls[0])
        for key in ("model_url", "result_url", "image_url", "thumbnail_url"):
            if task.get(key):
                urls[key] = str(task[key])
        return urls


def resolve_reference_photo(project_dir: Path | str) -> Path | None:
    """Find the primary reference photo for Meshy concept/head jobs."""

    project = Path(project_dir)
    intake_path = project / "references" / "intake.yaml"
    if intake_path.exists():
        intake = yaml.safe_load(intake_path.read_text()) or {}
        rel = intake.get("reference_photo", "")
        if rel:
            candidate = project / rel
            if candidate.exists():
                return candidate
    ref_dir = project / "photos" / "reference"
    if ref_dir.is_dir():
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            matches = sorted(ref_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def resolve_head_crop(project_dir: Path | str, subject: str) -> Path:
    project = Path(project_dir)
    for name in (f"crop-{subject}.jpg", f"crop-{subject}.jpeg", f"crop-{subject}.png"):
        candidate = project / "photos" / "reference" / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Head crop not found for {subject}. Save photos/reference/crop-{subject}.jpg before meshy head."
    )


def meshy_concept(
    project_dir: Path | str,
    *,
    photo: Path | str | None = None,
    client: MeshyClient | None = None,
) -> dict[str, Any]:
    """Run Figure prototype (or text-to-image fallback) and save concept PNG."""

    project = Path(project_dir)
    image = Path(photo) if photo else resolve_reference_photo(project)
    if image is None or not image.exists():
        raise FileNotFoundError("Reference photo not found for meshy concept")

    mesh_client = client or MeshyClient.from_env()
    dest = project / "photos" / "reference" / "concept-meshy.png"
    endpoint = "creative-lab/figure/v1/prototype"
    task: dict[str, Any]
    try:
        task = mesh_client.run_figure_prototype(image)
    except MeshyError:
        endpoint = "v1/text-to-image"
        task = mesh_client.run_text_to_image(DIORAMA_CONCEPT_PROMPT)

    urls = mesh_client.extract_model_urls(task)
    image_url = urls.get("image_url") or urls.get("png") or urls.get("result_url")
    if not image_url:
        image_urls = task.get("image_urls")
        if isinstance(image_urls, list) and image_urls:
            image_url = str(image_urls[0])
    if not image_url:
        raise MeshyError(f"No concept image URL in Meshy task: {list(urls)}")
    mesh_client.download_url(image_url, dest)

    provenance = {
        "concept": {
            "task_id": task.get("id") or task.get("task_id"),
            "endpoint": endpoint,
            "artifact": "photos/reference/concept-meshy.png",
            "credits": task.get("consumed_credits"),
        }
    }
    write_mesh_provenance(project, provenance)
    return {"concept_path": str(dest), "task": task, "endpoint": endpoint}


def meshy_head(
    project_dir: Path | str,
    *,
    subject: str,
    crop: Path | str | None = None,
    client: MeshyClient | None = None,
) -> dict[str, Any]:
    """Run image-to-3d on a cropped head photo and save STL."""

    project = Path(project_dir)
    image = Path(crop) if crop else resolve_head_crop(project, subject)
    mesh_client = client or MeshyClient.from_env()
    task = mesh_client.run_image_to_3d(image)
    urls = mesh_client.extract_model_urls(task)
    stl_url = urls.get("stl") or urls.get("model_url")
    if not stl_url:
        raise MeshyError(f"No STL URL in image-to-3d task: {list(urls)}")

    mesh_dir = project / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    dest = mesh_dir / f"{subject}-head.stl"
    mesh_client.download_url(stl_url, dest)
    task_id = str(task.get("id") or task.get("task_id") or "")

    provenance_path = mesh_dir / "provenance.yaml"
    provenance = yaml.safe_load(provenance_path.read_text()) if provenance_path.exists() else {}
    provenance.setdefault("heads", {})
    provenance["heads"][subject] = {
        "task_id": task_id,
        "endpoint": "v1/image-to-3d",
        "credits": 20,
        "artifact": f"mesh/{subject}-head.stl",
    }
    write_mesh_provenance(project, provenance)
    intake = mesh_intake(
        project,
        file=dest,
        role=f"head_{subject}",
        meshy_task_id=task_id,
        endpoint="v1/image-to-3d",
    )
    return {"stl_path": str(dest), "task": task, "intake": intake}


def meshy_analyze(
    project_dir: Path | str,
    *,
    subject: str | None = None,
    stl: Path | str | None = None,
    input_task_id: str | None = None,
    client: MeshyClient | None = None,
) -> dict[str, Any]:
    """Run free Meshy analyze-printability and write JSON report under mesh/."""

    project = Path(project_dir)
    mesh_client = client or MeshyClient.from_env()
    task_id = input_task_id
    if not task_id and subject:
        prov = yaml.safe_load((project / "mesh" / "provenance.yaml").read_text()) if (project / "mesh" / "provenance.yaml").exists() else {}
        task_id = (prov.get("heads", {}).get(subject) or {}).get("task_id")
    if not task_id:
        raise MeshyError("analyze requires --subject (with provenance task_id) or --task-id")
    task = mesh_client.analyze_printability(input_task_id=task_id)
    report_path = project / "mesh" / f"analyze-{subject or 'model'}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(task, indent=2) + "\n")
    return {"report_path": str(report_path), "task": task, "stl": str(stl) if stl else None}


def scaffold_mesh_without_api(project_dir: Path | str) -> dict[str, Any]:
    """Scaffold mesh/ and document next steps when MESHY_API_KEY is unset."""

    project = Path(project_dir)
    mesh_dir = project / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    readme = mesh_dir / "NEXT_STEPS.md"
    readme.write_text(
        "\n".join(
            [
                "# Meshy head meshes — manual next steps",
                "",
                "MESHY_API_KEY was not set during scaffold. Do not commit API keys.",
                "",
                "1. Export head crops: `photos/reference/crop-woman.jpg`, `photos/reference/crop-dog.jpg`",
                "2. `export MESHY_API_KEY=msy_...` (or test mode dummy key for dry runs)",
                "3. `uv run bambu meshy concept projects/<slug>`",
                "4. `uv run bambu meshy head projects/<slug> --subject woman`",
                "5. `uv run bambu meshy head projects/<slug> --subject dog`",
                "6. `uv run bambu meshy analyze projects/<slug> --subject woman`",
                "7. Shapr3D fuse per docs/learning/shapr3d-fusion-workflow.md",
                "",
            ]
        )
        + "\n"
    )
    write_mesh_provenance(project, {"status": "awaiting_meshy_api_key"})
    return {"mesh_dir": str(mesh_dir), "next_steps_path": str(readme), "api_key_set": False}
