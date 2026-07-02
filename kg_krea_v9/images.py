"""Reference-image preparation for the V9 stack encoder.

Turns a raw reference image into the tensor the vision encoder studies:
framing/resolution, color reduction, and the treatment washes (blurs,
palette wash, shape wash) that strip detail a card should not copy.
"""

import math

import torch

import comfy.utils


def blur_samples(samples, kernel_size):
    """Box-blur NCHW samples; sizes <= 1 pass through, evens round up to odd."""
    kernel_size = int(kernel_size)
    if kernel_size <= 1:
        return samples
    if kernel_size % 2 == 0:
        kernel_size += 1
    return torch.nn.functional.avg_pool2d(samples, kernel_size=kernel_size, stride=1, padding=kernel_size // 2)


def palette_wash_samples(samples):
    """Reduce an image to a blurred coarse color grid (palette-only signal)."""
    height = int(samples.shape[2])
    width = int(samples.shape[3])
    grid_h = min(10, max(2, height // 48))
    grid_w = min(10, max(2, width // 48))
    palette = torch.nn.functional.adaptive_avg_pool2d(samples, (grid_h, grid_w))
    palette = torch.nn.functional.interpolate(palette, size=(height, width), mode="nearest")
    average_color = samples.mean(dim=(2, 3), keepdim=True)
    palette = palette * 0.85 + average_color * 0.15
    return blur_samples(palette, 9)


def prepare_image(image, reference_resolution, reference_fit, reference_treatment, reference_detail, color_keep):
    """Resize, frame, and treat a reference image for the vision encoder.

    `reference_resolution` is the study side length; `reference_fit` chooses
    aspect handling; the treatment/color/detail settings progressively strip
    color and fine structure so only the card's intended signal survives.
    """
    samples = image.movedim(-1, 1)
    side = int(reference_resolution)

    if reference_fit == "center crop square":
        height_in = samples.shape[2]
        width_in = samples.shape[3]
        crop = min(height_in, width_in)
        top = (height_in - crop) // 2
        left = (width_in - crop) // 2
        samples = samples[:, :, top:top + crop, left:left + crop]
        width = side
        height = side
    elif reference_fit == "stretch square":
        width = side
        height = side
    else:
        total = int(side * side)
        scale_by = math.sqrt(total / (samples.shape[3] * samples.shape[2]))
        width = max(16, round(samples.shape[3] * scale_by))
        height = max(16, round(samples.shape[2] * scale_by))

    resized = comfy.utils.common_upscale(samples, width, height, "area", "disabled")
    treatment = reference_treatment

    if treatment in ("grayscale", "grayscale blur", "shape wash"):
        color_keep = 0.0

    color_keep = min(max(float(color_keep), 0.0), 1.0)
    if color_keep < 1.0:
        gray = resized.mean(dim=1, keepdim=True).repeat(1, 3, 1, 1)
        resized = gray * (1.0 - color_keep) + resized * color_keep

    if treatment == "soft blur":
        resized = blur_samples(resized, 5)
    elif treatment in ("strong blur", "grayscale blur"):
        resized = blur_samples(resized, 13)
    elif treatment == "palette wash":
        resized = palette_wash_samples(resized)
    elif treatment == "color wash":
        resized = blur_samples(resized, 31)
    elif treatment == "shape wash":
        gray = resized.mean(dim=1, keepdim=True).repeat(1, 3, 1, 1)
        resized = blur_samples(gray, 25)

    detail = min(max(float(reference_detail), 0.0), 1.0)
    if detail < 1.0:
        low_detail = blur_samples(resized, 17)
        resized = low_detail * (1.0 - detail) + resized * detail

    return resized.movedim(1, -1)[:, :, :, :3]
