"""Strict token, expanded-input and stripped-output coordinates for Krea 2.

This module contains no tokenizer or upstream model implementation. Coordinates
are verified against the host's actual process_tokens result before any muting.
"""
from dataclasses import dataclass
from numbers import Integral

TAPS = (2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35)
TAP_WIDTH = 2560
VISION_DEPTH = 3
TOKEN_KEY = 'qwen3vl_4b'
OWNER_KEY = 'kg_native_owner_v12'
# Exact newline-only carriers in the reviewed native Qwen vocabulary. The
# complete carrier stays in the opening; it is never split or skipped over.
_USER_OPENING_CARRIERS = frozenset((198, 271, 1406))


def element(item):
    return item[0] if isinstance(item, tuple) else item


def single_row(tokens):
    if not isinstance(tokens, dict) or list(tokens) != [TOKEN_KEY]:
        raise RuntimeError('V12 requires exactly one qwen3vl_4b token stream')
    rows = tokens[TOKEN_KEY]
    if len(rows) != 1:
        raise RuntimeError('V12 requires one untruncated token row')
    row = rows[0]
    for item in row:
        if isinstance(item, tuple) and (len(item) != 2 or item[1] != 1.0):
            raise RuntimeError('V12 requires unweighted tokens without word IDs')
        value = element(item)
        if isinstance(value, bool) or not isinstance(value, (Integral, dict)):
            raise RuntimeError('V12 encountered an unsupported token element')
        if isinstance(value, dict) and value.get('type') != 'image':
            raise RuntimeError('V12 cannot own non-image embedded tokens')
    return row


def same_token(left, right):
    left, right = element(left), element(right)
    if isinstance(left, dict) or isinstance(right, dict):
        return (isinstance(left, dict) and isinstance(right, dict)
                and left.get('type') == right.get('type') == 'image'
                and left.get('data') is right.get('data'))
    return left == right


def content_bounds(row):
    starts = [i for i, item in enumerate(row) if element(item) == 151644
              and not isinstance(element(item), dict)]
    if len(starts) != 3:
        raise RuntimeError('V12 requires system, user and assistant chat turns')
    start = starts[1]
    if (start + 3 > starts[2] or element(row[start + 1]) != 872
            or not isinstance(element(row[start + 2]), Integral)
            or element(row[start + 2]) not in _USER_OPENING_CARRIERS):
        raise RuntimeError('V12 cannot resolve the native user opening')
    start += 3
    ends = [i for i in range(start, starts[2])
            if not isinstance(element(row[i]), dict) and element(row[i]) == 151645]
    if len(ends) != 1:
        raise RuntimeError('V12 cannot resolve the native user content end')
    return start, ends[0]


def native_output_start(row):
    """Match native Krea stripping separately from the semantic content start."""
    start, _ = content_bounds(row)
    # The native encoder strips the opening only for the single-newline token.
    # With a merged newline carrier it retains im_start/user/carrier in output.
    return start if element(row[start - 1]) == 198 else start - 3


def _native_prompt_start(row, owners, content_start, content_end):
    """Consume complete native vision blocks; never skip prompt whitespace."""
    cursor = content_start
    for _ in owners:
        if (cursor + 3 > content_end or element(row[cursor]) != 151652
                or not isinstance(element(row[cursor + 1]), dict)
                or element(row[cursor + 2]) != 151653):
            raise RuntimeError('V12 requires complete native image blocks before the prompt')
        cursor += 3
    for item in row[cursor:content_end]:
        value = element(item)
        if isinstance(value, dict) or not 0 <= value < 151643:
            raise RuntimeError('V12 native image/prompt layout is ambiguous or contains unowned control/media tokens')
    return cursor


@dataclass(frozen=True)
class ExpandedLedger:
    token_offsets: tuple
    images: tuple
    prompt: tuple
    poles: tuple
    strip: int
    input_length: int

    @property
    def output_length(self):
        return self.input_length - self.strip

    def output_span(self, span):
        return span[0] - self.strip, span[1] - self.strip


