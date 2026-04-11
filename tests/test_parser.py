"""Unit tests for cotodo parser."""

import os
import tempfile
from cotodo.parser import scan


def _write_tmp(content: str) -> str:
    """Write content to a temp file and return path."""
    fd, path = tempfile.mkstemp(suffix='.md')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def test_empty_file():
    path = _write_tmp('')
    try:
        result = scan(path, all_topics=True)
        assert result['paused'] is False
        assert result['topics'] == []
    finally:
        os.unlink(path)


def test_file_not_found():
    result = scan('/nonexistent/TODO.md', all_topics=True)
    assert 'error' in result
    assert result['topics'] == []


def test_pause_true():
    path = _write_tmp('# Title\n\nPAUSE: true\n\n## Topic\n\nUser: hello over\n')
    try:
        result = scan(path, all_topics=True)
        assert result['paused'] is True
    finally:
        os.unlink(path)


def test_pause_false_empty():
    path = _write_tmp('# Title\n\nPAUSE:\n\n## Topic\n\nUser: hello over\n')
    try:
        result = scan(path, all_topics=True)
        assert result['paused'] is False
    finally:
        os.unlink(path)


def test_pause_false_whitespace():
    path = _write_tmp('# Title\n\nPAUSE:   \n\n## Topic\n\nUser: hello over\n')
    try:
        result = scan(path, all_topics=True)
        assert result['paused'] is False
    finally:
        os.unlink(path)


def test_over_basic():
    path = _write_tmp('## Topic\n\nUser: fix bug over\n')
    try:
        result = scan(path, all_topics=True)
        assert len(result['topics']) == 1
        assert result['topics'][0]['over'] == 3
    finally:
        os.unlink(path)


def test_over_case_insensitive():
    path = _write_tmp('## Topic\n\nUser: fix bug Over\nUser: another OVER\n')
    try:
        result = scan(path, all_topics=True)
        # Only last over is returned (canonical)
        assert result['topics'][0]['over'] == 4
    finally:
        os.unlink(path)


