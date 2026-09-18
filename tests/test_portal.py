"""Portal tests."""

import pytest
from samjon_memory.core.service import CoreService


def test_portal_index_contains_title():
    from samjon_memory.portal.pages import render_portal_index
    html = render_portal_index()
    assert "Samjon Memory Core Portal" in html


def test_portal_memory_list():
    from samjon_memory.portal.pages import render_memory_list
    memories = [{"memory_id": "m1", "subject": "test", "status": "active", "memory_type": "fact"}]
    html = render_memory_list(memories, page=1)
    assert "test" in html
    assert "m1" in html