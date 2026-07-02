"""Token-row analysis for the Krea (Qwen2.5-VL) chat template.

The stack encoder needs to know, inside the tokenized chat template, where
the reference-image embeds sit and where the user's written prompt starts and
ends, so it can mute or rescale each piece independently. Token rows arrive
as lists whose items are either token ids (possibly wrapped in tuples with
weights) or image-embed dicts.
"""

import numbers

# Qwen2.5-VL special/structural token ids the template analysis keys on.
IM_START_TOKEN = 151644  # <|im_start|>
IM_END_TOKEN = 151645  # <|im_end|>
VISION_END_TOKEN = 151653  # <|vision_end|>
USER_ROLE_TOKEN = 872  # "user"
NEWLINE_TOKEN = 198  # "\n"
DOUBLE_NEWLINE_TOKEN = 271  # "\n\n"


def token_elem(item):
    """Unwrap a token row item to its element (id or image dict)."""
    if isinstance(item, tuple):
        return item[0]
    return item


def tag_image_references(tokens):
    """Stamp each image embed with its 0-based reference index, in place.

    The scaled-embedding hook uses the index to apply per-card strengths.
    """
    key_name = next(iter(tokens))
    for row in tokens[key_name]:
        image_index = 0
        for i in range(len(row)):
            item = row[i]
            elem = token_elem(item)
            if isinstance(elem, dict) and elem.get("type") == "image":
                tagged = elem.copy()
                tagged["kg_reference_index"] = image_index
                if isinstance(item, tuple):
                    row[i] = (tagged,) + item[1:]
                else:
                    row[i] = tagged
                image_index += 1


def krea_user_content_start(row):
    """Return the index where the user message content begins.

    Finds the second <|im_start|> (system, then user) and skips the
    "user\\n" role header when present.
    """
    start = 0
    count_im_start = 0
    for i, item in enumerate(row):
        elem = token_elem(item)
        if isinstance(elem, numbers.Integral) and int(elem) == IM_START_TOKEN and count_im_start < 2:
            start = i
            count_im_start += 1

    if len(row) > start + 3:
        role = token_elem(row[start + 1])
        newline = token_elem(row[start + 2])
        if isinstance(role, numbers.Integral) and isinstance(newline, numbers.Integral):
            if int(role) == USER_ROLE_TOKEN and int(newline) == NEWLINE_TOKEN:
                start += 3

    return start


def find_prompt_bounds(row, image_count):
    """Return (user content start, prompt start, prompt end) token indices.

    The written prompt starts after the last image embed (skipping the
    vision-end and newline tokens that follow it) and ends at <|im_end|>.
    """
    output_start = krea_user_content_start(row)
    prompt_start = output_start

    if image_count > 0:
        seen_images = 0
        for i in range(output_start, len(row)):
            elem = token_elem(row[i])
            if isinstance(elem, dict) and elem.get("type") == "image":
                seen_images += 1
                if seen_images == image_count:
                    prompt_start = i + 1
                    break

        while prompt_start < len(row):
            elem = token_elem(row[prompt_start])
            if not isinstance(elem, numbers.Integral):
                break
            token_id = int(elem)
            if token_id == VISION_END_TOKEN or token_id in (NEWLINE_TOKEN, DOUBLE_NEWLINE_TOKEN):
                prompt_start += 1
                continue
            break

    prompt_end = len(row)
    for i in range(prompt_start, len(row)):
        elem = token_elem(row[i])
        if isinstance(elem, numbers.Integral) and int(elem) == IM_END_TOKEN:
            prompt_end = i
            break

    return output_start, prompt_start, prompt_end


def expanded_offset(row, start, end, image_embedding_sizes):
    """Convert a token-index span into an embedding-position offset.

    Each image embed expands to its embedding size; every other item
    occupies one position.
    """
    offset = 0
    image_index = 0
    for item in row[start:end]:
        elem = token_elem(item)
        if isinstance(elem, dict) and elem.get("type") == "image":
            if image_index < len(image_embedding_sizes):
                offset += image_embedding_sizes[image_index]
            else:
                offset += 1
            image_index += 1
        else:
            offset += 1
    return offset


def prompt_input_embedding_bounds(token_rows, image_embedding_sizes, image_count):
    """Return the written prompt's (start, end) in embedding positions."""
    row = token_rows[0]
    output_start, prompt_start, prompt_end = find_prompt_bounds(row, image_count)
    start = expanded_offset(row, 0, prompt_start, image_embedding_sizes)
    end = expanded_offset(row, 0, prompt_end, image_embedding_sizes)
    return start, end


def image_embedding_sizes(embeds_info):
    """Extract per-image embedding sizes from encoder embed info, in order."""
    images = [e for e in embeds_info if e.get("type") == "image"]
    images.sort(key=lambda e: e["index"])
    return [int(e["size"]) for e in images]
