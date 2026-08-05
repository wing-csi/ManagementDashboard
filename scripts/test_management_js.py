"""Unit tests for management status, scope movement and guarded forecasting."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright", reason="management.js tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/management.js'); "
        f"return ({body}); }}"
    )


def test_scope_change_reports_gross_adds_removes_and_net(page, server):
    plan = """{
      done: 5, total: 11,
      history: [
        {date:'2026-07-01', done:0, total:10},
        {date:'2026-07-08', done:2, total:12},
        {date:'2026-07-15', done:4, total:11}
      ]
    }"""
    got = evaluate(page, server, f"m.scopeChange({plan}, '2026-07-22')")
    assert got["baseline"] == 10
    assert got["current"] == 11
    assert got["added"] == 2
    assert got["removed"] == 1
    assert got["net"] == 1


def test_scope_change_ignores_task_date_rows_that_only_backfill_completion(page, server):
    plan = """{
      done:7,total:12,history_backfilled:true,
      history:[
        {date:'2026-01-01',done:0,total:12,source:'task-date'},
        {date:'2026-07-01',done:6,total:12,source:'task-date'},
        {date:'2026-08-01',done:7,total:12,source:'snapshot'}
      ]
    }"""
    got = evaluate(page, server, f"m.scopeChange({plan}, '2026-08-05')")
    assert got["baseline"] == 12 and got["current"] == 12
    assert got["net"] == 0 and got["observations"] == 2
    assert got["baselineDate"] == "2026-08-01"


def test_backfilled_forecast_is_capped_at_medium_confidence(page, server):
    plan = """{
      done:8,total:10,due_max:'2026-09-01',history_backfilled:true,
      history:[
        {date:'2026-01-01',done:0,total:10,source:'task-date'},
        {date:'2026-02-01',done:2,total:10,source:'task-date'},
        {date:'2026-03-01',done:4,total:10,source:'task-date'},
        {date:'2026-04-01',done:6,total:10,source:'task-date'},
        {date:'2026-05-01',done:8,total:10,source:'snapshot'}
      ]
    }"""
    got = evaluate(page, server, f"m.completionForecast({plan}, '2026-08-05')")
    assert got["status"] == "forecast"
    assert got["confidence"] == "medium"


def test_old_metrics_keep_current_scope_but_do_not_invent_a_baseline(page, server):
    change = evaluate(page, server, "m.scopeChange({done:0,total:11}, '2026-07-22')")
    assert change["available"] is False
    assert change["reason"] == "no-history"
    assert change["current"] == 11

    data = """{generated_at:'2026-07-22T12:00:00Z',repos:['acme/app'],tasks:[],errors:[],
      repo_meta:{'acme/app':{plan:{path:'plan.md',done:0,total:11,open_tasks:[]}}}}"""
    summary = evaluate(page, server,
        f"m.deriveManagement({data}, {{todayStr:'2026-07-22', nowMs:Date.parse('2026-07-22T13:00:00Z')}})")
    assert summary["totals"]["currentScope"] == 11
    assert summary["totals"]["scopeRepos"] == 1
    assert summary["totals"]["historyRepos"] == 0


def test_forecast_uses_observed_progress_and_names_confidence(page, server):
    plan = """{
      done: 5, total: 10, due_max:'2026-08-20',
      history: [
        {date:'2026-07-01', done:0, total:10},
        {date:'2026-07-08', done:2, total:10},
        {date:'2026-07-15', done:4, total:10}
      ]
    }"""
    got = evaluate(page, server, f"m.completionForecast({plan}, '2026-07-22')")
    assert got["status"] == "forecast"
    assert got["projected"] == "2026-08-12"
    assert got["confidence"] == "medium"
    assert got["late"] is False


def test_forecast_refuses_to_invent_a_rate_without_progress(page, server):
    plan = """{done:0,total:10,history:[
      {date:'2026-07-01',done:0,total:10},
      {date:'2026-07-15',done:0,total:10}
    ]}"""
    got = evaluate(page, server, f"m.completionForecast({plan}, '2026-07-15')")
    assert got["status"] == "unavailable"
    assert got["reason"] == "no-observed-progress"


def test_high_priority_overdue_work_is_off_track(page, server):
    data = """{
      generated_at:'2026-08-05T12:00:00Z', repos:['acme/app'], tasks:[], errors:[],
      repo_meta:{'acme/app':{plan:{path:'plan.md',done:1,total:3,due_max:'2026-08-20',
        open_tasks:[{title:'Ship blocker',due:'2026-08-01',priority:'P1'}],
        history:[{date:'2026-07-01',done:0,total:3},{date:'2026-08-05',done:1,total:3}]}}}
    }"""
    got = evaluate(page, server,
                   f"m.deriveManagement({data}, {{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')}})")
    assert got["portfolioStatus"] == "off-track"
    assert got["projects"][0]["highOverdue"] == 1


def test_missing_planning_data_is_unknown_not_green(page, server):
    data = """{generated_at:'2026-08-05T12:00:00Z',repos:['acme/app'],tasks:[],errors:[],
      repo_meta:{'acme/app':{}}}"""
    got = evaluate(page, server,
                   f"m.deriveManagement({data}, {{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')}})")
    assert got["portfolioStatus"] == "unknown"
    assert got["projects"][0]["status"] == "unknown"


def test_issue_permission_errors_are_visible_in_data_health(page, server):
    data = """{generated_at:'2026-08-05T12:00:00Z',repos:['acme/app'],tasks:[],errors:[],
      repo_meta:{'acme/app':{issues_error:'Resource not accessible by token'}}}"""
    got = evaluate(page, server,
                   f"m.deriveManagement({data}, {{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')}})")
    assert got["health"]["status"] == "attention"
    assert got["health"]["counts"]["issueErrors"] == 1
    assert any("收集唔到 GitHub Issue" in item["title"]
               for item in got["attention"])
