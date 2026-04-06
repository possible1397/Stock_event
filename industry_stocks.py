"""
產業 → 台股對照模組

優先從 Stock 專案的 supply_chain_data.json 讀取，
讀取失敗時 fallback 到內建的代表性股票清單。
"""
import json
from pathlib import Path

# 知識庫短標籤 → supply_chain_data.json 的 key
INDUSTRY_ALIAS: dict[str, str | None] = {
    # 直接對應
    "半導體":    "半導體",
    "記憶體":    "記憶體",
    "AI伺服器":  "AI伺服器",
    "航運":      "交通運輸及航運",
    "航空":      "交通運輸及航運",
    "金融":      "金融",
    "建設":      "建材營造",
    "房地產":    "建材營造",
    "綠能":      "綠能",
    "能源":      "油電燃氣",
    "石油":      "油電燃氣",
    "原物料":    "鋼鐵",
    "鋼鐵":      "鋼鐵",
    "汽車":      "汽車",
    "旅遊":      "休閒娛樂",
    "食品":      "食品",
    "製藥":      "製藥",
    # 概念對應 (KB 抽象標籤 → 最接近的供應鏈分類)
    "成長股":    "半導體",       # 台股成長股以半導體為主
    "REITs":     "建材營造",
    "高股息":    "金融",
    "科技":      "半導體",
    "消費電子":  "電子零組件",
    "低毛利製造":"電子零組件",
    "消費":      "食品",
    "出口":      "半導體",       # 台灣出口以電子/半導體為主
    "出口依賴":  "半導體",
    "轉單受惠":  "電子零組件",
    "伺服器":    "AI伺服器",
    "散熱":      "AI伺服器",
    "黃金":      "金融",
    "受補助產業":"綠能",
    "軍工":      None,           # 台股無直接軍工類股
}

# Fallback 代表性股票（供應鏈檔案不可用時）
FALLBACK_TICKERS: dict[str, list[str]] = {
    "半導體":          ["2330.TW", "2454.TW", "2303.TW", "2344.TW", "3711.TW"],
    "記憶體":          ["2344.TW", "2408.TW", "3260.TW"],
    "AI伺服器":        ["2382.TW", "2356.TW", "2308.TW", "3017.TW", "6669.TWO"],
    "交通運輸及航運":  ["2603.TW", "2609.TW", "2615.TW", "2618.TW"],
    "金融":            ["2880.TW", "2881.TW", "2882.TW", "2884.TW", "2886.TW"],
    "建材營造":        ["2515.TW", "5534.TW", "2504.TW"],
    "綠能":            ["3576.TWO", "6443.TW", "3691.TW"],
    "油電燃氣":        ["6505.TW", "8917.TW"],
    "電子零組件":      ["2317.TW", "2327.TW", "3037.TW"],
    "鋼鐵":            ["2002.TW", "2006.TW", "2007.TW"],
    "食品":            ["1216.TW", "1201.TW"],
    "休閒娛樂":        ["2901.TW", "9941.TW"],
    "汽車":            ["2207.TW", "2201.TW"],
    "製藥":            ["1710.TW", "4105.TW"],
}

# supply_chain_data.json 路徑
_SUPPLY_CHAIN_PATH = Path(__file__).parent.parent / "Stock" / "data" / "supply_chain_data.json"


class IndustryStockMapper:
    def __init__(self, supply_chain_path: Path = _SUPPLY_CHAIN_PATH):
        self._chain: dict = {}
        self._source = "fallback"
        if supply_chain_path.exists():
            try:
                with open(supply_chain_path, encoding="utf-8") as f:
                    raw = json.load(f)
                # 去除 _metadata
                self._chain = {k: v for k, v in raw.items() if not k.startswith("_")}
                self._source = str(supply_chain_path)
            except Exception as e:
                print(f"[Warning] 無法載入供應鏈資料: {e}，改用 fallback")

    @property
    def source(self) -> str:
        return self._source

    def get_tickers(self, kb_industry: str, max_per_industry: int = 15) -> list[str]:
        """
        將知識庫產業標籤轉為股票代碼清單。
        優先取 supply_chain 的全產業 tickers，否則用 fallback。
        """
        chain_key = INDUSTRY_ALIAS.get(kb_industry)
        if chain_key is None:
            return []  # 例如軍工，台股無對應

        # 嘗試從供應鏈資料取
        if chain_key in self._chain:
            entry = self._chain[chain_key]
            # 優先用「全產業」，其次合併各層
            if "全產業" in entry:
                tickers = entry["全產業"].get("tickers", [])
            else:
                tickers = []
                for layer in ["上游", "中游", "下游"]:
                    tickers += entry.get(layer, {}).get("tickers", [])
            # 去重、截斷
            seen: set[str] = set()
            result = []
            for t in tickers:
                if t not in seen:
                    seen.add(t)
                    result.append(t)
            return result[:max_per_industry]

        # Fallback
        return FALLBACK_TICKERS.get(chain_key, [])[:max_per_industry]

    def get_industry_label(self, kb_industry: str) -> str:
        """回傳顯示用產業名稱（供應鏈 key 或原始標籤）"""
        chain_key = INDUSTRY_ALIAS.get(kb_industry)
        return chain_key if chain_key else kb_industry
