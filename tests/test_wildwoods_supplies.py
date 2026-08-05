"""The Wildwoods: Supply Points (sp) economy + the Cargo Transport asset —
previously a deferred/reference-only Lexicon entry, now a real mechanic."""

import expansions
import warband_store


def _enable(wb: dict) -> None:
    wb["homerules"]["enabled_sources"]["The Wildwoods"] = True
    wb["homerules"]["wildwoods_supplies_enabled"] = True


def test_gate_requires_source_book(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["The Wildwoods"] = False
    wb["homerules"]["wildwoods_supplies_enabled"] = True
    ok, msg = warband_store.buy_supply_points(wb, 10)
    assert not ok
    assert "wildwoods" in msg.lower()


def test_gate_requires_homerule(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["The Wildwoods"] = True
    ok, msg = warband_store.buy_supply_points(wb, 10)
    assert not ok
    assert "homerule" in msg.lower()


def test_buy_supply_points_costs_gold_1_to_1(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 100
    ok, msg = warband_store.buy_supply_points(wb, 30)
    assert ok, msg
    assert wb["gold"] == 70
    assert wb["supply_points"] == 30


def test_buy_supply_points_capped_at_carry_capacity(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 1000
    ok, msg = warband_store.buy_supply_points(wb, 51)
    assert not ok
    assert "50" in msg


def test_sell_supply_points_at_2_to_1(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 100
    warband_store.buy_supply_points(wb, 40)
    ok, msg = warband_store.sell_supply_points(wb, 10)
    assert ok, msg
    assert wb["supply_points"] == 30
    assert wb["gold"] == 60 + 5


def test_buy_cargo_transport_raises_carry_capacity(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 1000
    assert expansions.supply_carry_capacity(wb) == 50
    ok, msg = warband_store.buy_cargo_transport(wb)
    assert ok, msg
    assert wb["gold"] == 900
    assert expansions.supply_carry_capacity(wb) == 150
    ok, msg = warband_store.buy_cargo_transport(wb)
    assert not ok
    assert "already" in msg.lower()


def test_cargo_transport_upgrade_needs_transport_first(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 1000
    ok, msg = warband_store.buy_cargo_transport_upgrade(wb, "additional_capacity")
    assert not ok
    assert "transport" in msg.lower()


def test_additional_capacity_upgrade_raises_capacity_further(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 1000
    warband_store.buy_cargo_transport(wb)
    ok, msg = warband_store.buy_cargo_transport_upgrade(wb, "additional_capacity")
    assert ok, msg
    assert expansions.supply_carry_capacity(wb) == 200
    ok, msg = warband_store.buy_cargo_transport_upgrade(wb, "additional_capacity")
    assert not ok
    assert "already" in msg.lower()


def test_sell_cargo_transport_clears_upgrades_and_trims_excess_sp(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 1000
    warband_store.buy_cargo_transport(wb)
    warband_store.buy_cargo_transport_upgrade(wb, "additional_capacity")
    warband_store.buy_supply_points(wb, 180)
    ok, msg = warband_store.sell_cargo_transport(wb)
    assert ok, msg
    assert wb["cargo_transport"]["owned"] is False
    assert wb["cargo_transport"]["upgrades"] == []
    assert wb["supply_points"] == 50  # trimmed down to the unaided capacity


def test_consume_wilderness_supplies_feeds_members_and_reports_shortfall(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 100
    warband_store.buy_supply_points(wb, 3)  # wizard alone needs 2sp
    ok, msg = warband_store.consume_wilderness_supplies(wb)
    assert ok, msg
    assert wb["supply_points"] == 1
    assert "fed" in msg.lower()

    warband_store.buy_supply_points(wb, 1)  # back up to 2sp, still needs 2 -> exact
    ok, msg = warband_store.consume_wilderness_supplies(wb)
    assert ok, msg
    assert wb["supply_points"] == 0

    ok, msg = warband_store.consume_wilderness_supplies(wb)
    assert ok, msg
    assert "short" in msg.lower()
    assert wb["supply_points"] == 0


def test_guide_and_trapper_are_exempt_from_supply_consumption(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["gold"] = 1000
    ok, msg = warband_store.add_soldier(wb, "guide", "Scout")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "trapper", "Snare")
    assert ok, msg
    summary = warband_store.wildwoods_summary(wb)
    # wizard only — the guide and trapper don't count toward consumption
    assert summary["consumption_per_scenario"] == 2
