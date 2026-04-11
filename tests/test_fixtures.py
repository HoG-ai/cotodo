"""Fixture-based integration tests for cotodo parser.

Tests use pre-built TODO.md files in tests/fixtures/.
Non-destructive tests run on originals; destructive tests (--clean) copy first.
"""

import os
import shutil
import tempfile

import pytest
from cotodo.parser import scan

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def fixture_path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


def copy_fixture(name: str) -> str:
    """Copy a fixture to a temp file for destructive tests."""
    src = fixture_path(name)
    fd, dst = tempfile.mkstemp(suffix='.md')
    os.close(fd)
    shutil.copy2(src, dst)
    return dst


# ===========================================================
# TODO_full.md — 17 scenarios (non-destructive, --all mode)
# ===========================================================

class TestFullFixture:
    """Tests against TODO_full.md covering all marker/parsing scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self):
        tmp = copy_fixture('TODO_full.md')
        try:
            self.result = scan(tmp, all_topics=True)
            self.topics = {t['title']: t for t in self.result['topics']}
            yield
        finally:
            os.unlink(tmp)

    def test_not_paused(self):
        assert self.result['paused'] is False

    def test_topic_count(self):
        assert len(self.result['topics']) == 17

    # --- over variants ---

    def test_t1_over_basic(self):
        t = self.topics['T1 - over basic']
        assert t['over'] is not None
        assert t['context'] == 'User: fix the login bug'

    def test_t2_over_case_insensitive(self):
        t = self.topics['T2 - over case insensitive']
        assert t['over'] is not None
        assert t['context'] == 'User: uppercase test'

    def test_t3_over_trailing_whitespace(self):
        t = self.topics['T3 - over trailing whitespace']
        assert t['over'] is not None
        assert t['context'] == 'User: trailing spaces'

    def test_t4_over_not_at_end(self):
        t = self.topics['T4 - over NOT at end']
        assert t['over'] is None
        assert t['context'] is None

    def test_t5_over_in_code_block(self):
        t = self.topics['T5 - over in code block (ignored)']
        assert t['over'] is None
        assert t['context'] is None

    def test_t6_over_in_inline_code(self):
        t = self.topics['T6 - over in inline code (ignored)']
        assert t['over'] is None
        assert t['context'] is None

    def test_t7_over_in_table_row(self):
        t = self.topics['T7 - over in table row (ignored)']
        assert t['over'] is None
        assert t['context'] is None

    # --- processing ---

    def test_t8_processing(self):
        t = self.topics['T8 - processing replaces over']
        assert t['processing'] is not None
        assert t['over'] is None
        assert t['context'] == 'User: fix color'

    def test_t9_processing_masks_over(self):
        t = self.topics['T9 - processing masks earlier over']
        assert t['processing'] is not None
        assert t['over'] is None
        assert 'first message over' in t['context']
        assert 'Agent: got it, working on it' in t['context']
        assert 'second message' in t['context']

    # --- pending ---

    def test_t10_pending_basic(self):
        t = self.topics['T10 - pending basic']
        assert t['pending'] is not None
        assert t['over'] is None
        assert 'Agent: I will fix the button style' in t['context']

    def test_t11_pending_masked_by_over(self):
        t = self.topics['T11 - pending masked by over']
        assert t['over'] is not None
        assert t['pending'] is None
        assert 'User: new instruction' in t['context']

    # --- @delete ---

    def test_t12_delete(self):
        t = self.topics['T12 - delete topic']
        assert t['delete'] is True
        assert t['context'] is None

    # --- edge cases ---

    def test_t13_multiple_overs_last_wins(self):
        t = self.topics['T13 - multiple overs (last wins)']
        assert t['over'] is not None
        assert 'third and last' in t['context']

    def test_t14_idle(self):
        t = self.topics['T14 - idle (no markers)']
        assert t['over'] is None
        assert t['processing'] is None
        assert t['pending'] is None
        assert t['context'] is None

    def test_t15_mixed_markers_processing_wins(self):
        t = self.topics['T15 - mixed markers processing wins all']
        assert t['processing'] is not None
        assert t['over'] is None
        assert t['pending'] is None

    def test_t16_empty_topic(self):
        t = self.topics['T16 - empty topic (no content)']
        assert t['over'] is None
        assert t['context'] is None

    def test_t17_context_multiline(self):
        t = self.topics['T17 - context extraction multi-line']
        assert t['over'] is not None
        lines = t['context'].split('\n')
        assert len(lines) == 5
        assert lines[0] == 'User: line 1'
        assert lines[1] == 'Agent: response 1'
        assert lines[4] == 'User: line 3'


# ===========================================================
# TODO_full.md — default mode (highest priority marker)
# ===========================================================

class TestFullDefaultMode:
    """Default scan mode returns highest priority marker from TODO_full.md."""

    def test_resume_is_highest(self):
        """T8 has [processing] → marker should be 'processing'."""
        tmp = copy_fixture('TODO_full.md')
        try:
            result = scan(tmp)
            assert result['marker'] == 'processing'
            assert result['topic']['title'] == 'T8 - processing replaces over'
        finally:
            os.unlink(tmp)


# ===========================================================
# TODO_paused.md — PAUSE state (non-destructive)
# ===========================================================

class TestPausedFixture:

    def test_paused_all_mode(self):
        tmp = copy_fixture('TODO_paused.md')
        try:
            result = scan(tmp, all_topics=True)
            assert result['paused'] is True
            assert len(result['topics']) == 2
        finally:
            os.unlink(tmp)

    def test_paused_default_mode(self):
        """PAUSE overrides all topic priorities."""
        tmp = copy_fixture('TODO_paused.md')
        try:
            result = scan(tmp)
            assert result['marker'] == 'pause'
            assert 'topic' not in result
        finally:
            os.unlink(tmp)


# ===========================================================
# TODO_idle.md — all idle (non-destructive)
# ===========================================================

class TestIdleFixture:

    def test_idle_all_mode(self):
        tmp = copy_fixture('TODO_idle.md')
        try:
            result = scan(tmp, all_topics=True)
            assert result['paused'] is False
            for t in result['topics']:
                assert t['over'] is None
                assert t['processing'] is None
                assert t['pending'] is None
        finally:
            os.unlink(tmp)

    def test_idle_default_mode(self):
        tmp = copy_fixture('TODO_idle.md')
        try:
            result = scan(tmp)
            assert result['marker'] == 'idle'
        finally:
            os.unlink(tmp)


# ===========================================================
# TODO_priority.md — marker priority chain (non-destructive)
# ===========================================================

class TestPriorityFixture:

    def test_resume_highest_priority(self):
        """processing (P3) should beat over (P2) and pending (P1)."""
        tmp = copy_fixture('TODO_priority.md')
        try:
            result = scan(tmp)
            assert result['marker'] == 'processing'
            assert result['topic']['title'] == 'P3 - has processing (highest active priority)'
        finally:
            os.unlink(tmp)

    def test_all_topics_markers(self):
        tmp = copy_fixture('TODO_priority.md')
        try:
            result = scan(tmp, all_topics=True)
            topics = {t['title']: t for t in result['topics']}
            assert topics['P1 - has pending (lowest active priority)']['pending'] is not None
            assert topics['P2 - has over (higher than pending)']['over'] is not None
            assert topics['P3 - has processing (highest active priority)']['processing'] is not None
            assert topics['P4 - idle (no markers)']['over'] is None
        finally:
            os.unlink(tmp)


# ===========================================================
# TODO_clean.md — @delete cleanup (DESTRUCTIVE — uses copy)
# ===========================================================

class TestCleanFixture:

    def test_clean_removes_delete_topics(self):
        tmp = copy_fixture('TODO_clean.md')
        try:
            result = scan(tmp, clean=True, all_topics=True)
            # Only non-delete topics should remain
            titles = [t['title'] for t in result['topics']]
            assert 'Keep this topic' in titles
            assert 'Keep this too' in titles
            assert len(titles) == 2

            # Verify file was actually modified
            with open(tmp, 'r') as f:
                content = f.read()
            assert '@delete' not in content
            assert 'Keep this topic' in content
            assert 'Keep this too' in content
        finally:
            os.unlink(tmp)

    def test_clean_default_mode(self):
        """After clean, highest priority should be over (over topic)."""
        tmp = copy_fixture('TODO_clean.md')
        try:
            result = scan(tmp, clean=True)
            assert result['marker'] == 'over'
            assert result['topic']['title'] == 'Keep this topic'
        finally:
            os.unlink(tmp)

    def test_clean_no_delete_topics_no_write(self):
        """If no @delete topics, all original content lines should be preserved."""
        tmp = copy_fixture('TODO_idle.md')
        try:
            with open(tmp, 'r', encoding='utf-8') as f:
                lines_before = [l.strip() for l in f.readlines() if l.strip()]
            scan(tmp, clean=True, all_topics=True)
            with open(tmp, 'r', encoding='utf-8') as f:
                content_after = f.read()
            # Every non-blank original line must appear in order
            pos = 0
            for orig_line in lines_before:
                idx = content_after.find(orig_line, pos)
                assert idx != -1, f"Line not found in output: {orig_line!r}"
                pos = idx + len(orig_line)
        finally:
            os.unlink(tmp)
