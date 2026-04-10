"""NCore Genesis — Intelligent GPU Lifecycle Manager v7.5

Uses the Vast.ai Python SDK (vastai-sdk) for GPU provisioning,
cost tracking, and orphan cleanup.  All synchronous SDK calls are
wrapped with asyncio.to_thread to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import structlog

log = structlog.get_logger()

# ── GPU Profiles ──────────────────────────────────────────────────────────────
# Vast.ai template ID for ComfyUI + ReActor + Wan 2.2 face-swap pipeline
# Template auto-provisions: Wan 2.2 I2V 14B FP8, ReActor, FaceDetailer,
# CodeFormer, GPEN, VideoHelperSuite, YOLO face detection
COMFYUI_TEMPLATE_ID = 381886  # ComfyUI-FaceSwap-v4-FIXED

# IMPORTANT: The correct Vast.ai ComfyUI Docker image is vastai/comfy:latest
# NOT vastai/comfyui (which does not exist and will fail with pull access denied)
COMFYUI_IMAGE = "vastai/comfy:latest"

GPU_PROFILES: dict[str, dict[str, Any]] = {
    "infer-light": {
        "query": "gpu_name=RTX_4090 num_gpus=1 gpu_ram>=24 inet_down>200 disk_space>=50",
        "image": "vllm/vllm-openai:latest",
        "disk": 50,
        "use_case": "LLM inference, image gen",
    },
    "infer-heavy": {
        "query": "gpu_name=A100_SXM num_gpus=1 gpu_ram>=80 inet_down>200 disk_space>=100",
        "image": "vllm/vllm-openai:latest",
        "disk": 100,
        "use_case": "Large MoE inference, 120B+ models",
    },
    "video-gen": {
        "query": "gpu_name=RTX_4090 num_gpus=1 gpu_ram>=24 inet_down>500 disk_space>=60",
        "image": COMFYUI_IMAGE,
        "template_id": COMFYUI_TEMPLATE_ID,
        "disk": 60,
        "use_case": "Wan 2.2 I2V + ReActor face-swap video generation",
    },
    "video-gen-hd": {
        "query": "gpu_name=A100_SXM num_gpus=1 gpu_ram>=80 inet_down>500 disk_space>=100",
        "image": COMFYUI_IMAGE,
        "template_id": COMFYUI_TEMPLATE_ID,
        "disk": 100,
        "use_case": "Wan 2.2 14B full resolution + face-swap",
    },
    "video-gen-fast": {
        "query": "gpu_name=RTX_4090 num_gpus=1 gpu_ram>=24 inet_down>2000 disk_space>=60",
        "image": COMFYUI_IMAGE,
        "template_id": COMFYUI_TEMPLATE_ID,
        "disk": 60,
        "use_case": "Fast boot video gen (>2Gbps download, ~4 min boot)",
    },
    "image-gen": {
        "query": "gpu_name=RTX_4090 num_gpus=1 gpu_ram>=24 inet_down>200 disk_space>=50",
        "image": COMFYUI_IMAGE,
        "template_id": COMFYUI_TEMPLATE_ID,
        "disk": 50,
        "use_case": "Flux/SD image generation",
    },
}

# Map task types to profiles for auto-selection
_TASK_PROFILE_MAP: dict[str, str] = {
    "inference": "infer-light",
    "inference_large": "infer-heavy",
    "llm": "infer-light",
    "moe": "infer-heavy",
    "video": "video-gen",
    "video_hd": "video-gen-hd",
    "video_fast": "video-gen-fast",
    "image": "image-gen",
    "flux": "image-gen",
    "wan": "video-gen",
    "comfyui": "image-gen",
    "faceswap": "video-gen",
    "nsfw": "video-gen",
    "nsfw_fast": "video-gen-fast",
}


class GPUManager:
    """Intelligent GPU lifecycle manager backed by Vast.ai SDK."""

    def __init__(self):
        from vastai_sdk import VastAI

        api_key = os.environ.get("VAST_API_KEY")
        if not api_key:
            log.warning("gpu_manager.init", error="VAST_API_KEY not set")
        self.vast = VastAI(api_key=api_key)
        self.active_instances: dict[str, dict] = {}  # {task_id: instance_info}
        self._session_cost: float = 0.0
        self._task_costs: dict[str, float] = {}  # {task_id: cumulative_cost}
        self._start_times: dict[str, float] = {}  # {instance_id: epoch}
        log.info("gpu_manager.init", profiles=list(GPU_PROFILES.keys()))

    # ── Profile selection ─────────────────────────────────────────────────────

    async def select_profile(self, task_type: str,
                             requirements: dict | None = None) -> str:
        requirements = requirements or {}
        profile = _TASK_PROFILE_MAP.get(task_type.lower())

        # Override based on explicit VRAM requirement
        min_vram = requirements.get("min_vram_gb", 0)
        if min_vram > 24 and profile and "light" in profile:
            profile = profile.replace("light", "heavy")
        if min_vram > 24 and profile == "video-gen":
            profile = "video-gen-hd"

        # Override based on cost constraint
        if requirements.get("prefer_cheap") and profile in ("infer-heavy", "video-gen-hd"):
            profile = "infer-light" if "infer" in profile else "video-gen"

        if not profile:
            profile = "infer-light"
            log.warning("gpu_manager.select_profile", task_type=task_type,
                        fallback=profile)

        log.info("gpu_manager.select_profile", task_type=task_type,
                 profile=profile, requirements=requirements)
        return profile

    async def smart_provision(self, task_type: str, task_id: str,
                               requirements: dict = None) -> dict:
        """Intelligent provisioning: auto-selects profile, prefers interruptible,
        reuses running instances when possible."""
        requirements = requirements or {}

        # Check if we have a running instance that matches
        for tid, info in self.active_instances.items():
            profile_needed = await self.select_profile(task_type, requirements)
            if info["profile"] == profile_needed:
                log.info("gpu_manager.reuse_instance", task_id=task_id,
                         existing_task=tid, instance_id=info["instance_id"])
                return {
                    "instance_id": info["instance_id"],
                    "ip": info["ip"],
                    "port": info["port"],
                    "cost_per_hour": info["cost_per_hour"],
                    "gpu_name": info["gpu_name"],
                    "reused": True,
                }

        profile = await self.select_profile(task_type, requirements)
        return await self.provision(profile, task_id)

    # ── Provisioning ──────────────────────────────────────────────────────────

    async def provision(self, profile_name: str, task_id: str) -> dict:
        t0 = time.monotonic()
        profile = GPU_PROFILES.get(profile_name)
        if not profile:
            raise ValueError(f"Unknown GPU profile: {profile_name}")

        log.info("gpu_manager.provision.start", profile=profile_name,
                 task_id=task_id)

        # Search for cheapest offer
        offer = await self.get_cheapest_offer(profile_name)
        if not offer:
            raise RuntimeError(f"No GPU offers found for profile {profile_name}")

        offer_id = offer["id"]
        dph = offer.get("dph_total", 0)

        # Launch instance (with template if specified)
        launch_kwargs = {
            "id": offer_id,
            "image": profile["image"],
            "disk": profile["disk"],
        }
        if "template_id" in profile:
            launch_kwargs["template_id"] = profile["template_id"]
            log.info("gpu_manager.provision.using_template",
                     template_id=profile["template_id"])
        try:
            result = await asyncio.to_thread(
                self.vast.launch_instance,
                **launch_kwargs,
            )
        except Exception as e:
            log.error("gpu_manager.provision.launch_failed", offer_id=offer_id,
                      error=str(e))
            raise

        instance_id = str(result.get("new_contract", result.get("instance_id", "")))
        if not instance_id:
            raise RuntimeError(f"Launch returned no instance ID: {result}")

        info = {
            "instance_id": instance_id,
            "task_id": task_id,
            "profile": profile_name,
            "offer_id": offer_id,
            "cost_per_hour": dph,
            "gpu_name": offer.get("gpu_name", "unknown"),
            "ip": offer.get("public_ipaddr"),
            "port": None,
            "started_at": time.time(),
        }
        self.active_instances[task_id] = info
        self._start_times[instance_id] = time.time()
        elapsed = time.monotonic() - t0
        log.info("gpu_manager.provision.done", instance_id=instance_id,
                 gpu=info["gpu_name"], dph=dph, elapsed_s=round(elapsed, 2))

        return {
            "instance_id": instance_id,
            "ip": info["ip"],
            "port": info["port"],
            "cost_per_hour": dph,
            "gpu_name": info["gpu_name"],
        }

    # ── Wait for ready ────────────────────────────────────────────────────────

    async def wait_ready(self, instance_id: str, timeout: int = 180) -> str:
        t0 = time.monotonic()
        deadline = time.time() + timeout
        log.info("gpu_manager.wait_ready", instance_id=instance_id,
                 timeout_s=timeout)

        while time.time() < deadline:
            try:
                info = await asyncio.to_thread(
                    self.vast.show_instance, id=instance_id,
                )
            except Exception as e:
                log.warning("gpu_manager.wait_ready.poll_error",
                            instance_id=instance_id, error=str(e))
                await asyncio.sleep(5)
                continue

            status = info.get("actual_status", "")
            if status == "running":
                ip = info.get("public_ipaddr", "")
                ports = info.get("ports", {})
                # Find the first mapped port
                port = None
                for key, mappings in (ports or {}).items():
                    if isinstance(mappings, list) and mappings:
                        port = mappings[0].get("HostPort")
                        break
                if ip:
                    api_url = f"http://{ip}:{port or 8080}"
                    elapsed = time.monotonic() - t0
                    log.info("gpu_manager.ready", instance_id=instance_id,
                             api_url=api_url, elapsed_s=round(elapsed, 2))
                    # Update stored info with resolved ip/port
                    for task_info in self.active_instances.values():
                        if task_info["instance_id"] == instance_id:
                            task_info["ip"] = ip
                            task_info["port"] = port
                            break
                    return api_url
            await asyncio.sleep(5)

        raise TimeoutError(
            f"Instance {instance_id} not ready after {timeout}s"
        )

    # ── Destruction ───────────────────────────────────────────────────────────

    async def destroy(self, instance_id: str) -> None:
        t0 = time.monotonic()
        runtime_s = time.time() - self._start_times.pop(instance_id, time.time())
        cost = 0.0

        # Calculate cost and attribute to task
        for task_id, info in list(self.active_instances.items()):
            if info["instance_id"] == instance_id:
                cost = (runtime_s / 3600) * info.get("cost_per_hour", 0)
                self._session_cost += cost
                self._task_costs[task_id] = self._task_costs.get(task_id, 0) + cost
                del self.active_instances[task_id]
                break

        try:
            await asyncio.to_thread(self.vast.destroy_instance, id=instance_id)
        except Exception as e:
            log.error("gpu_manager.destroy.failed", instance_id=instance_id,
                      error=str(e))
            raise

        log.info("gpu_manager.destroyed", instance_id=instance_id,
                 runtime_s=round(runtime_s, 1), cost_usd=round(cost, 4),
                 elapsed_s=round(time.monotonic() - t0, 2))

    async def destroy_all(self) -> None:
        """Emergency kill all tracked instances."""
        log.warning("gpu_manager.destroy_all", count=len(self.active_instances))
        instance_ids = list({
            info["instance_id"] for info in self.active_instances.values()
        })
        for iid in instance_ids:
            try:
                await self.destroy(iid)
            except Exception as e:
                log.error("gpu_manager.destroy_all.error", instance_id=iid,
                          error=str(e))

    # ── Orphan management ─────────────────────────────────────────────────────

    async def check_orphans(self, max_idle_minutes: int = 30) -> list[str]:
        """Find instances running longer than max_idle_minutes with no task."""
        tracked_ids = {
            info["instance_id"] for info in self.active_instances.values()
        }
        try:
            instances = await asyncio.to_thread(self.vast.show_instances)
        except Exception as e:
            log.error("gpu_manager.check_orphans.failed", error=str(e))
            return []

        orphans = []
        now = time.time()
        for inst in (instances if isinstance(instances, list) else []):
            iid = str(inst.get("id", ""))
            if iid in tracked_ids:
                continue
            started = inst.get("start_date", now)
            idle_min = (now - started) / 60
            if idle_min > max_idle_minutes:
                orphans.append(iid)
                log.warning("gpu_manager.orphan_found", instance_id=iid,
                            idle_minutes=round(idle_min, 1))
        return orphans

    async def cleanup_orphans(self) -> int:
        """Destroy all orphaned instances. Returns count destroyed."""
        orphans = await self.check_orphans()
        destroyed = 0
        for iid in orphans:
            try:
                await asyncio.to_thread(self.vast.destroy_instance, id=iid)
                destroyed += 1
                log.info("gpu_manager.orphan_destroyed", instance_id=iid)
            except Exception as e:
                log.error("gpu_manager.orphan_destroy_failed", instance_id=iid,
                          error=str(e))
        log.info("gpu_manager.cleanup_orphans.done", destroyed=destroyed,
                 total_orphans=len(orphans))
        return destroyed

    # ── Offer search ──────────────────────────────────────────────────────────

    async def get_cheapest_offer(self, profile_name: str) -> dict | None:
        profile = GPU_PROFILES.get(profile_name)
        if not profile:
            raise ValueError(f"Unknown GPU profile: {profile_name}")

        try:
            offers = await asyncio.to_thread(
                self.vast.search_offers,
                query=profile["query"],
                order="dph",
                limit=10,
            )
        except Exception as e:
            log.error("gpu_manager.search_offers.failed", profile=profile_name,
                      error=str(e))
            return None

        if not offers:
            log.warning("gpu_manager.no_offers", profile=profile_name)
            return None

        offer_list = offers if isinstance(offers, list) else []
        if not offer_list:
            return None

        # Sort by cost, prefer interruptible for batch work
        cheapest = min(offer_list, key=lambda o: o.get("dph_total", float("inf")))
        log.info("gpu_manager.cheapest_offer", profile=profile_name,
                 offer_id=cheapest.get("id"), dph=cheapest.get("dph_total"),
                 gpu=cheapest.get("gpu_name"),
                 interruptible=cheapest.get("rentable", True))
        return cheapest

    # ── Cost tracking ─────────────────────────────────────────────────────────

    @property
    def session_cost(self) -> float:
        return round(self._session_cost, 4)

    def task_cost(self, task_id: str) -> float:
        return round(self._task_costs.get(task_id, 0.0), 4)

    async def store_costs_redis(self) -> None:
        """Persist cost data to Redis for failure journal integration."""
        try:
            import redis.asyncio as aioredis

            r = aioredis.Redis(unix_socket_path=os.environ.get("NCORE_REDIS_UDS", "/var/run/redis/redis-server.sock"))
            await r.hset("ncore:gpu:session_cost",
                         mapping={"total": str(self._session_cost)})
            for task_id, cost in self._task_costs.items():
                await r.hset("ncore:gpu:task_costs", task_id, str(cost))
            await r.close()
            log.info("gpu_manager.costs_stored", session=self.session_cost,
                     tasks=len(self._task_costs))
        except Exception as e:
            log.error("gpu_manager.costs_store_failed", error=str(e))
