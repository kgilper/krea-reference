"""Prepared-reference contact sheet for the V10 stack encoder.

The treatments (washes, blurs, color and detail reduction) are the node's
guaranteed information filter, but in V9 they were invisible. The V10 stack
outputs exactly what the vision encoder studies, one frame per card, padded
onto a shared canvas so a single Preview Image node shows the whole stack.
"""

import torch

# Dark gray padding distinguishes canvas from genuinely black image content.
PAD_VALUE = 0.15


def contact_sheet(prepared_images):
    """Stack prepared reference frames onto one shared-size IMAGE batch.

    `prepared_images` are the encoder's post-treatment tensors, shaped
    [B, H, W, C]; the first frame of each is used. Returns [N, Hmax, Wmax, 3]
    with each frame centered on a padded canvas, or a small blank frame when
    no references are active (so downstream previews never crash).
    """
    frames = []
    for image in prepared_images:
        if torch.is_tensor(image) and image.dim() == 4 and image.shape[0] >= 1:
            frames.append(image[0, :, :, :3])

    if not frames:
        return torch.zeros((1, 8, 8, 3))

    max_height = max(int(frame.shape[0]) for frame in frames)
    max_width = max(int(frame.shape[1]) for frame in frames)

    canvas = torch.full(
        (len(frames), max_height, max_width, 3),
        PAD_VALUE,
        dtype=frames[0].dtype,
        device=frames[0].device,
    )
    for i, frame in enumerate(frames):
        height = int(frame.shape[0])
        width = int(frame.shape[1])
        top = (max_height - height) // 2
        left = (max_width - width) // 2
        canvas[i, top:top + height, left:left + width] = frame.to(canvas.dtype)
    return canvas
