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
            # One clause per guard, ANDed, as DynamoDB evaluates them: all must
            # hold against the STORED row or nothing is written. The voice
            # reservation uses three (dollar ceiling, voice sub-ceiling,
            # session count); the chat reservation uses one.
            clauses = re.split(r"\s+AND\s+", ConditionExpression)
            for clause in clauses:
                m = re.fullmatch(
                    r"\(?attribute_not_exists\((#\w+)\) OR (#\w+) (<=|<) (:\w+)\)?",
                    clause.strip())
                assert m, f"fake does not model condition {clause!r}"
                attr = names[m.group(1)]
                assert names[m.group(2)] == attr, "condition mixes two attributes"
                if attr in row:
                    ok = (row[attr] <= vals[m.group(4)] if m.group(3) == "<="
                          else row[attr] < vals[m.group(4)])
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


# --- voice ------------------------------------------------------------------
# A voice session is billed to a token the browser holds, and no audio or usage
# report ever returns to us. There is nothing to settle, so the reservation is
# the charge and every one of these tests is about the reservation refusing.

def test_a_voice_session_is_priced_at_both_sides_talking_throughout():
    """The worst case, from the rates, not a remembered dollar figure."""
    secs = 300
    tokens = secs * B.REALTIME_TOKENS_PER_SECOND
    usd = (tokens * B.PRICE_REALTIME_AUDIO_IN_PER_M
           + tokens * B.PRICE_REALTIME_AUDIO_OUT_PER_M) / 1_000_000
    assert B.realtime_session_micro(secs) == int(round(usd * B.MICRO)) + 1


def test_a_voice_session_is_charged_before_the_token_is_minted():
    t = LedgerTable()
    est = B.reserve_realtime_session(t, 300, now=DAY_T)
    assert est == B.realtime_session_micro(300)
    row = t.get_item(B.key_for(B.day_of(DAY_T)))["Item"]
    assert row["spent_micro"] == est          # counts against the day's ceiling
    assert row["voice_micro"] == est          # and against voice's own
    assert row["voice_sessions"] == 1


def test_voice_cannot_spend_the_whole_day_and_starve_typed_questions():
    """The sub-ceiling binds before the daily one. Typed questions are the
    service; voice is the flourish, so voice runs out first."""
    t = LedgerTable()
    est = B.realtime_session_micro(300)
    allowed = 0
    while True:
        try:
            B.reserve_realtime_session(t, 300, now=DAY_T)
            allowed += 1
        except B.BudgetExhausted:
            break
        assert allowed < 1000, "voice reservation never refused"
    voice_ceiling = B.REALTIME_DAILY_BUDGET_USD * B.MICRO
    spent_on_voice = t.get_item(B.key_for(B.day_of(DAY_T)))["Item"]["voice_micro"]
    assert spent_on_voice <= voice_ceiling
    # And it stopped well short of the day's whole budget, leaving room to type.
    assert spent_on_voice < B.budget_micro()
    assert allowed == int(voice_ceiling // est) or allowed == int(voice_ceiling // est) + 1


def test_the_session_count_refuses_even_when_the_price_is_wrong():
    """The backstop against a mispriced constant: if audio were billed at a
    thousandth of the real rate the dollar guards would never fire, so the
    count fires instead."""
    t = LedgerTable()
    cheap = 1                                  # one micro-dollar a session
    monkey = B.realtime_session_micro
    B.realtime_session_micro = lambda _s: cheap
    try:
        n = 0
        while True:
            try:
                B.reserve_realtime_session(t, 300, now=DAY_T)
                n += 1
            except B.BudgetExhausted:
                break
            assert n < 10_000, "nothing stopped an underpriced voice session"
    finally:
        B.realtime_session_micro = monkey
    assert n == B.REALTIME_MAX_SESSIONS_PER_DAY


def test_voice_spend_is_visible_to_the_typed_ceiling():
    """Voice and chat share one ceiling. A day that spent its budget on voice
    must refuse a typed question too."""
    t = LedgerTable()
    B.reserve_realtime_session(t, 300, now=DAY_T)
    before = spent(t)
    B.reserve(t, 1_000, now=DAY_T)
    assert spent(t) == before + 1_000          # the same counter, not a parallel one


def test_a_voice_session_fails_closed_when_the_ledger_cannot_be_written():
    with pytest.raises(B.BudgetUnavailable):
        B.reserve_realtime_session(LedgerTable(fail=True), 300, now=DAY_T)


def test_a_session_that_never_started_is_refunded():
    """The reservation is made before the token is minted, so a mint that
    fails has charged for a session nobody had. The first live attempt did
    exactly that -- OpenAI 404'd a retired endpoint and the day was 90 cents
    lighter for it. A broken upstream must not eat the voice budget one error
    at a time."""
    t = LedgerTable()
    est = B.reserve_realtime_session(t, 300, now=DAY_T)
    B.release_realtime_session(t, est, now=DAY_T)
    row = t.get_item(B.key_for(B.day_of(DAY_T)))["Item"]
    assert row["spent_micro"] == 0
    assert row["voice_micro"] == 0
    assert row["voice_sessions"] == 0


def test_a_session_that_started_is_never_refunded():
    """Only the mint-failed path releases. Once the browser holds a token we
    cannot see how much of it was used, so the worst case stands."""
    src = (ROOT / "cloud" / "chat" / "realtime.py").read_text()
    body = src[src.index("def handler("):]
    # Every release must sit in an error path, never after a token is returned.
    assert body.count("release_realtime_session") == 3, \
        "expected exactly three release calls: two upstream errors and no_client_secret"
    tail = body[body.index('return _reply(200'):]
    assert "release_realtime_session" not in tail
