#!/usr/bin/env python3
"""The assistant's daily dollar ceiling.

Each test pins one property the ceiling has to have for "$25 a day" to be true:
costs priced from real token counts, reservations that refuse at the line, a
failed call that is not charged, an unmeasured call that is not free, and a
ledger that fails closed. The last group drives the real _model_request and
handler, with the provider and the table faked, so no model is ever called.

The fake table enforces the conditional write the way DynamoDB does -- the
condition is evaluated against the stored row and the update is all-or-nothing
-- because a permissive fake is how an earlier suite passed over a collector
that had never once written a counter in production.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
# The package import, as the rest of the suite uses -- not the flat Lambda
# layout. Importing handler flat loaded tools_joins as a top-level module, so
# a later `import chat.tools` found it already in sys.modules and it registered
# pipeline_for into the flat copy of tools: test_every_extension_loads then
# failed, but only when it ran after this file.
sys.path.insert(0, str(ROOT / "cloud"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from chat import budget as B                                        # noqa: E402

DAY_T = 1_789_000_000          # a fixed instant, so every test shares one UTC day


def _err(code):
    return ClientError({"Error": {"Code": code, "Message": code}}, "UpdateItem")


class LedgerTable:
    """The operations budget.py uses, with DynamoDB's semantics.

    Supports `ADD n :v, ...` and `SET n = :v, ...` in one expression, and the
    one condition the reservation uses. The update is applied to a copy and
    committed only if the condition held.
    """

    def __init__(self, fail=False):
        self.items: dict[str, dict] = {}
        self.fail = fail

    def get_item(self, Key):
        it = self.items.get(Key["pk"])
        return {"Item": copy.deepcopy(it)} if it else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues, ConditionExpression=None, **_):
        if self.fail:
            raise _err("ProvisionedThroughputExceededException")
        names, vals = ExpressionAttributeNames, ExpressionAttributeValues
        row = copy.deepcopy(self.items.get(Key["pk"]) or dict(Key))

        if ConditionExpression:
            m = re.fullmatch(r"attribute_not_exists\((#\w+)\) OR (#\w+) <= (:\w+)",
                             ConditionExpression)
            assert m, f"fake does not model condition {ConditionExpression!r}"
            attr = names[m.group(1)]
            ok = attr not in row or row[attr] <= vals[m.group(3)]
            if not ok:
                raise _err("ConditionalCheckFailedException")

        for clause, body in re.findall(r"(ADD|SET)\s+(.*?)(?=\s+(?:ADD|SET)\s+|$)",
                                       UpdateExpression):
            for part in [p.strip() for p in body.split(",") if p.strip()]:
                if clause == "ADD":
                    n, v = part.split()
                    row[names[n]] = row.get(names[n], 0) + vals[v]
                else:
                    n, v = [x.strip() for x in part.split("=")]
                    row[names[n]] = vals[v]
        self.items[Key["pk"]] = row
        return {}


def spent(table):
    return table.get_item(B.key_for(B.day_of(DAY_T)))["Item"].get("spent_micro", 0)


# --- pricing ----------------------------------------------------------------
def test_cached_prompt_tokens_are_billed_at_the_cached_rate():
    """prompt_tokens includes the cached ones; they must not be charged twice."""
    usage = {"prompt_tokens": 43_000, "completion_tokens": 107,
             "prompt_tokens_details": {"cached_tokens": 40_000}}
    # 3,000 x $2.50 + 40,000 x $1.25 + 107 x $10, per million
    assert B.cost_micro(usage) == 7_500 + 50_000 + 1_070


def test_a_response_without_usage_is_not_priced_as_free():
    assert B.cost_micro(None) is None
    assert B.cost_micro({}) is None
    assert B.cost_micro({"prompt_tokens": 0, "completion_tokens": 0}) is None


def test_the_estimate_is_an_upper_bound_on_the_bill():
    """The ceiling only holds if a reservation is never smaller than the charge.

    A body of N characters is at most about N/4 tokens of English, all of it
    possibly uncached, and the output can run to max_tokens. The estimate has
    to cover that worst case for a prompt the size this service really sends.
    """
    body = {"messages": [{"role": "system", "content": "x" * 172_000}]}
    est = B.estimate_micro(body, max_tokens=2000)
    worst = B.cost_micro({"prompt_tokens": len(json.dumps(body)) // 4,
                          "completion_tokens": 2000})
    assert est >= worst


# --- reserve and settle ---------------------------------------------------------
def test_a_reservation_that_would_cross_the_ceiling_is_refused():
    t = LedgerTable()
    t.items[B.key_for(B.day_of(DAY_T))["pk"]] = {"pk": "x", "spent_micro": 24_950_000}
    with pytest.raises(B.BudgetExhausted):
        B.reserve(t, 100_000, now=DAY_T)          # $24.95 + $0.10 > $25
    B.reserve(t, 50_000, now=DAY_T)               # $24.95 + $0.05 fits exactly
    assert spent(t) == 25_000_000


def test_reservations_can_never_sum_past_the_ceiling():
    """1,000 worst-case calls against $25: exactly the ones that fit get in.

    DynamoDB serialises the conditional writes of concurrent Lambdas; this
    checks that the condition those writes run is the right one.
    """
    t = LedgerTable()
    admitted = 0
    for _ in range(1000):
        try:
            B.reserve(t, 150_000, now=DAY_T)       # $0.15 each
            admitted += 1
        except B.BudgetExhausted:
            pass
    assert admitted == 25_000_000 // 150_000     # 166
    assert spent(t) <= B.budget_micro()


def test_settling_replaces_the_reservation_with_the_real_cost():
    t = LedgerTable()
    B.reserve(t, 150_000, now=DAY_T)
    usage = {"prompt_tokens": 43_000, "completion_tokens": 107,
             "prompt_tokens_details": {"cached_tokens": 40_000}}
    charged = B.settle(t, 150_000, B.cost_micro(usage), usage, "openai", now=DAY_T)
    row = t.items[B.key_for(B.day_of(DAY_T))["pk"]]
    assert charged == 58_570
    assert row["spent_micro"] == 58_570
    assert row["calls"] == 1 and row["calls_openai"] == 1
    assert row["reservations"] == 0
    assert row["cached_tokens"] == 40_000


def test_an_unmeasured_call_keeps_its_reservation_as_the_charge():
    t = LedgerTable()
    B.reserve(t, 150_000, now=DAY_T)
    assert B.settle(t, 150_000, None, None, "openrouter", now=DAY_T) == 150_000
    row = t.items[B.key_for(B.day_of(DAY_T))["pk"]]
    assert row["spent_micro"] == 150_000 and row["unmeasured_calls"] == 1


def test_a_call_that_never_happened_is_not_charged():
    t = LedgerTable()
    B.reserve(t, 150_000, now=DAY_T)
    assert B.settle(t, 150_000, 0, None, now=DAY_T) == 0
    row = t.items[B.key_for(B.day_of(DAY_T))["pk"]]
    assert row["spent_micro"] == 0 and row.get("calls", 0) == 0


def test_the_ledger_fails_closed():
    """A spending cap that fails open is not a cap."""
    with pytest.raises(B.BudgetUnavailable):
        B.reserve(LedgerTable(fail=True), 150_000, now=DAY_T)


def test_rows_record_the_ceiling_in_force_and_outlive_the_dashboard_window():
    t = LedgerTable()
    B.reserve(t, 1, now=DAY_T)
    row = t.items[B.key_for(B.day_of(DAY_T))["pk"]]
    assert row["budget_micro"] == B.budget_micro() == 25_000_000
    assert row["ttl"] - DAY_T > 90 * 86400


# --- the real call path ----------------------------------------------------------
@pytest.fixture
def H(monkeypatch):
    from chat import handler
    table = LedgerTable()
    monkeypatch.setattr(handler, "_get_rate_table", lambda: table)
    handler._test_table = table
    return handler


def _fake_provider(calls, usage=None, fail=False):
    def request(provider, messages, use_tools=True):
        calls.append(provider["name"])
        if fail:
            raise OSError("connection refused")
        return ({"role": "assistant", "content": "ok"},
                usage if usage is not None else
                {"prompt_tokens": 43_000, "completion_tokens": 100,
                 "prompt_tokens_details": {"cached_tokens": 0}})
    return request


def test_an_exhausted_day_makes_no_model_call(H, monkeypatch):
    calls = []
    monkeypatch.setattr(H, "_provider_request", _fake_provider(calls))
    day = B.key_for(B.day_of())["pk"]
    H._test_table.items[day] = {"pk": day, "spent_micro": B.budget_micro()}
    with pytest.raises(B.BudgetExhausted):
        H._model_request([{"role": "user", "content": "hi"}])
    assert calls == [], "the provider must not be called once the day is spent"


def test_each_call_is_charged_its_real_cost(H, monkeypatch):
    calls = []
    monkeypatch.setattr(H, "_provider_request", _fake_provider(calls))
    H._request_spend.update(micro=0, calls=0)
    H._model_request([{"role": "user", "content": "hi"}])
    H._model_request([{"role": "user", "content": "again"}])
    assert H._request_spend == {"micro": 2 * 108_500, "calls": 2}
    assert H._test_table.items[B.key_for(B.day_of())["pk"]]["spent_micro"] == 217_000


def test_when_every_provider_fails_the_reservation_is_returned(H, monkeypatch):
    calls = []
    monkeypatch.setattr(H, "_provider_request", _fake_provider(calls, fail=True))
    with pytest.raises(RuntimeError):
        H._model_request([{"role": "user", "content": "hi"}])
    assert calls == ["openai", "openrouter"]
    assert H._test_table.items[B.key_for(B.day_of())["pk"]]["spent_micro"] == 0


def test_the_handler_refuses_with_a_daily_budget_code_and_logs_it(H, monkeypatch):
    calls, logged = [], []
    monkeypatch.setattr(H, "_provider_request", _fake_provider(calls))
    monkeypatch.setattr(H, "_check_rate", lambda ip: (True, 30))
    monkeypatch.setattr(H, "_check_daily", lambda now=None: ("ok", 1))
    monkeypatch.setattr(H._cache, "lookup", lambda *a, **k: (None, None))
    monkeypatch.setattr(H, "_log_chat", logged.append)
    day = B.key_for(B.day_of())["pk"]
    H._test_table.items[day] = {"pk": day, "spent_micro": B.budget_micro()}

    out = H.handler({"requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.9"}},
                     "headers": {"origin": H.ALLOWED_ORIGIN},
                     "body": json.dumps({"v": 2, "message": "a question nobody has asked"})})
    body = json.loads(out["body"])
    assert out["statusCode"] == 429
    assert body["error_code"] == "daily_budget"
    assert 0 < body["retry_after_s"] <= 86400
    assert calls == []
    assert H._test_table.items[day]["refused"] == 1
    assert logged and logged[0]["budget_refused"] is True
    assert logged[0]["cost_micro"] == 0


def test_a_cached_answer_is_still_served_after_the_ceiling(H, monkeypatch):
    """Cache hits cost nothing, so the ceiling must not turn them away."""
    calls = []
    monkeypatch.setattr(H, "_provider_request", _fake_provider(calls))
    monkeypatch.setattr(H, "_check_rate", lambda ip: (True, 30))
    monkeypatch.setattr(H, "_check_daily", lambda now=None: ("ok", 1))
    monkeypatch.setattr(H, "_log_chat", lambda r: None)
    monkeypatch.setattr(H._cache, "lookup",
                        lambda *a, **k: ({"v": 2, "reply": "cached answer"}, "exact"))
    day = B.key_for(B.day_of())["pk"]
    H._test_table.items[day] = {"pk": day, "spent_micro": B.budget_micro()}

    out = H.handler({"requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.9"}},
                     "headers": {"origin": H.ALLOWED_ORIGIN},
                     "body": json.dumps({"v": 2, "message": "a common question"})})
    assert out["statusCode"] == 200
    assert json.loads(out["body"])["reply"] == "cached answer"
    assert calls == []
