"""Tests for new features: Summary parsing, scan --take, reply, init."""

import os
import tempfile

from cotodo.parser import scan, reply, init
from conftest import topic_id


def _write_tmp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix='.md')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================
# Summary parsing tests
# ============================================================

class TestSummaryParsing:
    def test_summary_basic(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: hello over\n\n'
            '> **Summary**\n'
            '> - task 1\n'
            '> - task 2\n'
        )
        try:
            result = scan(path, all_topics=True)
            t = result['topics'][0]
            assert t['summary'] == '- task 1\n- task 2'
        finally:
            os.unlink(path)

    def test_summary_with_pending_marker(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: hello\n\n'
            '> **Summary** [pending]\n'
            '> - task 1\n'
        )
        try:
            result = scan(path, all_topics=True)
            t = result['topics'][0]
            assert t['summary'] == '- task 1'
            assert t['pending'] is not None
        finally:
            os.unlink(path)

    def test_summary_with_processing_marker(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: hello\n\n'
            '> **Summary** [processing]\n'
            '> - task 1\n'
        )
        try:
            result = scan(path, all_topics=True)
            t = result['topics'][0]
            assert t['summary'] == '- task 1'
            assert t['processing'] is not None
        finally:
            os.unlink(path)

    def test_summary_none_when_absent(self):
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            result = scan(path, all_topics=True)
            t = result['topics'][0]
            assert t['summary'] is None
        finally:
            os.unlink(path)

    def test_summary_empty_body(self):
        path = _write_tmp(
            '## Topic A\n\n'
            '> **Summary**\n'
            '\n'
            'User: hello over\n'
        )
        try:
            result = scan(path, all_topics=True)
            t = result['topics'][0]
            assert t['summary'] is None  # empty body → None
        finally:
            os.unlink(path)

    def test_summary_in_default_mode_output(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: do it over\n\n'
            '> **Summary**\n'
            '> plan content here\n'
        )
        try:
            result = scan(path)
            assert result['marker'] == 'over'
            assert result['topic']['summary'] == 'plan content here'
        finally:
            os.unlink(path)

    def test_summary_none_in_output_when_absent(self):
        path = _write_tmp('## Topic A\n\nUser: do it over\n')
        try:
            result = scan(path)
            assert result['marker'] == 'over'
            assert result['topic']['summary'] is None
        finally:
            os.unlink(path)

    def test_summary_multiline(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: hi over\n\n'
            '> **Summary**\n'
            '> line 1\n'
            '> line 2\n'
            '> line 3\n'
        )
        try:
            result = scan(path, all_topics=True)
            assert result['topics'][0]['summary'] == 'line 1\nline 2\nline 3'
        finally:
            os.unlink(path)


# ============================================================
# scan --take tests
# ============================================================

class TestScanTake:
    def test_take_over_becomes_processing(self):
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            result = scan(path, take=True)
            assert result['marker'] == 'processing'
            # Verify file was modified
            content = _read(path)
            assert '[processing]' in content
        finally:
            os.unlink(path)

    def test_take_pending_becomes_processing(self):
        path = _write_tmp('## Topic A\n\nUser: hello\n\n[pending]\n')
        try:
            result = scan(path, take=True)
            assert result['marker'] == 'processing'
            content = _read(path)
            assert '[processing]' in content
        finally:
            os.unlink(path)

    def test_take_already_processing_no_change(self):
        content_orig = '## Topic A\n\nUser: hello [processing]\n'
        path = _write_tmp(content_orig)
        try:
            result = scan(path, take=True)
            assert result['marker'] == 'processing'
            # Content should be preserved (cid injection is allowed)
            content = _read(path)
            assert '## Topic A' in content
            assert 'User: hello [processing]' in content
        finally:
            os.unlink(path)

    def test_take_idle_no_change(self):
        path = _write_tmp('## Topic A\n\nUser: hello\n')
        try:
            result = scan(path, take=True)
            assert result['marker'] == 'idle'
        finally:
            os.unlink(path)

    def test_take_paused_no_change(self):
        path = _write_tmp('PAUSE: reason\n\n## Topic A\n\nUser: hello over\n')
        try:
            result = scan(path, take=True)
            assert result['marker'] == 'pause'
        finally:
            os.unlink(path)

    def test_take_picks_highest_priority(self):
        path = _write_tmp(
            '## Topic A\n\nUser: hello [pending]\n\n'
            '## Topic B\n\nUser: hello over\n'
        )
        try:
            result = scan(path, take=True)
            # over is higher priority than pending
            assert result['marker'] == 'processing'
            assert result['topic']['title'] == 'Topic B'
        finally:
            os.unlink(path)


# ============================================================
# reply tests
# ============================================================

