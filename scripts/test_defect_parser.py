"""Unit tests for the per-repo defect register parser in collect_github.py.

`defect.md` is a plain GFM task list maintained by hand in each tracked repo,
configured with `defect_file` in config.toml. It exists because GitHub Issues
carry no usable signal here: 1 of 14 repos has issue data at all, and that one
reports open_total = closed_total = 0.

The parser is deliberately separate from parse_plan_markdown even though both
read checkboxes. The plan parser feeds 完成度, 今日建議, 異常 tasks and the
Defect 追蹤 table; changing its return shape to also retain ticked items would
put four working surfaces at risk to serve one new card. They share the marker
regexes instead.

Run:  python -m pytest scripts/test_defect_parser.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collect_github import (  # noqa: E402
    CollectError, DEFECT_CAP, fetch_defect_file, parse_defect_markdown,
)


# ------------------------------ status ------------------------------

def test_checkbox_decides_status_not_the_heading():
    """The rule the format hangs on: `- [ ]` under 「已修」is still open.

    Two signals for one fact is a contradiction waiting to happen, so the
    heading is decoration and the checkbox is the only source of truth.
    """
    got = parse_defect_markdown(
        "# 未修\n"
        "- [x] already fixed but filed under 未修 found:2026-07-01 fixed:2026-07-02\n"
        "# 已修\n"
        "- [ ] still open but filed under 已修 found:2026-07-03\n"
    )
    assert [i["open"] for i in got["items"]] == [False, True]


def test_open_and_fixed_are_both_retained():
    """A ratio needs both sides. parse_plan_markdown keeps only unticked
    tasks, which is why this parser exists."""
    got = parse_defect_markdown(
        "- [ ] a found:2026-07-01\n"
        "- [x] b found:2026-07-02 fixed:2026-07-05\n"
    )
    assert len(got["items"]) == 2
    assert got["items"][1]["fixed"] == "2026-07-05"


# ------------------------------ markers ------------------------------

def test_severity_found_and_fixed_are_parsed():
    got = parse_defect_markdown(
        "- [x] 匯出 CSV 中文亂碼 !P1 found:2026-07-14 fixed:2026-07-20\n")
    assert got["items"][0] == {
        "title": "匯出 CSV 中文亂碼",
        "severity": "P1",
        "found": "2026-07-14",
        "fixed": "2026-07-20",
        "open": False,
    }


def test_markers_are_stripped_from_the_title():
    got = parse_defect_markdown("- [ ] token 冇 refresh !P0 found:2026-07-20\n")
    assert got["items"][0]["title"] == "token 冇 refresh"


def test_marker_order_does_not_matter():
    got = parse_defect_markdown("- [x] a fixed:2026-07-09 !P2 found:2026-07-08\n")
    it = got["items"][0]
    assert (it["severity"], it["found"], it["fixed"]) == ("P2", "2026-07-08", "2026-07-09")


def test_severity_case_is_normalised():
    got = parse_defect_markdown("- [ ] a !p3 found:2026-07-01\n")
    assert got["items"][0]["severity"] == "P3"


def test_absent_markers_are_none_not_missing_keys():
    """Every item carries the full key set so the frontend never has to
    distinguish 'absent' from 'null'."""
    got = parse_defect_markdown("- [ ] bare defect\n")
    assert got["items"][0] == {
        "title": "bare defect", "severity": None,
        "found": None, "fixed": None, "open": True,
    }


# --------------------------- undated defects ---------------------------

def test_an_undated_defect_is_kept_not_dropped():
    """It cannot enter the windowed rate, but it is still a real open defect.

    Dropping it here would depress the rate invisibly — the frontend reports
    the undated count instead.
    """
    got = parse_defect_markdown("- [ ] no date at all\n- [ ] dated found:2026-07-01\n")
    assert len(got["items"]) == 2
    assert got["items"][0]["found"] is None


# ------------------------------ guards ------------------------------

def test_a_file_with_no_checkboxes_is_not_a_register():
    """None, never an empty register — a missing or unrelated file must not
    read as 「zero defects」, which is the same guard parse_plan_markdown uses."""
    assert parse_defect_markdown("# Notes\n\nJust prose, no checkboxes.\n") is None
    assert parse_defect_markdown("") is None


def test_an_empty_register_with_only_a_heading_is_none():
    assert parse_defect_markdown("# 未修\n# 已修\n") is None


def test_items_are_capped_and_the_truncation_is_declared():
    """Silent truncation would read as a complete register."""
    text = "".join(f"- [ ] defect {n} found:2026-07-01\n" for n in range(DEFECT_CAP + 10))
    got = parse_defect_markdown(text)
    assert len(got["items"]) == DEFECT_CAP
    assert got["truncated"] is True


def test_an_uncapped_register_is_not_marked_truncated():
    got = parse_defect_markdown("- [ ] one found:2026-07-01\n")
    assert got["truncated"] is False


# ------------------------------ fetching ------------------------------

class _Boom:
    def rest_raw(self, _path):
        raise CollectError("404 not found")


class _Ok:
    def __init__(self, text):
        self.text = text
        self.asked = None

    def rest_raw(self, path):
        self.asked = path
        return self.text


def test_fetch_returns_none_when_the_file_is_missing():
    """Same contract as fetch_plan_file: a repo without a register is not an
    error, it simply contributes nothing."""
    assert fetch_defect_file(_Boom(), "acme/alpha", "docs/defects.md") is None


def test_fetch_returns_none_when_the_file_is_not_a_register():
    assert fetch_defect_file(_Ok("no checkboxes here"), "acme/alpha", "d.md") is None


def test_fetch_records_the_path_it_read():
    """The Defect 追蹤 table links back to the file, so it needs the path."""
    client = _Ok("- [ ] a found:2026-07-01\n")
    got = fetch_defect_file(client, "acme/alpha", "docs/defects.md")
    assert got["path"] == "docs/defects.md"
    assert client.asked == "/repos/acme/alpha/contents/docs/defects.md"
