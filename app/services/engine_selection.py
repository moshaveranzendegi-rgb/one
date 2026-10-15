from __future__ import annotations


def select_avatar_engine(omniavatar_gpu_ready: bool, sadtalker_cpu_ready: bool) -> str | None:
    """Prefer full-motion GPU mode when available; otherwise use CPU talking-head mode."""
    if omniavatar_gpu_ready:
        return "omniavatar"
    if sadtalker_cpu_ready:
        return "sadtalker_cpu"
    return None


def resolve_engine_mode(requested_mode: str | None, detected_engine: str | None) -> str:
    """Resolve the UI request without silently sending local jobs to a cloud workflow."""
    mode = (requested_mode or "auto").strip().lower()

    if mode == "cloud":
        # Cloud mode is opt-in only; it packages files for manual transfer.
        return "cloud"

    if mode == "cpu":
        if detected_engine == "sadtalker_cpu":
            return "sadtalker_cpu"
        raise RuntimeError(
            "موتور SadTalker CPU آماده نیست. ابتدا نصب محلی موتور CPU را کامل کن."
        )

    if mode in {"auto", "local"}:
        if detected_engine in {"omniavatar", "sadtalker_cpu"}:
            return detected_engine
        raise RuntimeError(
            "هیچ موتور محلی آماده نیست. برای این رایانه، SadTalker CPU را نصب و "
            "در بخش «وضعیت موتور‌ها» بررسی کن. پروژه به GPU ابری فرستاده نمی‌شود."
        )

    raise RuntimeError("حالت انتخاب‌شده برای موتور آواتار شناخته‌شده نیست.")

