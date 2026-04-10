"""cotodo parser — parse TODO.md into structured state.

Reads a TODO.md file and extracts:
- Global PAUSE state
- Topics with their markers (over, [processing], [pending], @delete)
- Context text for each topic (up to the active marker)
"""

import os
import re
import tempfile
from typing import Optional

# Marker patterns
RE_OVER = re.compile(r'over\s*$', re.IGNORECASE)
RE_PROCESSING = re.compile(r'\[processing\]\s*$')
RE_PENDING = re.compile(r'\[pending\]\s*$')
RE_DELETE = re.compile(r'@delete\s*$')
RE_HEADING = re.compile(r'^##\s+(.+)$')
RE_PAUSE = re.compile(r'^PAUSE:\s*(.*)$')
RE_CODE_FENCE = re.compile(r'^```')
RE_TABLE_ROW = re.compile(r'^\s*\|.*\|\s*$')


def _strip_inline_code(line: str) -> str:
    """Remove inline code spans so markers inside backticks are ignored."""
    return re.sub(r'`[^`]+`', '', line)


def _extract_context(lines: list, heading_line: int, marker_line: Optional[int]) -> Optional[str]:
    """Extract context text from first non-blank line after heading to marker line.

    Args:
        lines: All file lines (0-indexed list of strings with newlines).
        heading_line: 1-based line number of ## heading.
        marker_line: 1-based line number of the active marker, or None.

    Returns:
        Context string or None if no marker.
    """
    if marker_line is None:
        return None

    # Find first non-blank line after heading (heading_line is 1-based, so index = heading_line)
    start_idx = heading_line  # 0-indexed position right after the heading line
    while start_idx < len(lines) and lines[start_idx].strip() == '':
        start_idx += 1

    # Extract from start to marker line (inclusive; marker_line is 1-based)
    end_idx = marker_line  # lines[marker_line - 1] is the marker line, so [:marker_line] includes it
    context_lines = list(lines[start_idx:end_idx])

    # Strip marker text from the last line
    if context_lines:
        last = context_lines[-1]
        for pat in [RE_PROCESSING, RE_OVER, RE_PENDING]:
            last = pat.sub('', last)
        context_lines[-1] = last

    context = ''.join(context_lines).rstrip('\n').rstrip()
    return context if context else None


def _atomic_remove(filepath: str, lines: list, delete_topics: list) -> None:
    """Remove @delete topic sections from file atomically.

    Uses write-to-temp + os.replace() for atomic update.
    """
    remove = set()
    for t in delete_topics:
        for i in range(t['line'] - 1, t['end']):  # line is 1-based, convert to 0-based
            remove.add(i)
    new_lines = [l for i, l in enumerate(lines) if i not in remove]

    dir_name = os.path.dirname(os.path.abspath(filepath))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        os.replace(tmp_path, filepath)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _pick_highest(filepath: str, paused: bool, topics: list) -> dict:
    """Select the highest priority topic and return marker-based output.

    Priority: pause > processing > over > pending > idle.
    """
    if paused:
        return {"file": filepath, "marker": "pause"}

    # Priority 1: processing
    for t in topics:
        if t['processing'] is not None:
            return {
                "file": filepath,
                "marker": "processing",
                "topic": _format_topic(t),
            }

    # Priority 2: over
    over_topics = [t for t in topics if t['over'] is not None]
    if over_topics:
        return {
            "file": filepath,
            "marker": "over",
            "topic": _format_topic(over_topics[0]),
            "queue_depth": len(over_topics),
        }

    # Priority 3: pending
    for t in topics:
        if t['pending'] is not None:
            return {
                "file": filepath,
                "marker": "pending",
                "topic": _format_topic(t),
            }

    return {"file": filepath, "marker": "idle"}


def _format_topic(t: dict) -> dict:
    """Format a topic for marker-based output (single topic mode)."""
    marker_line = t['processing'] or t['over'] or t['pending']
    return {
        "title": t['title'],
        "line": t['line'],
        "end": t['end'],
        "marker_line": marker_line,
        "context": t['context'],
    }


