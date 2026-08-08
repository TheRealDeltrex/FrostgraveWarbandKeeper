import warband_store as ws


def test_black_market_roll_and_buy(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["black_market_enabled"] = True

    ok, msg = ws.black_market_roll(wb, "Treasure Table", 11)  # "Magic Item"
    assert ok, msg
    bm = wb["black_market"]
    assert bm["rolls_used"] == 1
    assert len(bm["offers"]) == 1
    offer = bm["offers"][0]
    assert offer["entries"], "row 11 (Magic Item) should resolve to a concrete item"
    item = offer["entries"][0]
    assert not item["bought"]

    ok, msg = ws.black_market_buy_item(wb, offer["id"], item["id"])
    assert ok, msg
    assert item["bought"]
    assert any(v["name"] == item["name"] for v in wb["vault_items"])

    ok, msg = ws.black_market_buy_item(wb, offer["id"], item["id"])
    assert not ok

    ok, msg = ws.black_market_roll(wb, "Treasure Table", 4)  # "20gc, Potions (3)"
    assert ok, msg
    offer2 = wb["black_market"]["offers"][1]
    assert len(offer2["entries"]) == 3

    ok, msg = ws.black_market_reset(wb)
    assert ok, msg
    assert wb["black_market"]["offers"] == []
    assert wb["black_market"]["rolls_used"] == 0
