import pytest

from metro.prep import select_resources

BASE = "https://example.org/download/"
RESOURCES = [
    {"name": "Eylül 2024", "url": BASE + "hourly_transportation_202409.csv"},
    {"name": "Ekim 2024", "url": BASE + "hourly_transportation_202410.csv"},
    {"name": "Kasım 2024", "url": BASE + "hourly_transportation_202411.csv"},
    {"name": "Aralık 2024", "url": BASE + "hourly_transportation_202512.csv"},  # misnamed on the portal
    {"name": "Readme", "url": BASE + "notes.pdf"},
]


def test_selects_months_in_range_by_file_name():
    assert select_resources(RESOURCES, "2024-09", "2024-10") == [
        ("2024-09", BASE + "hourly_transportation_202409.csv"),
        ("2024-10", BASE + "hourly_transportation_202410.csv"),
    ]


def test_misnamed_december_file_is_not_taken_for_2024():
    with pytest.raises(ValueError, match="2024-12"):
        select_resources(RESOURCES, "2024-09", "2024-12")
    assert select_resources(RESOURCES, "2025-12", "2025-12")[0][0] == "2025-12"


def test_newest_first_reverses_order():
    months = [m for m, _ in select_resources(RESOURCES, "2024-09", "2024-10", newest_first=True)]
    assert months == ["2024-10", "2024-09"]


def test_missing_month_in_range_raises():
    with pytest.raises(ValueError, match="2024-08"):
        select_resources(RESOURCES, "2024-08", "2024-10")
