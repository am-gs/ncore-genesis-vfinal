"""NCore Genesis — Dynamic Vast.ai Pod Provisioner v3.1

Audit fix H4: All CLI calls now use asyncio.create_subprocess_exec
and asyncio.sleep — no blocking of the event loop.
Reserve-pool pattern preserved for zero-cold-start operation.
"""
from __future__ import annotations
import asyncio, json, os, time
from dataclasses import dataclass
import httpx
import structlog

log = structlog.get_logger()


@dataclass
class PodResult:
    success: bool
    output: dict
    instance_id: str
    cost_usd: float
    runtime_seconds: float
    error: str = None


class DynamicPodProvisioner:
    GPU_SPEC = "gpu_name=RTX_4090 gpu_ram>=24 inet_down>200"
    TEMPLATES = {
        "video": {"image": "vastai/comfyui-wan22:latest",  "disk_gb": 100, "startup_wait_sec": 120},
        "image": {"image": "vastai/comfyui-flux:latest",   "disk_gb": 50,  "startup_wait_sec": 60},
    }

    def _reserve_id(self, pod_type: str) -> str | None:
        return os.environ.get(f"VAST_RESERVE_{pod_type.upper()}_ID")

    # ── Public entry point (async) ────────────────────────────────────────────
    async def run(self, pod_type: str, prompt: str, extra: dict = {}) -> PodResult:
        t0          = time.time()
        instance_id = self._reserve_id(pod_type)
        created_new = instance_id is None

        try:
            tmpl = self.TEMPLATES[pod_type]
            if created_new:
                offer = await self._find_offer(tmpl["disk_gb"])
                if not offer:
                    return PodResult(False, {}, "", 0, 0, "No suitable GPU offer found")
                instance_id = await self._create(offer, tmpl)
                if not instance_id:
                    return PodResult(False, {}, "", 0, 0, "Instance creation failed")

            api_url = await self._wait_ready(instance_id, tmpl["startup_wait_sec"])
            if not api_url:
                await self._destroy(instance_id)
                return PodResult(False, {}, instance_id, 0, 0, "Startup timeout")

            output  = await self._run_job(pod_type, api_url, prompt, extra)
            runtime = time.time() - t0
            return PodResult(True, output, instance_id, self._est_cost(runtime), runtime)

        except Exception as e:
            log.error("pod.run_failed", error=str(e))
            return PodResult(False, {}, instance_id or "", 0, time.time()-t0, str(e))
        finally:
            if created_new and instance_id:
                await self._destroy(instance_id)

    # ── Async CLI wrappers (H4 fix) ───────────────────────────────────────────
    async def _vastai(self, *args) -> str:
        proc = await asyncio.create_subprocess_exec(
            "vastai", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode()

    async def _find_offer(self, disk_gb: int) -> str | None:
        raw    = await self._vastai("search", "offers", self.GPU_SPEC,
                                    f"disk_space>={disk_gb}",
                                    "--order", "dph_total", "--raw", "--limit", "5")
        offers = json.loads(raw or "[]")
        if not offers:
            return None
        return str(sorted(offers, key=lambda x: x.get("dph_total", 999))[0]["id"])

    async def _create(self, offer_id: str, tmpl: dict) -> str | None:
        raw  = await self._vastai("create", "instance", offer_id,
                                   "--image", tmpl["image"],
                                   "--disk",  str(tmpl["disk_gb"]),
                                   "--env",   "-p 8188:8188",
                                   "--ssh", "--direct", "--raw")
        data = json.loads(raw or "{}")
        return str(data.get("new_contract", "")) or None

    async def _wait_ready(self, iid: str, max_wait: int) -> str | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            raw  = await self._vastai("show", "instance", iid, "--raw")
            info = json.loads(raw or "{}")
            if info.get("actual_status") == "running":
                ip   = info.get("public_ipaddr", "")
                port = (info.get("ports") or {}).get("8188/tcp", [{}])[0].get("HostPort", "8188")
                if ip:
                    return f"http://{ip}:{port}"
            await asyncio.sleep(10)          # H4: async sleep, not blocking time.sleep
        return None

    async def _destroy(self, iid: str):
        await self._vastai("destroy", "instance", iid)
        log.info("pod.destroyed", instance_id=iid)

    def _est_cost(self, secs: float) -> float:
        return (secs / 3600) * 0.17

    # ── ComfyUI job runners ───────────────────────────────────────────────────
    async def _run_job(self, pod_type: str, api_url: str, prompt: str, p: dict) -> dict:
        if pod_type == "video":
            workflow = self._wan22_workflow(prompt, p)
            timeout  = 600
        else:
            workflow = self._flux_workflow(prompt, p)
            timeout  = 120
        return await self._submit_and_poll(api_url, workflow, timeout)

    async def _submit_and_poll(self, api_url: str, workflow: dict, timeout: int) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r   = await client.post(f"{api_url}/prompt", json=workflow)
            pid = r.json().get("prompt_id")
            if not pid:
                raise Exception("ComfyUI rejected workflow")
            deadline = time.time() + timeout
            while time.time() < deadline:
                status = (await client.get(f"{api_url}/history/{pid}")).json()
                if pid in status:
                    for _, out in status[pid].get("outputs", {}).items():
                        if "gifs" in out:
                            fn = out["gifs"][0]["filename"]
                            return {"video_url": f"{api_url}/view?filename={fn}", "filename": fn}
                        if "images" in out:
                            fn = out["images"][0]["filename"]
                            return {"image_url": f"{api_url}/view?filename={fn}", "filename": fn}
                await asyncio.sleep(5)
        raise Exception("Job timed out")

    def _wan22_workflow(self, prompt: str, p: dict) -> dict:
        return {"prompt": {
            "3": {"class_type": "VAELoader",
                  "inputs": {"vae_name": "Wan2_1_VAE_bf16.safetensors"}},
            "4": {"class_type": "WanVideoModelLoader",
                  "inputs": {"model": "Wan2.2_Remix_NSFW_t2v_14b_high_lighting_v2.0.safetensors",
                             "attention_mode": "sdpa"}},
            "5": {"class_type": "WanVideoModelLoader",
                  "inputs": {"model": "Wan2.2_Remix_NSFW_t2v_14b_low_lighting_v2.0.safetensors",
                             "attention_mode": "sdpa"}},
            "6": {"class_type": "WanVideoTextEncode",
                  "inputs": {"text_encoder": "nsfw_wan_umt5-xxl_bf16.safetensors",
                             "positive": prompt,
                             "negative": p.get("negative", "low quality, blurry")}},
            "7": {"class_type": "WanVideoSampler",
                  "inputs": {"steps": p.get("steps", 8), "split_step": p.get("split_step", 4),
                             "width": p.get("width", 832), "height": p.get("height", 480),
                             "num_frames": p.get("frames", 65), "fps": p.get("fps", 16),
                             "seed": p.get("seed", -1)}},
            "8": {"class_type": "VHS_VideoCombine",
                  "inputs": {"frame_rate": p.get("fps", 16), "filename_prefix": "ncore_video"}}
        }}

    def _flux_workflow(self, prompt: str, p: dict) -> dict:
        return {"prompt": {
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "KSampler",
                  "inputs": {"steps": p.get("steps", 20), "cfg": p.get("cfg", 3.5),
                             "width": p.get("width", 1024), "height": p.get("height", 1024),
                             "seed": p.get("seed", -1)}},
            "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ncore_img"}}
        }}
