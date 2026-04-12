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
            # Verify User: placeholder was added
            assert 'User: \n' in content
        finally:
            os.unlink(path)

    def test_take_pending_becomes_processing(self):
        path = _write_tmp('## Topic A\n\nUser: hello\n\n[pending]\n')
        try:
            result = scan(path, take=True)
            assert result['marker'] == 'processing'
            content = _read(path)
            assert '[processing]' in content
            # Verify User: placeholder was added
            assert 'User: \n' in content
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

    def test_take_then_reply_no_duplicate_user_prompt(self):
        """take adds User: placeholder, reply should not create duplicate."""
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            # take: over → processing + User: placeholder
            scan(path, take=True)
            content_after_take = _read(path)
            assert content_after_take.count('User: \n') == 1

            # reply: should replace the existing User: placeholder, not add another
            tid = topic_id(path, 'Topic A')
            reply(path, tid, context='response here')
            content_after_reply = _read(path)
            # Should have exactly one User: placeholder (from reply)
            assert content_after_reply.count('User: \n') == 1
            assert 'Agent: response here' in content_after_reply
        finally:
            os.unlink(path)

    def test_take_user_prompt_at_end_of_file(self):
        """take at end of file: User prompt has no trailing blank line."""
        path = _write_tmp('## Topic A\n\nUser: hello over\n')
        try:
            scan(path, take=True)
            content = _read(path)
            assert content.endswith('User: \n')
            assert not content.endswith('User: \n\n')
        finally:
            os.unlink(path)

    def test_take_user_prompt_with_following_topic(self):
        """take with following topic: blank line separator before next topic."""
        path = _write_tmp(
            '## Topic A\n\nUser: hello over\n\n'
            '## Topic B\n\nUser: world\n'
        )
        try:
            scan(path, take=True)
            content = _read(path)
            # Should have separator between User: prompt and next topic
            assert 'User: \n\n## Topic B' in content
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
        """compress=True replaces old conversation with compressed version preserving dialog order."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: very long question with details about foo and bar and baz over\n\n'
            'Agent: very long answer explaining foo, then bar, then baz in detail\n\n'
            'User: follow up question with more redundant info over\n\n'
            'Agent: follow up answer with more details\n'
        )
        try:
            compressed_convo = (
                'User: 问 foo/bar/baz\n\n'
                'Agent: 已解释 foo/bar/baz\n\n'
                'User: 追问\n\n'
                'Agent: 已补充'
            )
            reply(path, topic_id(path, 'Topic A'), context=compressed_convo, compress=True)
            content = _read(path)
            # Old verbose content removed
            assert 'very long question' not in content
            assert 'very long answer' not in content
            assert 'redundant info' not in content
            # Compressed content present, preserving dialog order
            assert 'User: 问 foo/bar/baz' in content
            assert 'Agent: 已解释 foo/bar/baz' in content
            assert 'User: 追问' in content
            assert 'Agent: 已补充' in content
            # User prompt placeholder at end
            assert 'User: \n' in content
        finally:
            os.unlink(path)

    def test_reply_compress_clears_conversation_when_no_context(self):
        """compress=True with context=None clears conversation, keeps Summary."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old question over\n\n'
            'Agent: old answer\n\n'
            '> **Summary**\n'
            '> **问题**: test\n'
            '> **方案**: solution\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'), context=None, compress=True)
            content = _read(path)
            assert 'old question' not in content
            assert 'old answer' not in content
            assert '> **Summary**' in content
            assert '**问题**: test' in content
            assert '**方案**: solution' in content
            assert 'User: ' in content  # User prompt placeholder
        finally:
            os.unlink(path)

    def test_reply_compress_with_context_and_summary(self):
        """compress=True with context and summary replaces both."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old convo over\n\n'
            'Agent: old reply\n\n'
            '> **Summary**\n'
            '> old summary\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'),
                  context='compressed convo', summary='new summary', compress=True)
            content = _read(path)
            assert 'old convo' not in content
            assert 'old reply' not in content
            assert 'old summary' not in content
            assert 'compressed convo' in content
            assert 'new summary' in content
        finally:
            os.unlink(path)

    def test_reply_compress_preserves_other_topics(self):
        """compress only affects the target topic, not others."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old message over\n\n'
            '## Topic B\n\n'
            'User: keep this over\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'),
                  context='compressed', compress=True)
            content = _read(path)
            assert '## Topic B' in content
            assert 'keep this' in content
            assert 'old message' not in content
        finally:
            os.unlink(path)

    def test_reply_compress_no_context_no_summary(self):
        """compress=True with no context and no summary: clears convo, keeps existing summary."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: q1 over\n\n'
            'Agent: a1\n\n'
            'User: q2 over\n\n'
            'Agent: a2\n\n'
            '> **Summary**\n'
            '> existing summary\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'), compress=True)
            content = _read(path)
            assert 'q1' not in content
            assert 'a1' not in content
            assert 'q2' not in content
            assert 'a2' not in content
            assert '> **Summary**' in content
            assert 'existing summary' in content
        finally:
            os.unlink(path)

    def test_reply_compress_user_prompt_at_end_of_file(self):
        """compress at end of file: User prompt has no trailing blank line."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old data over\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'),
                  context='compressed', compress=True)
            content = _read(path)
            assert content.endswith('User: \n'), f"File should end with 'User: \\n', got: {repr(content[-20:])}"
            assert not content.endswith('User: \n\n'), "Should not have trailing blank line at end of file"
        finally:
            os.unlink(path)

    def test_reply_compress_discards_pending_after(self):
        """compress discards pending_after messages (no duplicate User: prompts)."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old convo over\n\n'
            '> **Summary**\n'
            '> s0\n\n'
            'User: compress please [processing]\n\n'
            'User: \n\n'
            '## Topic B\n\n'
            'User: other\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'), compress=True)
            content = _read(path)
            # Only one User: prompt should exist in topic A
            topic_a_end = content.find('## Topic B')
            topic_a = content[:topic_a_end]
            user_count = topic_a.count('User: ')
            assert user_count == 1, (
                f"Expected 1 User: prompt in compressed topic, got {user_count}"
            )
            # Summary preserved
            assert '> **Summary**' in topic_a
            assert 's0' in topic_a
        finally:
            os.unlink(path)

    def test_reply_compress_user_prompt_with_following_topic(self):
        """compress with following topic: User prompt has one blank line separator."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: old data over\n\n'
            '## Topic B\n\n'
            'User: other over\n'
        )
        try:
            reply(path, topic_id(path, 'Topic A'),
                  context='compressed', compress=True)
            content = _read(path)
            # Should have blank line between User: prompt and next topic
            assert 'User: \n\n## Topic B' in content
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

    def test_reply_keeps_post_processing_messages(self):
        """Messages added after [processing] should not be merged into conversation."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: question over\n\n'
            '> **Summary**\n'
            '> existing\n\n'
            'User: pre-processing message over\n\n'
            '[processing]\n\n'
            'User: new idea while agent is working\n'
        )
        try:
            tid = topic_id(path, 'Topic A')
            reply(path, tid, context='answer', summary='updated summary')
            content = _read(path)
            # pre-processing message should be merged into conversation
            assert 'pre-processing message' in content
            # post-processing message should still be present (not lost)
            assert 'new idea while agent is working' in content
            # Agent reply present
            assert 'Agent: answer' in content
            # The post-processing message should appear AFTER Summary
            summary_pos = content.find('> **Summary**')
            new_idea_pos = content.find('new idea while agent is working')
            assert new_idea_pos > summary_pos, \
                "Post-processing message should appear after Summary"
        finally:
            os.unlink(path)

    def test_reply_processing_on_text_line_merges_text(self):
        """[processing] on same line as text: text belongs to pre-processing."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: first question over\n\n'
            '> **Summary**\n'
            '> existing\n\n'
            'User: two issues:\n'
            '1. first issue [processing]\n\n'
            'User: new follow-up\n'
        )
        try:
            tid = topic_id(path, 'Topic A')
            reply(path, tid, context='answer', summary='new summary')
            content = _read(path)
            # "two issues" and "1. first issue" should merge into conversation
            assert 'two issues' in content
            assert '1. first issue' in content
            # They should appear BEFORE Agent reply
            agent_pos = content.find('Agent: answer')
            issues_pos = content.find('two issues')
            assert issues_pos < agent_pos, \
                "Pre-processing content should be before Agent reply"
            # "new follow-up" is post-processing, should be after Summary
            assert 'new follow-up' in content
            summary_pos = content.find('> **Summary**')
            followup_pos = content.find('new follow-up')
            assert followup_pos > summary_pos, \
                "Post-processing content should be after Summary"
        finally:
            os.unlink(path)

    def test_reply_processing_standalone_line(self):
        """[processing] on standalone line: content before it merges, after stays."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: question over\n\n'
            '> **Summary**\n'
            '> existing\n\n'
            'User: pre msg over [processing]\n\n'
            'User: post msg\n'
        )
        try:
            tid = topic_id(path, 'Topic A')
            reply(path, tid, context='answer')
            content = _read(path)
            # "pre msg" text (with [processing] stripped) should be in conversation
            assert 'pre msg' in content
            agent_pos = content.find('Agent: answer')
            pre_pos = content.find('pre msg')
            assert pre_pos < agent_pos
            # "post msg" should be preserved after Summary
            assert 'post msg' in content
        finally:
            os.unlink(path)

    def test_reply_no_processing_merges_all_after_summary(self):
        """Without [processing], all after_summary content merges into conversation."""
        path = _write_tmp(
            '## Topic A\n\n'
            'User: question over\n\n'
            '> **Summary**\n'
            '> existing\n\n'
            'User: follow up over\n'
        )
        try:
            tid = topic_id(path, 'Topic A')
            reply(path, tid, context='answer')
            content = _read(path)
            # follow up should be merged into conversation (before Agent reply)
            assert 'follow up' in content
            agent_pos = content.find('Agent: answer')
            followup_pos = content.find('follow up')
            assert followup_pos < agent_pos, \
                "After-summary content should be merged before Agent reply"
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