@dataclass(frozen=True)
class TokenLedger:
    row: tuple
    owners: tuple
    prompt: tuple
    poles: tuple
    strip: int

    @classmethod
    def assemble(cls, original_tokens, owners, pole_tokens):
        """Own added token spans without retokenizing any native prompt prefix.

        Retain the original native row exactly. After complete image blocks,
        insert separately tokenized literal payloads before every prompt token.
        Trailing delimiters are explicitly owned newline tokens, avoiding both
        native BPE boundary merges and causal isolation behind the prompt.
        This assembles tokens before encoding, never completed conditionings.
        """
        original = cls.build(original_tokens, owners)
        if not isinstance(pole_tokens, (list, tuple)) or not 1 <= len(pole_tokens) <= 16:
            raise ValueError('V12 requires one through sixteen native pole payload rows')
        content_start, content_end = content_bounds(original.row)
        insertion = original.prompt[0]
        additions, spans = [], []
        for tokens in pole_tokens:
            row = single_row(tokens)
            start, end = content_bounds(row)
            payload = row[start:end]
            if (element(row[start - 1]) != 198 or not payload
                    or any(isinstance(element(item), dict) for item in row)
                    or any(not 0 <= element(item) < 151643 for item in payload)):
                raise RuntimeError('V12 pole payload must be nonempty plain text without native control/media tokens')
            begin = insertion + len(additions)
            # Qwen newline198 is also verified in the native user-opening row.
            # Both separators and payload are owned/muted/projected as one span.
            additions.extend(payload)
            additions.extend(((198, 1.0), (198, 1.0)))
            spans.append((begin, insertion + len(additions)))
        row = original.row[:insertion] + tuple(additions) + original.row[insertion:]
        if content_bounds(row) != (content_start, content_end + len(additions)):
            raise RuntimeError('V12 pole assembly changed native template ownership')
        retained = tuple(item for index, item in enumerate(row)
                         if not any(start <= index < end for start, end in spans))
        if (len(retained) != len(original.row)
                or any(item is not native_item for item, native_item in zip(retained, original.row))):
            raise RuntimeError('V12 removing owned pole spans did not recover the exact native row')
        prompt = (insertion + len(additions), original.prompt[1] + len(additions))
        return cls(row, original.owners, prompt, tuple(spans), original.strip)

    @classmethod
    def build(cls, tokens, owners, ladder=()):
        row = single_row(tokens)
        content_start, content_end = content_bounds(row)
        image_positions = [i for i, item in enumerate(row) if isinstance(element(item), dict)]
        if len(image_positions) != len(owners) or len(set(owners)) != len(owners):
            raise RuntimeError('V12 requires a unique owner for every image')
        if any(not content_start <= i < content_end for i in image_positions):
            raise RuntimeError('V12 images must follow the stripped user opening')
        prompt_start = _native_prompt_start(row, owners, content_start, content_end)
        boundaries = []
        for prefix_tokens in ladder:
            prefix = single_row(prefix_tokens)
            prefix_start, prefix_end = content_bounds(prefix)
            if prefix_start != content_start or prefix_end >= content_end:
                raise RuntimeError('V12 pole ladder was truncated or changed template')
            if not all(same_token(a, b) for a, b in zip(prefix[:prefix_end], row[:prefix_end])):
                raise RuntimeError('V12 pole boundary merged into existing native content')
            boundaries.append(prefix_end)
        if boundaries != sorted(set(boundaries)):
            raise RuntimeError('V12 pole spans overlap or are empty')
        poles = tuple(zip(boundaries, boundaries[1:] + [content_end]))
        prompt_end = boundaries[0] if boundaries else content_end
        if prompt_end < prompt_start:
            raise RuntimeError('V12 pole boundary overlaps a native image')
        return cls(tuple(row), tuple(owners), (prompt_start, prompt_end), poles, native_output_start(row))

    def tagged_tokens(self):
        row = []
        owners = iter(self.owners)
        for item in self.row:
            value = element(item)
            if isinstance(value, dict):
                if OWNER_KEY in value:
                    raise RuntimeError('V12 cannot replace an existing image owner tag')
                value = {**value, OWNER_KEY: next(owners)}
            row.append((value, 1.0))
        return {TOKEN_KEY: [row]}

    def native_output_positions(self, original_tokens, expanded):
        """Project one study's output onto its original owned native positions.

        Only the contiguous owned pole interval is removed. The original sequence,
        including image identity/order and assistant suffix, must match exactly.
        This never joins independently encoded sequences or invents padding.
        """
        original = single_row(original_tokens)
        if not self.poles:
            raise RuntimeError('V12 native projection requires owned pole positions')
        start, end = self.poles[0][0], self.poles[-1][1]
        retained = self.row[:start] + self.row[end:]
        if len(retained) != len(original) or not all(same_token(a, b) for a, b in zip(retained, original)):
            raise RuntimeError('V12 cannot project studies onto the original native token sequence')
        output_start = expanded.token_offsets[start] - expanded.strip
        output_end = expanded.token_offsets[end] - expanded.strip
        if not 0 <= output_start < output_end <= expanded.output_length:
            raise RuntimeError('V12 owned pole output interval is invalid')
        return tuple(i for i in range(expanded.output_length) if not output_start <= i < output_end)

    def expand(self, process_rows, embeds_info, input_length):
        if len(process_rows) != 1 or len(process_rows[0]) != len(self.row):
            raise RuntimeError('V12 host changed token rows during preparation')
        if not all(same_token(a, b) for a, b in zip(process_rows[0], self.row)):
            raise RuntimeError('V12 host changed token content during preparation')
        images = sorted(embeds_info, key=lambda entry: entry.get('index', -1))
        if len(images) != len(self.owners):
            raise RuntimeError('V12 host dropped or added embedded images')
        offsets, spans, cursor, image_index = [0], [], 0, 0
        for item in self.row:
            if isinstance(element(item), dict):
                info = images[image_index]
                size = info.get('size')
                if (info.get('type') != 'image' or info.get('index') != cursor
                        or isinstance(size, bool) or not isinstance(size, Integral) or size <= 0):
                    raise RuntimeError('V12 image expansion index/size mismatch')
                extra = info.get('extra')
                if (not isinstance(extra, dict) or extra.get('grid') is None
                        or not isinstance(extra.get('deepstack'), (list, tuple))
                        or len(extra['deepstack']) != VISION_DEPTH):
                    raise RuntimeError('V12 requires the three native vision deepstack injections')
                spans.append((self.owners[image_index], cursor, cursor + size))
                cursor += size
                image_index += 1
            else:
                cursor += 1
            offsets.append(cursor)
        if cursor != input_length:
            raise RuntimeError('V12 expanded extent differs from the actual input embeddings')
        def mapped(span):
            return offsets[span[0]], offsets[span[1]]
        return ExpandedLedger(tuple(offsets), tuple(spans), mapped(self.prompt),
                              tuple(mapped(span) for span in self.poles), offsets[self.strip], cursor)
