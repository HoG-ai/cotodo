"""End-to-end integration test for all cotodo commands."""
import os
import tempfile
import shutil
from cotodo.parser import init, scan, reply
from conftest import topic_id


def test_full_workflow():
    """Full workflow: init → add topics → scan → take → reply → scan."""
    dir_path = tempfile.mkdtemp()
    filepath = os.path.join(dir_path, 'TODO.md')
    try:
        # Step 1: Init
        r = init(filepath, gitignore=False)
        assert r['ok'] is True

        # Step 2: Add topics
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write('\n## Fix bug\n\nUser: 修复 bug over\n\n## Add feature\n\nUser: 加功能 over\n')

        # Step 3: Scan
        r = scan(filepath)
        assert r['marker'] == 'over'
        assert r['topic']['title'] == 'Fix bug'

        # Step 4: Take
        r = scan(filepath, take=True)
        assert r['marker'] == 'processing'
        assert r['topic']['title'] == 'Fix bug'

        # Verify [processing] was written
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
        assert '[processing]' in content

        # Step 5: Reply to Fix bug
        r = reply(filepath, topic_id(filepath, 'Fix bug'),
                  context='已修复 auth.py',
                  summary='- [x] 修复完成')
        assert r['ok'] is True

        # Verify file after reply
        with open(filepath, encoding='utf-8') as f:
            content = f.read()

        # Verify markers removed from Fix bug
        assert 'over [processing]' not in content
        # Verify Agent reply was added
        assert 'Agent: 已修复 auth.py' in content
        # Verify Summary was added
        assert '> **Summary**' in content
        assert '> - [x] 修复完成' in content
        # Verify User: prompt added
        assert '\nUser: \n' in content
        # Verify Add feature still has over
        assert '加功能 over' in content

        # Step 6: Scan again — should show Add feature
        r = scan(filepath)
        assert r['marker'] == 'over'
        assert r['topic']['title'] == 'Add feature'

        # Step 7: Reply with pending marker
        r = scan(filepath, take=True)
        assert r['topic']['title'] == 'Add feature'

        r = reply(filepath, topic_id(filepath, 'Add feature'),
                  context='方案：添加 toggle 组件',
                  summary='- [ ] 添加 toggle\n- [ ] 更新 CSS',
                  pending=True)
        assert r['ok'] is True

        with open(filepath, encoding='utf-8') as f:
            content = f.read()

        assert '> **Summary** [pending]' in content
        assert '> - [ ] 添加 toggle' in content

        # Step 8: Scan — should show pending (no more over)
        r = scan(filepath)
        assert r['marker'] == 'pending'
        assert r['topic']['title'] == 'Add feature'

    finally:
        shutil.rmtree(dir_path, ignore_errors=True)


if __name__ == '__main__':
    test_full_workflow()
