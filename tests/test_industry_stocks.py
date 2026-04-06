"""
測試：IndustryStockMapper — 產業映射與 fallback
"""
import pytest
from industry_stocks import IndustryStockMapper, INDUSTRY_ALIAS, FALLBACK_TICKERS


class TestIndustryStockMapper:
    def setup_method(self):
        # 用預設路徑（可能命中 Stock 的 supply_chain_data.json，也可能 fallback）
        self.mapper = IndustryStockMapper()

    # ── get_tickers ──────────────────────────────────────────────

    def test_semiconductor_returns_tickers(self):
        tickers = self.mapper.get_tickers("半導體")
        assert len(tickers) > 0

    def test_military_returns_empty(self):
        """台股無軍工，應回傳空串列"""
        assert self.mapper.get_tickers("軍工") == []

    def test_unknown_industry_returns_empty(self):
        assert self.mapper.get_tickers("不存在的產業") == []

    def test_max_per_industry_limit(self):
        tickers = self.mapper.get_tickers("半導體", max_per_industry=3)
        assert len(tickers) <= 3

    def test_no_duplicate_tickers(self):
        tickers = self.mapper.get_tickers("半導體")
        assert len(tickers) == len(set(tickers))

    def test_reits_maps_to_construction(self):
        """REITs → 建材營造"""
        tickers = self.mapper.get_tickers("REITs")
        assert len(tickers) > 0

    def test_ticker_format(self):
        """台股代號應含 .TW 或 .TWO 後綴"""
        for industry in ["半導體", "金融", "航運"]:
            tickers = self.mapper.get_tickers(industry)
            for t in tickers:
                assert ".TW" in t, f"{t} 不含 .TW 後綴"

    # ── get_industry_label ───────────────────────────────────────

    def test_label_semiconductor(self):
        label = self.mapper.get_industry_label("半導體")
        assert label == "半導體"

    def test_label_growth_stock_maps(self):
        """成長股 → 半導體"""
        label = self.mapper.get_industry_label("成長股")
        assert label == "半導體"

    def test_label_unknown_returns_original(self):
        label = self.mapper.get_industry_label("軍工")
        # INDUSTRY_ALIAS["軍工"] is None → 回傳原始標籤
        assert label == "軍工"

    # ── INDUSTRY_ALIAS 完整性 ────────────────────────────────────

    def test_all_kb_industries_have_alias(self):
        """知識庫中用到的所有產業標籤都應在 INDUSTRY_ALIAS 中"""
        from event_kb import EVENT_KB
        kb_industries: set[str] = set()
        for rule in EVENT_KB.values():
            for entry in rule["positive_industries"] + rule["negative_industries"]:
                kb_industries.add(entry["industry"])

        missing = kb_industries - set(INDUSTRY_ALIAS.keys())
        assert not missing, f"INDUSTRY_ALIAS 缺少: {missing}"
