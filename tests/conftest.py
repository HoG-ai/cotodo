"""Shared test helpers and fixtures for cotodo tests."""
from cotodo.parser import scan


def topic_id(path: str, title: str) -> str:
    """Get the cid of a topic by its title via scan."""
    result = scan(path, all_topics=True)
    for t in result['topics']:
        if t['title'] == title:
            return t['id']
    raise ValueError(f"Topic '{title}' not found in {path}")
