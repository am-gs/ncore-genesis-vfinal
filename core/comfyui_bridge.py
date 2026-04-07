"""NCore Genesis — ComfyUI Bridge v7.6
Automates video/image generation via ComfyUI on Vast.ai GPU pods.
Lifecycle: provision pod -> wait ready -> upload workflow -> queue prompt -> poll -> download -> destroy pod
"""
from __future__ import annotations

import asyncio
import os
import random
import time

import httpx
import structlog

log = structlog.get_logger()


class ComfyUIBridge:
    """Manages ComfyUI workflows on ephemeral Vast.ai pods."""

    def __init__(self, gpu_manager=None):
        """
        Args:
            gpu_manager: Instance of GPUManager from gpu_manager.py.
                         If None, creates one internally.
        """
        if gpu_manager is None:
            from gpu_manager import GPUManager
            gpu_manager = GPUManager()
        self.gpu = gpu_manager
        self.client = httpx.AsyncClient(timeout=300)

    # -- Workflow templates ---------------------------------------------------

    def _wan22_video_workflow(self, prompt: str, negative: str = "",
                              width: int = 832, height: int = 480,
                              frames: int = 81, steps: int = 30,
                              cfg: float = 6.0, seed: int = -1) -> dict:
        """Build Wan 2.2 text-to-video workflow JSON.

        Uses the standard ComfyUI API format with node IDs.
        Wan 2.2 5B model for RTX 4090 (24GB VRAM).
        """
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        default_negative = (
            "blurry, low quality, distorted, watermark, text, logo, "
            "worst quality, jpeg artifacts, deformed, mutation, extra limbs"
        )
        neg = negative or default_negative

        return {
            "prompt": {
                "1": {
                    "class_type": "WanVideoModelLoader",
                    "inputs": {"model_name": "wan2.2_5b_t2v.safetensors"},
                },
                "2": {
                    "class_type": "WanVideoTextEncode",
                    "inputs": {
                        "model": ["1", 0],
                        "positive_prompt": prompt,
                        "negative_prompt": neg,
                    },
                },
                "3": {
                    "class_type": "WanVideoSampler",
                    "inputs": {
                        "model": ["1", 0],
                        "conditioning": ["2", 0],
                        "width": width,
                        "height": height,
                        "num_frames": frames,
                        "steps": steps,
                        "cfg": cfg,
                        "seed": seed,
                    },
                },
                "4": {
                    "class_type": "WanVideoDecode",
                    "inputs": {"samples": ["3", 0], "model": ["1", 0]},
                },
                "5": {
                    "class_type": "SaveAnimatedWEBP",
                    "inputs": {
                        "images": ["4", 0],
                        "filename_prefix": f"ncore_video_{seed}",
                        "fps": 16,
                        "quality": 90,
                    },
                },
            }
        }

    def _flux_image_workflow(self, prompt: str, negative: str = "",
                             width: int = 1024, height: int = 1024,
                             steps: int = 20, cfg: float = 7.0,
                             seed: int = -1) -> dict:
        """Build Flux Dev text-to-image workflow JSON."""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        default_negative = "blurry, low quality, distorted, watermark, text, worst quality"
        neg = negative or default_negative

        return {
            "prompt": {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "flux1-dev.safetensors"},
                },
                "2": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": prompt, "clip": ["1", 1]},
                },
                "3": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": neg, "clip": ["1", 1]},
                },
                "4": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": width, "height": height, "batch_size": 1},
                },
                "5": {
                    "class_type": "KSampler",
                    "inputs": {
                        "model": ["1", 0],
                        "positive": ["2", 0],
                        "negative": ["3", 0],
                        "latent_image": ["4", 0],
                        "seed": seed,
                        "steps": steps,
                        "cfg": cfg,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 1.0,
                    },
                },
                "6": {
                    "class_type": "VAEDecode",
                    "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
                },
                "7": {
                    "class_type": "SaveImage",
                    "inputs": {"images": ["6", 0], "filename_prefix": f"ncore_img_{seed}"},
                },
            }
        }

    # -- Core lifecycle -------------------------------------------------------

    async def generate_video(self, prompt: str, negative: str = "",
                              width: int = 832, height: int = 480,
                              frames: int = 81, steps: int = 30,
                              hd: bool = False, task_id: str = "") -> dict:
        """Full lifecycle: provision GPU -> generate video -> download -> destroy.

        Args:
            prompt: Video description
            negative: Negative prompt (optional)
            width/height: Resolution
            frames: Number of frames (81 = ~5 seconds at 16fps)
            steps: Sampling steps
            hd: If True, use A100 80GB profile for 14B model
            task_id: For tracking

        Returns:
            {output_path, duration_s, cost_usd, gpu_profile, prompt_id, instance_id}
        """
        profile = "video-gen-hd" if hd else "video-gen"
        t0 = time.time()
        tid = task_id or f"video_{int(t0)}"

        log.info("comfyui.video.start", prompt=prompt[:80], profile=profile, task_id=tid)

        instance = await self.gpu.provision(profile, tid)
        instance_id = instance["instance_id"]

        try:
            api_url = await self._wait_comfyui_ready(instance["ip"], instance.get("port", 8188))
            workflow = self._wan22_video_workflow(prompt, negative, width, height, frames, steps)
            prompt_id = await self._queue_prompt(api_url, workflow)
            output_data = await self._poll_completion(api_url, prompt_id, timeout=600)
            output_path = await self._download_output(api_url, output_data, f"/tmp/ncore_video_{tid}")

            duration = time.time() - t0
            cost = instance.get("cost_per_hour", 0.5) * (duration / 3600)

            log.info("comfyui.video.complete", duration_s=round(duration, 1),
                     cost_usd=round(cost, 4), output=output_path, task_id=tid)

            return {
                "output_path": output_path,
                "duration_s": round(duration, 1),
                "cost_usd": round(cost, 4),
                "gpu_profile": profile,
                "prompt_id": prompt_id,
                "instance_id": instance_id,
            }
        finally:
            await self.gpu.destroy(instance_id)

    async def generate_image(self, prompt: str, negative: str = "",
                              width: int = 1024, height: int = 1024,
                              steps: int = 20, task_id: str = "") -> dict:
        """Full lifecycle: provision GPU -> generate image -> download -> destroy."""
        t0 = time.time()
        tid = task_id or f"img_{int(t0)}"

        log.info("comfyui.image.start", prompt=prompt[:80], task_id=tid)

        instance = await self.gpu.provision("image-gen", tid)
        instance_id = instance["instance_id"]

        try:
            api_url = await self._wait_comfyui_ready(instance["ip"], instance.get("port", 8188))
            workflow = self._flux_image_workflow(prompt, negative, width, height, steps)
            prompt_id = await self._queue_prompt(api_url, workflow)
            output_data = await self._poll_completion(api_url, prompt_id, timeout=300)
            output_path = await self._download_output(api_url, output_data, f"/tmp/ncore_img_{tid}")

            duration = time.time() - t0
            cost = instance.get("cost_per_hour", 0.5) * (duration / 3600)

            log.info("comfyui.image.complete", duration_s=round(duration, 1),
                     cost_usd=round(cost, 4), output=output_path, task_id=tid)

            return {
                "output_path": output_path,
                "duration_s": round(duration, 1),
                "cost_usd": round(cost, 4),
                "gpu_profile": "image-gen",
                "prompt_id": prompt_id,
                "instance_id": instance_id,
            }
        finally:
            await self.gpu.destroy(instance_id)

    # -- ComfyUI API helpers --------------------------------------------------

    async def _wait_comfyui_ready(self, ip: str, port: int = 8188, timeout: int = 180) -> str:
        """Poll ComfyUI /system_stats until it responds."""
        api_url = f"http://{ip}:{port}"
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                r = await self.client.get(f"{api_url}/system_stats", timeout=5)
                if r.status_code == 200:
                    log.info("comfyui.ready", url=api_url)
                    return api_url
            except Exception:
                pass
            await asyncio.sleep(5)

        raise TimeoutError(f"ComfyUI at {api_url} not ready after {timeout}s")

    async def _queue_prompt(self, api_url: str, workflow: dict) -> str:
        """Submit workflow to ComfyUI /prompt endpoint."""
        r = await self.client.post(f"{api_url}/prompt", json=workflow)
        r.raise_for_status()
        data = r.json()
        prompt_id = data.get("prompt_id", "")
        log.info("comfyui.queued", prompt_id=prompt_id)
        return prompt_id

    async def _poll_completion(self, api_url: str, prompt_id: str, timeout: int = 600) -> dict:
        """Poll /history/{prompt_id} until generation completes."""
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                r = await self.client.get(f"{api_url}/history/{prompt_id}", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if prompt_id in data:
                        status = data[prompt_id].get("status", {})
                        if status.get("completed", False) or status.get("status_str") == "success":
                            log.info("comfyui.completed", prompt_id=prompt_id)
                            return data[prompt_id].get("outputs", {})
                        if status.get("status_str") == "error":
                            raise RuntimeError(f"ComfyUI generation failed: {status}")
            except (httpx.RequestError, httpx.TimeoutException):
                pass
            await asyncio.sleep(3)

        raise TimeoutError(f"ComfyUI generation {prompt_id} timed out after {timeout}s")

    async def _download_output(self, api_url: str, outputs: dict, output_dir: str) -> str:
        """Download generated files from ComfyUI /view endpoint."""
        os.makedirs(output_dir, exist_ok=True)
        downloaded = []

        for _node_id, node_output in outputs.items():
            for file_type in ("images", "gifs", "videos"):
                for item in node_output.get(file_type, []):
                    filename = item.get("filename", "")
                    subfolder = item.get("subfolder", "")
                    params = {"filename": filename}
                    if subfolder:
                        params["subfolder"] = subfolder

                    r = await self.client.get(f"{api_url}/view", params=params, timeout=120)
                    if r.status_code == 200:
                        out_path = os.path.join(output_dir, filename)
                        with open(out_path, "wb") as f:
                            f.write(r.content)
                        downloaded.append(out_path)
                        log.info("comfyui.downloaded", file=out_path, size_bytes=len(r.content))

        if not downloaded:
            raise RuntimeError("No output files found in ComfyUI response")
        return downloaded[0]

    async def close(self):
        await self.client.aclose()
