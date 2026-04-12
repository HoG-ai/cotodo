"""cotodo parser — parse TODO.md into structured state.

Reads a TODO.md file and extracts:
- Global PAUSE state
- Topics with their markers (over, [processing], [pending], @delete)
- Context text for each topic (up to the active marker)
- Summary section content (> **Summary** blockquote)
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
RE_CID = re.compile(r'\s*<!--\s*cid:([0-9a-f]{8})\s*-->\s*$')
RE_PAUSE = re.compile(r'^PAUSE:\s*(.*)$')
RE_CODE_FENCE = re.compile(r'^```')
RE_TABLE_ROW = re.compile(r'^\s*\|.*\|\s*$')
RE_SUMMARY_START = re.compile(r'^>\s*\*\*Summary\*\*\s*(\[(?:pending|processing)\])?\s*$')


def _gen_cid() -> str:
    """Generate a random 8-char hex topic ID."""
    return os.urandom(4).hex()


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


def _extract_summary(lines: list, topic_start: int, topic_end: int) -> Optional[str]:
    """Extract Summary section content from a topic.

    Looks for a line matching `> **Summary** [marker]?` within the topic,
    then collects subsequent `>` lines as the summary body.

    Args:
        lines: All file lines (0-indexed list of strings with newlines).
        topic_start: 1-based line number of ## heading.
        topic_end: 1-based last line of the topic section.

    Returns:
        Summary content string (without `>` prefixes) or None if no Summary section.
    """
    for i in range(topic_start, topic_end):  # 0-indexed: topic_start is line after heading
        line = lines[i].rstrip('\n\r')
        if RE_SUMMARY_START.match(line):
            body_lines = []
            for j in range(i + 1, topic_end):
                bline = lines[j].rstrip('\n\r')
                if bline.startswith('>'):
                    # Strip leading '>' and optional one space
                    content = bline[1:]
                    if content.startswith(' '):
                        content = content[1:]
                    body_lines.append(content)
                else:
                    break
            body = '\n'.join(body_lines).strip()
            return body if body else None
    return None


def _atomic_remove(filepath: str, lines: list, delete_topics: list) -> None:
    """Remove @delete topic sections from file atomically."""
    remove = set()
    for t in delete_topics:
        for i in range(t['line'] - 1, t['end']):  # line is 1-based, convert to 0-based
            remove.add(i)
    new_lines = [l for i, l in enumerate(lines) if i not in remove]
    _atomic_write(filepath, new_lines)


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
    return {
        "id": t['id'],
        "title": t['title'],
        "context": t['context'],
        "summary": t.get('summary'),
    }


def _atomic_write(filepath: str, lines: list) -> None:
    """Write lines to file atomically via temp file + os.replace()."""
    dir_name = os.path.dirname(os.path.abspath(filepath))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _normalize_format(filepath: str, lines: list) -> None:
    """Normalize formatting: collapse blank lines, deduplicate User:, add User: prefix."""
    changed = False
    result = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ''
        if is_blank and prev_blank:
            changed = True
            continue  # skip consecutive blank lines
        result.append(line)
        prev_blank = is_blank

    # Deduplicate consecutive "User:" lines (keep last)
    deduped = []
    i = 0
    while i < len(result):
        if re.match(r'^User:\s*$', result[i]):
            j = i + 1
            while j < len(result):
                stripped = result[j].strip()
                if stripped == '' or re.match(r'^User:\s*$', stripped):
                    j += 1
                else:
                    break
            if j - i > 1:
                changed = True
            deduped.append('User: \n')
            i = j
        else:
            deduped.append(result[i])
            i += 1

    # Auto-add "User: " prefix to first content line after ## heading
    final = deduped
    for idx in range(len(final)):
        if RE_HEADING.match(final[idx].rstrip('\n\r')):
            # Find first non-blank content line after heading
            for j in range(idx + 1, len(final)):
                stripped = final[j].strip()
                if stripped == '':
                    continue
                if RE_HEADING.match(stripped):
                    break  # next topic, no content
                # Check if it already has User:/Agent: prefix or is a marker/comment
                if (stripped.startswith('User:') or stripped.startswith('Agent:')
                        or stripped.startswith('>') or stripped.startswith('<!--')
                        or stripped.startswith('PAUSE:')):
                    break
                # First content line without prefix — add User:
                final[j] = f'User: {stripped}\n'
                changed = True
                break

    if changed:
        _atomic_write(filepath, final)


def scan(filepath: str = 'TODO.md', clean: bool = False, all_topics: bool = False,
         take: bool = False) -> dict:
    """Parse TODO.md and return structured state as a dict.

    Args:
        filepath: Path to TODO.md file.
        clean: If True, delete @delete topics from file before returning.
        all_topics: If True, return all topics. If False, return highest priority topic.
        take: If True, atomically mark the highest priority topic as [processing].

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
            # Extract cid if present: <!-- cid:xxxxxxxx -->
            cid_match = RE_CID.search(title_raw)
            cid = cid_match.group(1) if cid_match else None
            if cid_match:
                title_raw = title_raw[:cid_match.start()].strip()
            has_delete = bool(RE_DELETE.search(title_raw))
            title = RE_DELETE.sub('', title_raw).strip() if has_delete else title_raw

            current_topic = {
                'title': title,
                'cid': cid,
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
    # Auto-assign cids to topics that don't have one
    needs_cid_write = False
    topics = []
    for t in raw_topics:
        cid = t['cid']
        if cid is None and not t['delete']:
            cid = _gen_cid()
            # Inject cid into heading line (t['line'] is 1-based)
            h_idx = t['line'] - 1
            h_line = lines[h_idx].rstrip('\n')
            lines[h_idx] = f"{h_line} <!-- cid:{cid} -->\n"
            needs_cid_write = True

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
            'id': cid,
            'title': t['title'],
            'line': t['line'],
            'end': t['end'],
            'delete': t['delete'],
            'over': over,
            'processing': processing,
            'pending': pending,
            'context': _extract_context(lines, t['line'], marker_line),
            'summary': _extract_summary(lines, t['line'], t['end']),
        })

    # Write back auto-assigned cids
    if needs_cid_write:
        _atomic_write(filepath, lines)

    # --clean: delete @delete topics and normalize formatting
    if clean:
        delete_topics = [t for t in topics if t['delete']]
        if delete_topics:
            _atomic_remove(filepath, lines, delete_topics)
            topics = [t for t in topics if not t['delete']]
        # Re-read file for normalization (file may have been modified by _atomic_remove or cid write)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                current_lines = f.readlines()
            _normalize_format(filepath, current_lines)
        except FileNotFoundError:
            pass

    # --take: atomically mark the highest priority topic as [processing]
    if take:
        result = _pick_highest(filepath, paused, topics)
        if result['marker'] in ('over', 'pending'):
            topic = result['topic']
            # Find the raw topic data by id
            target_topic = None
            for t in topics:
                if t['id'] == topic['id']:
                    target_topic = t
                    break
            if target_topic:
                ml = target_topic['over'] or target_topic['pending']
                if ml:
                    idx = ml - 1  # 0-based
                    old_line = lines[idx].rstrip('\n')
                    # Remove existing markers, then add [processing]
                    new_line = RE_OVER.sub('', old_line).rstrip()
                    new_line = RE_PENDING.sub('', new_line).rstrip()
                    new_line = new_line + ' [processing]\n'
                    lines[idx] = new_line
                    _atomic_write(filepath, lines)
                    # Update result to reflect new state
                    result['marker'] = 'processing'
        return result

    # --all: return full topic list
    if all_topics:
        return {
            'file': filepath,
            'paused': paused,
            'topics': topics,
        }

    # Default: return highest priority action
    return _pick_highest(filepath, paused, topics)


