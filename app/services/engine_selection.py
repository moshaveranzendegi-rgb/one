from __future__ import annotations


def select_avatar_engine(omniavatar_gpu_ready: bool, sadtalker_cpu_ready: bool) -> str | None:
    """Prefer full-motion GPU mode when available; otherwise use CPU talking-head mode."""
    if omniavatar_gpu_ready:
        return "omniavatar"
    if sadtalker_cpu_ready:
        return "sadtalker_cpu"
    return None