def scan(filepath: str = 'TODO.md', clean: bool = False, all_topics: bool = False) -> dict:
    """Parse TODO.md and return structured state as a dict.

    Args:
        filepath: Path to TODO.md file.
        clean: If True, delete @delete topics from file before returning.
        all_topics: If True, return all topics. If False, return highest priority topic.

    Markers are normalized:
    - over: only the last occurrence per topic (canonical)
    - processing/pending: only the last occurrence per topic
    - context: text from first non-blank line after heading to active marker

    Context marker priority: processing > over > pending.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {"file": filepath, "paused": False, "topics": [], "error": "file not found"}

    paused = False
    raw_topics: list[dict] = []
    current_topic = None
    in_code_block = False

    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip('\n\r')

        # Track code block state
        if RE_CODE_FENCE.match(line):
            in_code_block = not in_code_block
            continue

        # Skip content inside code blocks
        if in_code_block:
            continue

        # Check PAUSE: (only in header area, before first topic)
        if current_topic is None:
            pause_match = RE_PAUSE.match(line)
            if pause_match:
                value = pause_match.group(1).strip()
                paused = len(value) > 0
                continue

        # Check for ## heading
        heading_match = RE_HEADING.match(line)
        if heading_match:
            # Close previous topic
            if current_topic is not None:
                current_topic['end'] = i - 1
                raw_topics.append(current_topic)

            title_raw = heading_match.group(1).strip()
            has_delete = bool(RE_DELETE.search(title_raw))
            title = RE_DELETE.sub('', title_raw).strip() if has_delete else title_raw

            current_topic = {
                'title': title,
                'line': i,
                'end': i,
                'delete': has_delete,
                '_over_all': [],
                '_processing_all': [],
                '_pending_all': [],
            }
            continue

        # Only detect markers within a topic
        if current_topic is None:
            continue

        # Skip table rows
        if RE_TABLE_ROW.match(line):
            continue

        # Strip inline code before checking markers
        check_line = _strip_inline_code(line)

        if RE_OVER.search(check_line):
            current_topic['_over_all'].append(i)
        if RE_PROCESSING.search(check_line):
            current_topic['_processing_all'].append(i)
        if RE_PENDING.search(check_line):
            current_topic['_pending_all'].append(i)

    # Close last topic
    if current_topic is not None:
        current_topic['end'] = len(lines)
        raw_topics.append(current_topic)

    # Post-process: normalize markers and extract context
    topics = []
    for t in raw_topics:
        over_raw = t['_over_all'][-1] if t['_over_all'] else None
        processing_raw = t['_processing_all'][-1] if t['_processing_all'] else None
        pending_raw = t['_pending_all'][-1] if t['_pending_all'] else None

        # Priority: processing > over > pending — higher masks lower
        if processing_raw is not None:
            processing = processing_raw
            over = None
            pending = None
        elif over_raw is not None:
            processing = None
            over = over_raw
            pending = None
        else:
            processing = None
            over = None
            pending = pending_raw

        # Context marker priority follows the same masking
        marker_line = None
        if not t['delete']:
            marker_line = processing or over or pending

        topics.append({
            'title': t['title'],
            'line': t['line'],
            'end': t['end'],
            'delete': t['delete'],
            'over': over,
            'processing': processing,
            'pending': pending,
            'context': _extract_context(lines, t['line'], marker_line),
        })

    # --clean: delete @delete topics from file
    if clean:
        delete_topics = [t for t in topics if t['delete']]
        if delete_topics:
            _atomic_remove(filepath, lines, delete_topics)
            topics = [t for t in topics if not t['delete']]

    # --all: return full topic list
    if all_topics:
        return {
            'file': filepath,
            'paused': paused,
            'topics': topics,
        }

    # Default: return highest priority action
    return _pick_highest(filepath, paused, topics)