def test_over_trailing_whitespace():
    path = _write_tmp('## Topic\n\nUser: fix bug over   \n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['over'] == 3
    finally:
        os.unlink(path)


def test_over_not_at_end():
    path = _write_tmp('## Topic\n\nUser: the game is over now\n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['over'] is None
    finally:
        os.unlink(path)


def test_processing():
    path = _write_tmp('## Topic\n\nUser: fix bug [processing]\n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['processing'] == 3
        assert result['topics'][0]['over'] is None
    finally:
        os.unlink(path)


def test_pending():
    path = _write_tmp('## Topic\n\nAgent: plan here [pending]\n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['pending'] == 3
    finally:
        os.unlink(path)


def test_pending_not_in_middle():
    """[pending] in the middle of a line should NOT be detected."""
    path = _write_tmp('## Topic\n\nThe [pending] marker is used for tasks\n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['pending'] is None
    finally:
        os.unlink(path)


def test_delete_marker():
    path = _write_tmp('## Old topic @delete\n\nsome content\n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['delete'] is True
        assert result['topics'][0]['title'] == 'Old topic'
    finally:
        os.unlink(path)


def test_delete_trailing_whitespace():
    path = _write_tmp('## Old topic @delete   \n\nsome content\n')
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['delete'] is True
    finally:
        os.unlink(path)


def test_multiple_topics():
    content = '## Topic A\n\nUser: msg1 over\n\n## Topic B\n\nUser: msg2 over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert len(result['topics']) == 2
        assert result['topics'][0]['title'] == 'Topic A'
        assert result['topics'][0]['line'] == 1
        assert result['topics'][0]['end'] == 4
        assert result['topics'][1]['title'] == 'Topic B'
        assert result['topics'][1]['line'] == 5
        assert result['topics'][1]['end'] == 7
    finally:
        os.unlink(path)


def test_code_block_ignored():
    content = '## Topic\n\n```\nUser: inside code over\n```\n\nUser: real over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['over'] == 7
    finally:
        os.unlink(path)


def test_inline_code_ignored():
    content = '## Topic\n\nThe marker `over` is used at line end\n\nUser: real over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['over'] == 5
    finally:
        os.unlink(path)


def test_table_row_ignored():
    content = '## Topic\n\n| cmd | desc |\n| over | marks end |\n\nUser: real over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['over'] == 6
    finally:
        os.unlink(path)


def test_topic_end_lines():
    content = '# Header\n\nPAUSE:\n\n## A\n\nline1\nline2\n\n## B\n\nline3\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['line'] == 5
        assert result['topics'][0]['end'] == 9
        assert result['topics'][1]['line'] == 10
        assert result['topics'][1]['end'] == 12
    finally:
        os.unlink(path)


# --- New tests for context and normalization ---

def test_multiple_over_returns_last_only():
    """Multiple over in same topic: only last one returned."""
    content = '## Topic\n\nUser: msg1 over\nUser: msg2 over\nUser: msg3 over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['over'] == 5  # only last
    finally:
        os.unlink(path)


def test_context_with_over():
    content = '## Topic\n\nUser: fix bug over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['context'] == 'User: fix bug'
    finally:
        os.unlink(path)


def test_context_with_processing():
    content = '## Topic\n\nUser: msg1\nUser: msg2 [processing]\nUser: new opinion\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        # Context stops at [processing] line, excludes below; marker stripped
        assert result['topics'][0]['context'] == 'User: msg1\nUser: msg2'
    finally:
        os.unlink(path)


def test_context_priority_processing_over_over():
    content = '## Topic\n\nUser: msg1 [processing]\nUser: msg2 over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        # processing takes priority for context; marker stripped
        assert result['topics'][0]['context'] == 'User: msg1'
    finally:
        os.unlink(path)


def test_context_with_pending():
    content = '## Topic\n\nAgent: plan [pending]\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['context'] == 'Agent: plan'
    finally:
        os.unlink(path)


def test_context_none_when_no_markers():
    content = '## Topic\n\nSome discussion\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['context'] is None
    finally:
        os.unlink(path)


def test_context_skips_blank_lines_after_heading():
    content = '## Topic\n\n\n\nUser: msg over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, all_topics=True)
        assert result['topics'][0]['context'] == 'User: msg'
    finally:
        os.unlink(path)


# --- Marker priority masking tests ---

def test_processing_masks_over_and_pending():
    """When [processing] exists, over and [pending] are masked to null."""
    content = '## Topic\n\nUser: msg over\nAgent: working [processing]\nAgent: plan [pending]\n'
    path = _write_tmp(content)
    try:
        t = scan(path, all_topics=True)['topics'][0]
        assert t['processing'] == 4
        assert t['over'] is None
        assert t['pending'] is None
    finally:
        os.unlink(path)


def test_over_masks_pending():
    """When over exists (no [processing]), [pending] is masked to null."""
    content = '## Topic\n\nAgent: plan [pending]\nUser: new request over\n'
    path = _write_tmp(content)
    try:
        t = scan(path, all_topics=True)['topics'][0]
        assert t['over'] == 4
        assert t['pending'] is None
        assert t['processing'] is None
    finally:
        os.unlink(path)


def test_pending_alone_reported():
    """When only [pending] exists, it is reported normally."""
    content = '## Topic\n\nAgent: step 1, step 2 [pending]\n'
    path = _write_tmp(content)
    try:
        t = scan(path, all_topics=True)['topics'][0]
        assert t['pending'] == 3
        assert t['over'] is None
        assert t['processing'] is None
    finally:
        os.unlink(path)


# --- Marker-based output (default mode) tests ---

def test_action_idle_empty():
    """Empty file returns idle."""
    path = _write_tmp('')
    try:
        result = scan(path)
        assert result['marker'] == 'idle'
        assert result['file'] == path
    finally:
        os.unlink(path)


def test_action_idle_no_markers():
    """Topics without markers return idle."""
    path = _write_tmp('## Topic\n\nSome discussion\n')
    try:
        result = scan(path)
        assert result['marker'] == 'idle'
    finally:
        os.unlink(path)


def test_action_pause():
    """Paused state returns pause marker."""
    path = _write_tmp('# Title\n\nPAUSE: true\n\n## Topic\n\nUser: hello over\n')
    try:
        result = scan(path)
        assert result['marker'] == 'pause'
        assert 'topic' not in result
    finally:
        os.unlink(path)


def test_action_reply_over():
    """Topic with over returns over marker."""
    path = _write_tmp('## Topic\n\nUser: fix bug over\n')
    try:
        result = scan(path)
        assert result['marker'] == 'over'
        assert result['topic']['title'] == 'Topic'
        assert result['topic']['context'] == 'User: fix bug'
    finally:
        os.unlink(path)


def test_action_resume_processing():
    """Topic with [processing] returns processing marker."""
    path = _write_tmp('## Topic\n\nAgent: working [processing]\n')
    try:
        result = scan(path)
        assert result['marker'] == 'processing'
        assert result['topic']['title'] == 'Topic'
    finally:
        os.unlink(path)


def test_action_execute_pending():
    """Topic with [pending] returns pending marker."""
    path = _write_tmp('## Topic\n\nAgent: plan here [pending]\n')
    try:
        result = scan(path)
        assert result['marker'] == 'pending'
        assert result['topic']['title'] == 'Topic'
    finally:
        os.unlink(path)


def test_action_priority_resume_over_reply():
    """processing takes priority over over."""
    content = '## A\n\nUser: msg over\n\n## B\n\nAgent: working [processing]\n'
    path = _write_tmp(content)
    try:
        result = scan(path)
        assert result['marker'] == 'processing'
        assert result['topic']['title'] == 'B'
    finally:
        os.unlink(path)


def test_action_priority_reply_over_execute():
    """over takes priority over pending."""
    content = '## A\n\nAgent: plan [pending]\n\n## B\n\nUser: msg over\n'
    path = _write_tmp(content)
    try:
        result = scan(path)
        assert result['marker'] == 'over'
        assert result['topic']['title'] == 'B'
    finally:
        os.unlink(path)


# --- --clean tests ---

def test_clean_removes_delete_topics():
    """--clean removes @delete topics from the file."""
    content = '## Keep me\n\nUser: hello over\n\n## Remove me @delete\n\nold content\n'
    path = _write_tmp(content)
    try:
        result = scan(path, clean=True, all_topics=True)
        # @delete topic should not be in result
        assert len(result['topics']) == 1
        assert result['topics'][0]['title'] == 'Keep me'
        # File should be modified
        with open(path, 'r', encoding='utf-8') as f:
            new_content = f.read()
        assert '@delete' not in new_content
        assert 'Keep me' in new_content
    finally:
        os.unlink(path)


def test_clean_no_delete_topics():
    """--clean with no @delete topics preserves all content."""
    content = '## Topic\n\nUser: hello over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, clean=True, all_topics=True)
        assert len(result['topics']) == 1
        with open(path, 'r', encoding='utf-8') as f:
            actual = f.read()
        # Content preserved (heading may have cid injected)
        assert 'User: hello over' in actual
        assert '## Topic' in actual
    finally:
        os.unlink(path)


def test_clean_default_mode():
    """--clean with default (marker) mode skips @delete in priority."""
    content = '## Old @delete\n\nold stuff\n\n## Active\n\nUser: hello over\n'
    path = _write_tmp(content)
    try:
        result = scan(path, clean=True)
        assert result['marker'] == 'over'
        assert result['topic']['title'] == 'Active'
        # File should have @delete removed
        with open(path, 'r', encoding='utf-8') as f:
            assert '@delete' not in f.read()
    finally:
        os.unlink(path)
