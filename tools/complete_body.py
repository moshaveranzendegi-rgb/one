#!/usr/bin/env python3
"""Optional WSL2 inpainting stage for extending a cropped portrait to a full-body frame.

It is an estimate of unseen body/clothing, not a guarantee of the person's actual physique.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        import torch
        from diffusers import StableDiffusionInpaintPipeline
    except Exception as exc:
        raise SystemExit(f"Missing inpainting dependencies; run tools/setup_body_wsl.sh first: {exc}")
    with Image.open(args.input) as source:
        src = ImageOps.exif_transpose(source).convert("RGB")
    canvas_w, canvas_h = 512, 896
    scale = canvas_w / max(1, src.width)
    resized = src.resize((canvas_w, max(1, round(src.height * scale))), Image.Resampling.LANCZOS)
    if resized.height > 640:
        scale = 640 / resized.height
        resized = resized.resize((max(1, round(resized.width * scale)), 640), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (224, 224, 224))
    x = (canvas_w - resized.width) // 2
    canvas.paste(resized, (x, 0))
    mask = Image.new("L", (canvas_w, canvas_h), 255)
    keep_until = max(240, min(455, int(resized.height * 0.64)))
    ImageDraw.Draw(mask).rectangle((0, 0, canvas_w, keep_until), fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(8))
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = StableDiffusionInpaintPipeline.from_pretrained(
        "/opt/rs-ai-body-model", torch_dtype=dtype, safety_checker=None, local_files_only=True
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    if device == "cuda":
        model.enable_attention_slicing()
    prompt = (
        "photorealistic full body photo of the same adult person, natural human anatomy, "
        "complete torso, both arms, hands, legs and feet, realistic proportions, continue the existing clothing "
        "and colors consistently, neutral standing pose, studio-quality natural lighting, no text, no logo"
    )
    negative = "extra arms, extra fingers, missing legs, deformed hands, different face, text, watermark, cartoon"
    result = model(prompt=prompt, negative_prompt=negative, image=canvas, mask_image=mask, num_inference_steps=28, guidance_scale=6.0).images[0]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output)
    print(output)


if __name__ == "__main__":
    main()