def _find_summary_range(lines: list, start: int, end: int):
    """Find the Summary blockquote range within lines[start:end] (0-based).

    Returns (header_idx, body_end_idx) or None.
    header_idx: index of `> **Summary**` line
    body_end_idx: exclusive end (first non-`>` line after header)
    """
    for i in range(start, end):
        line = lines[i].rstrip('\n\r')
        if RE_SUMMARY_START.match(line):
            j = i + 1
            while j < end and lines[j].rstrip('\n\r').startswith('>'):
                j += 1
            return (i, j)
    return None


def _find_topic_bounds(lines: list, topic_id: str):
    """Find a topic by cid. Returns (heading_idx, end_idx) as 0-based indices.

    heading_idx: the `##` heading line (0-based)
    end_idx: exclusive end (next heading or EOF)
    Returns None if topic_id not found.
    """
    in_code = False
    found_idx = None
    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip('\n\r')
        if RE_CODE_FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        heading_match = RE_HEADING.match(line)
        if heading_match:
            if found_idx is not None:
                return (found_idx, i)
            cid_match = RE_CID.search(heading_match.group(1))
            if cid_match and cid_match.group(1) == topic_id:
                found_idx = i
    if found_idx is not None:
        return (found_idx, len(lines))
    return None


def reply(filepath: str, topic_id: str, context: str = None,
          summary: str = None, pending: bool = False,
          compress: bool = False) -> dict:
    """Reply to a topic: append conversation, update Summary, manage markers.

    Args:
        filepath: Path to TODO.md file.
        topic_id: Persistent 8-char hex cid (from scan output).
        context: Agent reply text to append (or full conversation if compress=True).
        summary: Summary content to write (overwrites existing). None = no change.
        pending: If True, mark topic as [pending] (has plan, not executing yet).
        compress: If True, context replaces entire conversation area.

    Returns:
        dict with operation result.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {"ok": False, "error": "file not found"}

    bounds = _find_topic_bounds(lines, topic_id)
    if bounds is None:
        return {"ok": False, "error": f"topic not found: id={topic_id}"}

    h_idx, t_end = bounds  # 0-based heading index, exclusive end

    # Extract topic lines as a separate list for easier manipulation
    heading_line = lines[h_idx]
    body = list(lines[h_idx + 1: t_end])

    # --- Step 1: strip all markers from body ---
    in_code = False
    cleaned_body = []
    for bline in body:
        raw = bline.rstrip('\n\r')
        if RE_CODE_FENCE.match(raw):
            in_code = not in_code
            cleaned_body.append(bline)
            continue
        if in_code:
            cleaned_body.append(bline)
            continue
        if RE_TABLE_ROW.match(raw):
            cleaned_body.append(bline)
            continue

        check = _strip_inline_code(raw)
        modified = raw
        # Remove markers progressively — order matters because
        # e.g. "over [processing]" has over NOT at end until [processing] is removed
        for pat in [RE_PROCESSING, RE_PENDING, RE_OVER]:
            check_modified = _strip_inline_code(modified)
            if pat.search(check_modified):
                modified = pat.sub('', modified).rstrip()

        # Check if this is a Summary header — preserve but strip marker
        if RE_SUMMARY_START.match(raw):
            cleaned_body.append('> **Summary**\n')
            continue

        if modified != raw:
            if modified.strip() == '':
                # Line became empty after marker removal — skip it
                continue
            cleaned_body.append(modified + '\n')
        else:
            cleaned_body.append(bline)
    body = cleaned_body

    # --- Step 2: Split body into conversation + summary ---
    summary_start = None
    summary_end = None
    for i, bline in enumerate(body):
        if RE_SUMMARY_START.match(bline.rstrip('\n\r')):
            summary_start = i
            summary_end = i + 1
            while summary_end < len(body) and body[summary_end].rstrip('\n\r').startswith('>'):
                summary_end += 1
            break

    if summary_start is not None:
        conv_lines = body[:summary_start]
        old_summary_lines = body[summary_start:summary_end]
        after_summary = body[summary_end:]
    else:
        conv_lines = body[:]
        old_summary_lines = []
        after_summary = []

    # Merge after_summary (User messages after Summary) into conversation
    if after_summary:
        conv_lines.extend(after_summary)
        after_summary = []

    # --- Step 3: Handle context ---
    if compress and context is not None:
        # Replace entire conversation
        conv_lines = ['\n', context.rstrip('\n') + '\n']
    elif context is not None:
        # Append Agent reply — add "Agent: " prefix if not already present
        text = context.rstrip()
        if not text.startswith('Agent:'):
            text = f'Agent: {text}'
        conv_lines.append(f'\n{text}\n')

    # --- Step 4: Handle summary ---
    if summary is not None:
        marker_suffix = ' [pending]' if pending else ''
        new_summary_lines = [f'\n> **Summary**{marker_suffix}\n']
        for sline in summary.split('\n'):
            new_summary_lines.append(f'> {sline}\n')
    elif pending and old_summary_lines:
        # Update existing summary header with [pending]
        new_summary_lines = ['\n> **Summary** [pending]\n'] + old_summary_lines[1:]
        if not new_summary_lines[-1].endswith('\n'):
            new_summary_lines[-1] += '\n'
    elif old_summary_lines:
        # Preserve existing summary as-is (header already cleaned)
        new_summary_lines = ['\n'] + old_summary_lines
    else:
        new_summary_lines = []

    # --- Step 5: Add User: prompt ---
    has_following = bool(lines[t_end:])
    if has_following:
        # Separate from next topic with a blank line
        user_prompt = ['\nUser: \n\n']
    else:
        # End of file: no trailing blank line
        user_prompt = ['\nUser: \n']

    # --- Step 6: Reassemble ---
    new_body = conv_lines + new_summary_lines + user_prompt

    # Replace topic in the original lines
    new_lines = lines[:h_idx] + [heading_line] + new_body + lines[t_end:]

    _atomic_write(filepath, new_lines)
    return {"ok": True, "topic_id": topic_id}


INIT_TEMPLATE = """\
# TODO

