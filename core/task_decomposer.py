"""NCore Genesis — Task Decomposer v7.6
Analyzes complex prompts and decomposes them into executable sub-tasks.
Uses external GPU providers via Bifrost for analysis.
"""
import os, json, re, asyncio, httpx, structlog
from pathlib import Path

log = structlog.get_logger()

BIFROST_URL = os.environ.get("BIFROST_URL", "http://localhost:8000")


class TaskDecomposer:
    """Analyzes prompts and decomposes into optimal execution plans."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def analyze(self, task: str, image_paths: list[str] = None) -> dict:
        """Analyze a task and return an execution plan.

        Returns:
            {
                task_type: "text_to_video" | "face_swap_video" | "image_to_video" | ...,
                requires_images: bool,
                image_issues: list[str],  # "need higher resolution", "face not detected", etc.
                sub_tasks: list[dict],    # ordered execution steps
                gpu_profile: str,         # recommended GPU
                estimated_cost: float,
                estimated_time_s: int,
                parallel_tasks: list[list[int]],  # which sub_tasks can run in parallel
            }
        """
        image_paths = image_paths or []

        # Quick heuristic analysis (no LLM needed)
        analysis = self._heuristic_analyze(task, image_paths)

        # If images are provided, validate them
        if image_paths:
            image_issues = await self._validate_images(image_paths)
            analysis["image_issues"] = image_issues
            if image_issues:
                analysis["blocked"] = True
                analysis["block_reason"] = "; ".join(image_issues)

        log.info("task_decomposer.analyze", task_type=analysis["task_type"],
                 sub_tasks=len(analysis.get("sub_tasks", [])),
                 requires_images=analysis["requires_images"])
        return analysis

    def _heuristic_analyze(self, task: str, image_paths: list[str]) -> dict:
        """Fast keyword-based task analysis."""
        text = task.lower()
        has_images = len(image_paths) > 0

        # Detect task type
        is_video = any(kw in text for kw in ["video", "animate", "motion", "clip", "footage"])
        is_image = any(kw in text for kw in ["image", "picture", "photo", "render"]) and not is_video
        has_face_ref = any(kw in text for kw in ["attached", "reference", "pic ", "pic1", "pic2", "photo of", "featuring the"])
        needs_faceswap = has_face_ref or (has_images and is_video)
        is_nsfw = any(kw in text for kw in ["nsfw", "adult", "nude", "explicit", "hardcore", "xxx"])

        # Parse duration
        duration_match = re.search(r'(\d+)\s*(?:second|sec|s\b)', text)
        duration_s = int(duration_match.group(1)) if duration_match else 5
        frames = duration_s * 16  # 16fps default

        # Determine if HD needed
        needs_hd = duration_s > 10 or any(kw in text for kw in ["4k", "hd", "high quality", "hyper realistic", "hyperrealistic"])

        # Build task type
        if is_video and needs_faceswap:
            task_type = "face_swap_video"
        elif is_video and has_images:
            task_type = "image_to_video"
        elif is_video:
            task_type = "text_to_video"
        elif is_image and needs_faceswap:
            task_type = "face_swap_image"
        elif is_image:
            task_type = "text_to_image"
        else:
            task_type = "text_generation"

        # Check if images are required but missing
        requires_images = needs_faceswap or task_type in ("image_to_video", "face_swap_image")
        missing_images = requires_images and not has_images

        # Determine expected face count from prompt
        expected_faces = 0
        if "male" in text and "female" in text:
            expected_faces = 2
        elif any(kw in text for kw in ["person", "man", "woman", "male", "female", "him", "her"]):
            expected_faces = 1
        faces_match = len(image_paths) >= expected_faces if expected_faces > 0 else True

        # Build sub-tasks
        sub_tasks = []
        if task_type == "face_swap_video":
            sub_tasks = [
                {"id": 0, "name": "validate_images", "type": "analysis", "gpu": False,
                 "description": "Validate reference images: face detection, resolution, quality"},
                {"id": 1, "name": "warm_gpu", "type": "provision", "gpu": True,
                 "description": f"Provision {'A100' if needs_hd else 'RTX 4090'} with ComfyUI + ReActor",
                 "parallel_with": [0]},
                {"id": 2, "name": "generate_base_video", "type": "generation", "gpu": True,
                 "description": f"Generate {duration_s}s base video using Wan 2.2 {'14B' if needs_hd else '5B'}",
                 "depends_on": [0, 1]},
                {"id": 3, "name": "face_swap", "type": "post_process", "gpu": True,
                 "description": f"Apply ReActor face-swap for {expected_faces} face(s)",
                 "depends_on": [2]},
                {"id": 4, "name": "quality_check", "type": "analysis", "gpu": False,
                 "description": "Verify face consistency, motion quality, artifact check",
                 "depends_on": [3]},
            ]
        elif task_type == "text_to_video":
            sub_tasks = [
                {"id": 0, "name": "warm_gpu", "type": "provision", "gpu": True},
                {"id": 1, "name": "generate_video", "type": "generation", "gpu": True, "depends_on": [0]},
            ]
        elif task_type == "image_to_video":
            sub_tasks = [
                {"id": 0, "name": "validate_images", "type": "analysis", "gpu": False},
                {"id": 1, "name": "warm_gpu", "type": "provision", "gpu": True, "parallel_with": [0]},
                {"id": 2, "name": "generate_i2v", "type": "generation", "gpu": True, "depends_on": [0, 1]},
            ]

        return {
            "task_type": task_type,
            "requires_images": requires_images,
            "missing_images": missing_images,
            "expected_faces": expected_faces,
            "faces_provided": len(image_paths),
            "faces_match": faces_match,
            "duration_s": duration_s,
            "frames": frames,
            "needs_hd": needs_hd,
            "is_nsfw": is_nsfw,
            "gpu_profile": "video-gen-hd" if needs_hd else "video-gen",
            "estimated_cost": round(0.5 * (duration_s / 5) * (2 if needs_hd else 1) * (1.5 if needs_faceswap else 1), 2),
            "estimated_time_s": duration_s * 8 + (60 if needs_faceswap else 0) + 30,  # rough estimate
            "sub_tasks": sub_tasks,
            "image_issues": [],
            "blocked": missing_images,
            "block_reason": f"This task requires {expected_faces} reference image(s) but {len(image_paths)} were provided. Please attach face reference photos." if missing_images else None,
        }

    async def _validate_images(self, image_paths: list[str]) -> list[str]:
        """Validate uploaded images for face-swap readiness."""
        issues = []

        for i, path in enumerate(image_paths):
            p = Path(path)
            if not p.exists():
                issues.append(f"Image {i+1}: File not found")
                continue

            size = p.stat().st_size
            if size < 10_000:  # < 10KB
                issues.append(f"Image {i+1}: Too small ({size} bytes) — likely too low resolution for facial matching")
            if size > 50_000_000:  # > 50MB
                issues.append(f"Image {i+1}: Very large ({size // 1_000_000}MB) — will slow upload to GPU")

            # Check format
            ext = p.suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                issues.append(f"Image {i+1}: Unsupported format '{ext}' — use JPG or PNG")

            # Basic resolution check via image header (no heavy deps)
            try:
                with open(path, "rb") as f:
                    header = f.read(32)
                    # PNG header check
                    if header[:8] == b'\x89PNG\r\n\x1a\n':
                        w = int.from_bytes(header[16:20], 'big')
                        h = int.from_bytes(header[20:24], 'big')
                        if w < 256 or h < 256:
                            issues.append(f"Image {i+1}: Resolution too low ({w}x{h}) — minimum 512x512 recommended for facial matching")
                        elif w < 512 or h < 512:
                            issues.append(f"Image {i+1}: Low resolution ({w}x{h}) — may produce blurry face swap. 1024x1024+ recommended")
                    # JPEG doesn't have resolution in first 32 bytes, skip detailed check
            except Exception:
                pass

        return issues

    async def close(self):
        await self.client.aclose()