class TestReply:
    def test_reply_basic_context(self):
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            result = reply(path, topic_id(path, 'Topic A'), context='world')
            assert result['ok'] is True
            content = _read(path)
            assert 'Agent: world' in content
            assert 'User:' in content  # User: prompt appended
        finally:
            os.unlink(path)

    def test_reply_with_summary(self):
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            result = reply(path, topic_id(path, 'Topic A'), context='done', summary='- task 1\n- task 2')
            assert result['ok'] is True
            content = _read(path)
            assert 'Agent: done' in content
            assert '> **Summary**' in content
            assert '> - task 1' in content
            assert '> - task 2' in content
        finally:
            os.unlink(path)

    def test_reply_with_pending_marker(self):
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            reply(path, topic_id(path, 'Topic A'), context='working', summary='plan', pending=True)
            content = _read(path)
            assert '> **Summary** [pending]' in content
        finally:
            os.unlink(path)

    def test_reply_removes_processing_marker(self):
        path = _write_tmp('## Topic A\n\nUser: hello [processing]\n')
        try:
            reply(path, topic_id(path, 'Topic A'), context='done')
            content = _read(path)
            assert '[processing]' not in content
            assert 'Agent: done' in content
        finally:
            os.unlink(path)

    def test_reply_overwrites_existing_summary(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: hello over\n\n'
            '> **Summary**\n'
            '> old plan\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'), context='updated', summary='new plan')
            content = _read(path)
            assert '> new plan' in content
            assert 'old plan' not in content
        finally:
            os.unlink(path)

    def test_reply_topic_not_found(self):
        path = _write_tmp('## Topic A\n\nUser: hello\n')
        try:
            result = reply(path, 'nonexistent')
            assert result['ok'] is False
            assert 'not found' in result['error']
        finally:
            os.unlink(path)

    def test_reply_file_not_found(self):
        result = reply('/nonexistent/TODO.md', 'any')
        assert result['ok'] is False
        assert 'file not found' in result['error']

    def test_reply_removes_processing_leaves_idle(self):
        path = _write_tmp('## Topic A\n\nUser: hello [processing]\n')
        try:
            reply(path, topic_id(path, 'Topic A'), context='all done')
            content = _read(path)
            assert '[processing]' not in content
            assert 'Agent: all done' in content
        finally:
            os.unlink(path)

    def test_reply_compress_mode(self):
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old message over\n\n'
            'Agent: old response\n\n'
            'User: another message over\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'), context='compressed conversation', compress=True)
            content = _read(path)
            assert 'compressed conversation' in content
            assert 'old message' not in content
            assert 'old response' not in content
            assert 'another message' not in content
        finally:
            os.unlink(path)

    def test_reply_preserves_other_topics(self):
        path = _write_tmp(
            '## Topic A\n\nUser: hello over\n\n'
            '## Topic B\n\nUser: world over\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'), context='reply to A')
            content = _read(path)
            assert '## Topic A' in content
            assert '## Topic B' in content
            assert 'User: world over' in content
            assert 'Agent: reply to A' in content
        finally:
            os.unlink(path)

    def test_reply_summary_only_no_context(self):
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            reply(path, topic_id(path, 'Topic A'), summary='just a plan', pending=True)
            content = _read(path)
            assert '> **Summary** [pending]' in content
            assert '> just a plan' in content
            assert 'Agent:' not in content
        finally:
            os.unlink(path)


# ============================================================
# init tests
# ============================================================

class TestInit:
    def test_init_creates_file(self):
        dir_path = tempfile.mkdtemp()
        filepath = os.path.join(dir_path, 'TODO.md')
        try:
            result = init(filepath)
            assert result['ok'] is True
            assert os.path.exists(filepath)
            content = _read(filepath)
            assert '# TODO' in content
        finally:
            _cleanup_dir(dir_path)

    def test_init_creates_gitignore(self):
        dir_path = tempfile.mkdtemp()
        filepath = os.path.join(dir_path, 'TODO.md')
        try:
            init(filepath)
            gi = os.path.join(dir_path, '.gitignore')
            assert os.path.exists(gi)
            content = _read(gi)
            assert 'TODO.md' in content
        finally:
            _cleanup_dir(dir_path)

    def test_init_appends_to_existing_gitignore(self):
        dir_path = tempfile.mkdtemp()
        filepath = os.path.join(dir_path, 'TODO.md')
        gi = os.path.join(dir_path, '.gitignore')
        with open(gi, 'w') as f:
            f.write('node_modules/\n')
        try:
            init(filepath)
            content = _read(gi)
            assert 'node_modules/' in content
            assert 'TODO.md' in content
        finally:
            _cleanup_dir(dir_path)

    def test_init_no_duplicate_gitignore(self):
        dir_path = tempfile.mkdtemp()
        filepath = os.path.join(dir_path, 'TODO.md')
        gi = os.path.join(dir_path, '.gitignore')
        with open(gi, 'w') as f:
            f.write('TODO.md\n')
        try:
            init(filepath)  # Will fail because file exists? No, init creates TODO.md
            # Actually init should fail because TODO.md doesn't exist yet,
            # but .gitignore already has it
            content = _read(gi)
            assert content.count('TODO.md') == 1
        finally:
            _cleanup_dir(dir_path)

    def test_init_skip_gitignore(self):
        dir_path = tempfile.mkdtemp()
        filepath = os.path.join(dir_path, 'TODO.md')
        try:
            init(filepath, gitignore=False)
            gi = os.path.join(dir_path, '.gitignore')
            assert not os.path.exists(gi)
        finally:
            _cleanup_dir(dir_path)

    def test_init_file_already_exists(self):
        path = _write_tmp('existing content')
        try:
            result = init(path)
            assert result['ok'] is False
            assert 'already exists' in result['error']
        finally:
            os.unlink(path)


def _cleanup_dir(dir_path):
    import shutil
    shutil.rmtree(dir_path, ignore_errors=True)