<!-- cotodo collaborative task file -->
<!-- Summary: a blockquote section (> **Summary**) for conclusions/plans -->
<!-- Markers: over, [processing], [pending], @delete -->
<!-- PAUSE: <reason> to pause all processing -->

"""


def init(filepath: str = 'TODO.md', gitignore: bool = True) -> dict:
    """Create a TODO.md template file.

    Args:
        filepath: Path to create the TODO.md file.
        gitignore: If True, add filepath to .gitignore if not already present.

    Returns:
        dict with operation result.
    """
    if os.path.exists(filepath):
        return {"ok": False, "error": f"file already exists: {filepath}"}

    dir_name = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(dir_name, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(INIT_TEMPLATE)

    if gitignore:
        gi_path = os.path.join(os.path.dirname(os.path.abspath(filepath)), '.gitignore')
        basename = os.path.basename(filepath)
        entry = basename + '\n'
        if os.path.exists(gi_path):
            with open(gi_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if basename not in content.splitlines():
                with open(gi_path, 'a', encoding='utf-8') as f:
                    if not content.endswith('\n'):
                        f.write('\n')
                    f.write(entry)
        else:
            with open(gi_path, 'w', encoding='utf-8') as f:
                f.write(entry)

    return {"ok": True, "file": filepath}
