"""NCore Genesis — Dynamic Vast.ai Pod Provisioner v3.0

Spins up a Vast.ai GPU pod on demand, runs the job (ComfyUI workflow),
returns the output URL, then DESTROYS the instance immediately.
Used for: video generation (Wan 2.2 NSFW) and image generation (FLUX).
All pods are ephemeral — zero idle cost.
"""
from __future__ import annotations
import subprocess, time, json, os, httpx
from dataclasses import dataclass


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
        "video": {
            "image": "vastai/comfyui-wan22:latest",
            "disk_gb": 100,
            "startup_wait_sec": 120,   # Wan 2.2 weights take ~2 min to load
        },
        "image": {
            "image": "vastai/comfyui-flux:latest",
            "disk_gb": 50,
            "startup_wait_sec": 60,
        },
    }

    # ── Latency optimisation: keep one warm reserve worker per type ─────────
    # Set env var VAST_RESERVE_VIDEO_ID / VAST_RESERVE_IMAGE_ID to a
    # pre-warmed instance ID; provisioner uses it first before creating new.
    def _reserve_id(self, pod_type: str) -> str | None:
        key = f"VAST_RESERVE_{pod_type.upper()}_ID"
        return os.environ.get(key)

    def run(self, pod_type: str, prompt: str, extra: dict = {}) -> PodResult:
        t0 = time.time()
        instance_id = self._reserve_id(pod_type)   # use warm instance if set
        created_new = instance_id is None

        try:
            tmpl = self.TEMPLATES[pod_type]

            if created_new:
                offer = self._find_offer(tmpl["disk_gb"])
                if not offer:
                    return PodResult(False, {}, "", 0, 0, "No suitable GPU offer")
                instance_id = self._create(offer, tmpl)
                if not instance_id:
                    return PodResult(False, {}, "", 0, 0, "Instance creation failed")

            api_url = self._wait_ready(instance_id, tmpl["startup_wait_sec"])
            if not api_url:
                self._destroy(instance_id)
                return PodResult(False, {}, instance_id, 0, 0, "Startup timeout")

            if pod_type == "video":
                output = self._run_wan22(api_url, prompt, extra)
            else:
                output = self._run_flux(api_url, prompt, extra)

            runtime = time.time() - t0
            return PodResult(True, output, instance_id, self._est_cost(runtime), runtime)

        except Exception as e:
            return PodResult(False, {}, instance_id or "", 0, time.time()-t0, str(e))
        finally:
            # Destroy only if we created a new instance (reserve stays alive)
            if created_new and instance_id:
                self._destroy(instance_id)

    # ── Vast CLI wrappers ────────────────────────────────────────────────────

    def _find_offer(self, disk_gb: int) -> str | None:
        r = subprocess.run(
            ["vastai", "search", "offers",
             self.GPU_SPEC, f"disk_space>={disk_gb}",
             "--order", "dph_total", "--raw", "--limit", "5"],
            capture_output=True, text=True)
        offers = json.loads(r.stdout or "[]")
        if not offers:
            return None
        return str(sorted(offers, key=lambda x: x.get("dph_total", 999))[0]["id"])

    def _create(self, offer_id: str, tmpl: dict) -> str | None:
        r = subprocess.run([
            "vastai", "create", "instance", offer_id,
            "--image", tmpl["image"],
            "--disk", str(tmpl["disk_gb"]),
            "--env", "-p 8188:8188",
            "--ssh", "--direct", "--raw"
        ], capture_output=True, text=True)
        data = json.loads(r.stdout or "{}")
        return str(data.get("new_contract", "")) or None

    def _wait_ready(self, iid: str, max_wait: int) -> str | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            r = subprocess.run(
                ["vastai", "show", "instance", iid, "--raw"],
                capture_output=True, text=True)
            info = json.loads(r.stdout or "{}")
            if info.get("actual_status") == "running":
                ip = info.get("public_ipaddr", "")
                port = (info.get("ports") or {}).get("8188/tcp", [{}])[0].get("HostPort", "8188")
                if ip:
                    return f"http://{ip}:{port}"
            time.sleep(10)
        return None

    def _destroy(self, iid: str):
        subprocess.run(["vastai", "destroy", "instance", iid], capture_output=True)

    def _est_cost(self, secs: float) -> float:
        return (secs / 3600) * 0.17   # RTX 4090 ~$0.17/hr on Vast

    # ── ComfyUI job runners ──────────────────────────────────────────────────

    def _submit_and_poll(self, api_url: str, workflow: dict, timeout: int) -> dict:
        r = httpx.post(f"{api_url}/prompt", json=workflow, timeout=30)
        pid = r.json().get("prompt_id")
        if not pid:
            raise Exception("ComfyUI rejected workflow")
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = httpx.get(f"{api_url}/history/{pid}", timeout=10).json()
            if pid in status:
                outputs = status[pid].get("outputs", {})
                for _, out in outputs.items():
                    if "gifs" in out:
                        fn = out["gifs"][0]["filename"]
                        return {"video_url": f"{api_url}/view?filename={fn}", "filename": fn}
                    if "images" in out:
                        fn = out["images"][0]["filename"]
                        return {"image_url": f"{api_url}/view?filename={fn}", "filename": fn}
            time.sleep(5)
        raise Exception("Job timed out")

    def _run_wan22(self, api_url: str, prompt: str, p: dict) -> dict:
        """Wan 2.2 Remix NSFW text-to-video via ComfyUI."""
        workflow = {
            "prompt": {
                "3":  {"class_type": "VAELoader",
                       "inputs": {"vae_name": "Wan2_1_VAE_bf16.safetensors"}},
                "4":  {"class_type": "WanVideoModelLoader",
                       "inputs": {"model": "Wan2.2_Remix_NSFW_t2v_14b_high_lighting_v2.0.safetensors",
                                  "attention_mode": "sdpa"}},
                "5":  {"class_type": "WanVideoModelLoader",
                       "inputs": {"model": "Wan2.2_Remix_NSFW_t2v_14b_low_lighting_v2.0.safetensors",
                                  "attention_mode": "sdpa"}},
                "6":  {"class_type": "WanVideoTextEncode",
                       "inputs": {"text_encoder": "nsfw_wan_umt5-xxl_bf16.safetensors",
                                  "positive": prompt,
                                  "negative": p.get("negative", "low quality, blurry")}},
                "7":  {"class_type": "WanVideoSampler",
                       "inputs": {"steps": p.get("steps", 8),
                                  "split_step": p.get("split_step", 4),
                                  "width": p.get("width", 832),
                                  "height": p.get("height", 480),
                                  "num_frames": p.get("frames", 65),
                                  "fps": p.get("fps", 16),
                                  "seed": p.get("seed", -1)}},
                "8":  {"class_type": "VHS_VideoCombine",
                       "inputs": {"frame_rate": p.get("fps", 16),
                                  "filename_prefix": "ncore_video"}}
            }
        }
        return self._submit_and_poll(api_url, workflow, timeout=600)

    def _run_flux(self, api_url: str, prompt: str, p: dict) -> dict:
        """FLUX.1-dev image generation via ComfyUI."""
        workflow = {
            "prompt": {
                "1": {"class_type": "CheckpointLoaderSimple",
                      "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"}},
                "2": {"class_type": "CLIPTextEncode",
                      "inputs": {"text": prompt, "clip": ["1", 1]}},
                "3": {"class_type": "KSampler",
                      "inputs": {"steps": p.get("steps", 20),
                                 "cfg": p.get("cfg", 3.5),
                                 "width": p.get("width", 1024),
                                 "height": p.get("height", 1024),
                                 "seed": p.get("seed", -1)}},
                "4": {"class_type": "SaveImage",
                      "inputs": {"filename_prefix": "ncore_img"}}
            }
        }
        return self._submit_and_poll(api_url, workflow, timeout=120)
