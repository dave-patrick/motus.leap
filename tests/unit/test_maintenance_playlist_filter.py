import pytest
from app import MaintenanceActionIn

def test_maintenance_action_in_schema():
    payload = MaintenanceActionIn(action="fix_all", type="misplaced", playlist_id="PL_SORT_123")
    assert payload.action == "fix_all"
    assert payload.type == "misplaced"
    assert payload.playlist_id == "PL_SORT_123"
