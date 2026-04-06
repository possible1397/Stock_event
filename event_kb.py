"""
事件知識庫 (Event Knowledge Base)
將 事件驅動選股_關係鏈知識庫_v_1.md 結構化為 Python dict。

事件 → 正向/負向產業 + 強度 (高=3, 中=2, 低=1)
"""

STRENGTH_MAP = {"高": 3, "中": 2, "低": 1}

# 關鍵字→事件對照表 (中英文混合，用於新聞分類)
EVENT_KEYWORDS: dict[str, list[str]] = {
    "rate_hike": [
        # 中文
        "升息", "調升利率", "聯準會升息", "Fed升息", "加息",
        "利率上調", "FOMC升息", "央行升息", "理監事會升息",
        "升息1碼", "升息2碼", "升息3碼",
        # English
        "rate hike", "rate increase", "raises rates", "raised rates",
        "interest rate hike", "Fed hikes", "FOMC hikes", "tightening",
        "hawkish", "25 basis points", "50 basis points",
    ],
    "rate_cut": [
        # 中文
        "降息", "調降利率", "聯準會降息", "Fed降息", "減息",
        "利率下調", "央行降息", "降息1碼", "利率寬鬆",
        # English
        "rate cut", "rate cuts", "cuts rates", "cut rates",
        "interest rate cut", "Fed cuts", "FOMC cuts", "monetary easing",
        "dovish", "rate reduction", "pivot",
    ],
    "inflation_up": [
        # 中文
        "通膨上升", "通膨飆升", "通膨加劇", "CPI上揚", "CPI年增率攀升",
        "物價上漲", "通貨膨脹", "PCE上升", "高通膨", "通膨升溫",
        # English
        "inflation rises", "inflation surge", "inflation soars", "CPI rises",
        "CPI higher", "inflation accelerates", "price pressures rise",
        "PCE inflation", "hot inflation", "inflationary",
    ],
    "inflation_down": [
        # 中文
        "通膨降溫", "通膨下滑", "CPI降低", "物價回穩", "通縮",
        "通膨緩和", "CPI年減",
        # English
        "inflation cools", "inflation falls", "inflation eases", "disinflation",
        "deflation", "CPI lower", "CPI drops", "price pressures ease",
        "cooling inflation",
    ],
    "oil_up": [
        # 中文
        "油價上漲", "油價飆升", "原油上揚", "布蘭特原油上漲",
        "WTI上升", "石油漲價", "油價創高", "油價突破",
        # English
        "oil price rise", "oil prices surge", "crude oil rises", "crude higher",
        "Brent rises", "Brent surges", "Brent crude surges", "WTI rises", "WTI surges",
        "oil rally", "oil spike", "oil surges", "crude surges",
        "oil climbs", "energy prices rise",
    ],
    "oil_down": [
        # 中文
        "油價下跌", "油價走軟", "原油下滑", "石油降價",
        "油價重挫", "油價跌破",
        # English
        "oil price drop", "oil prices fall", "crude oil falls", "crude lower",
        "Brent falls", "WTI falls", "oil slump", "oil tumbles",
        "oil declines", "energy prices fall",
    ],
    "war": [
        # 中文
        "戰爭", "戰事升溫", "軍事衝突", "烏克蘭", "中東衝突",
        "以巴衝突", "台海緊張", "軍事行動", "空襲", "開戰",
        "戰爭風險", "地緣政治風險",
        # English
        "war", "military conflict", "geopolitical tensions", "invasion",
        "airstrike", "Ukraine", "Middle East conflict", "Gaza", "Iran attack",
        "Taiwan strait", "escalation", "military action",
    ],
    "usd_strong": [
        # 中文
        "美元升值", "美元強勢", "美元指數上漲", "DXY上揚",
        "新台幣貶值", "台幣走貶", "美元走強",
        # English
        "dollar strengthens", "dollar rises", "dollar surges", "DXY rises",
        "DXY surges", "DXY climbs", "strong dollar", "dollar rallies",
        "greenback rises", "dollar index higher", "dollar index rises",
    ],
    "usd_weak": [
        # 中文
        "美元貶值", "美元走弱", "美元指數下跌", "DXY下跌",
        "新台幣升值", "台幣走升",
        # English
        "dollar weakens", "dollar falls", "dollar drops", "DXY falls",
        "weak dollar", "dollar declines", "greenback falls",
        "dollar index lower",
    ],
    "tariff_war": [
        # 中文
        "關稅", "貿易戰", "貿易摩擦", "關稅壁壘", "加徵關稅",
        "反傾銷", "貿易制裁", "出口管制", "晶片禁令", "轉單效應",
        "供應鏈重組", "脫鉤",
        # English
        "tariff", "tariffs", "trade war", "trade conflict", "trade friction",
        "import duties", "export controls", "chip ban", "sanctions",
        "decoupling", "supply chain reshoring", "reshoring",
        "anti-dumping", "trade restrictions",
    ],
    "ai_boom": [
        # 中文
        "AI熱潮", "人工智慧需求", "GPU需求", "AI伺服器",
        "AI晶片", "大語言模型", "ChatGPT", "算力需求",
        "AI應用", "生成式AI", "AI基礎建設", "CoWoS",
        "HBM", "AI PC", "Nvidia", "英偉達",
        # English
        "AI boom", "artificial intelligence demand", "GPU demand",
        "AI server", "AI chip", "large language model", "LLM",
        "generative AI", "AI infrastructure", "data center demand",
        "Nvidia", "AMD AI", "AI spending", "AI capex",
    ],
    "memory_up": [
        # 中文
        "記憶體漲價", "DRAM上漲", "NAND漲價", "記憶體供不應求",
        "HBM需求", "記憶體報價上揚", "DRAM報價",
        # English
        "DRAM prices rise", "memory prices surge", "NAND prices up",
        "memory shortage", "HBM demand", "DRAM spot price",
        "memory chip prices", "DRAM rally",
    ],
    "shipping_up": [
        # 中文
        "運費上漲", "運價上揚", "貨櫃運價", "BDI上升",
        "波羅的海指數", "海運運費飆升", "缺艙", "塞港",
        # English
        "shipping rates rise", "freight rates surge", "container rates up",
        "Baltic Dry Index", "BDI rises", "shipping costs higher",
        "port congestion", "freight surge",
    ],
    "recession": [
        # 中文
        "景氣轉弱", "經濟衰退", "景氣下行", "需求疲軟",
        "消費萎縮", "GDP下修", "衰退風險", "景氣燈號",
        "製造業萎縮", "PMI低於50",
        # English
        "recession", "economic slowdown", "GDP contracts", "GDP shrinks",
        "demand weakness", "consumer spending falls", "PMI below 50",
        "manufacturing contraction", "recession risk", "economic downturn",
        "stagflation",
    ],
    "policy_subsidy": [
        # 中文
        "政策補助", "政府補貼", "產業補助", "振興方案",
        "科技補助", "綠能補貼", "電動車補助", "國家隊",
        "產業政策", "補貼政策", "政府扶持",
        # English
        "government subsidy", "subsidy", "stimulus package", "fiscal stimulus",
        "IRA", "CHIPS Act", "green subsidy", "EV subsidy",
        "industrial policy", "government support", "tax credit",
    ],
}

# 主知識庫：事件 → 產業影響
EVENT_KB: dict[str, dict] = {
    "rate_hike": {
        "event_name": "升息",
        "factors": ["資金成本上升", "折現率上升"],
        "lag": "immediate",
        "positive_industries": [
            {"industry": "金融", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "成長股", "strength": "高", "strength_score": 3},
            {"industry": "REITs",  "strength": "高", "strength_score": 3},
            {"industry": "高股息", "strength": "中", "strength_score": 2},
        ],
    },
    "rate_cut": {
        "event_name": "降息",
        "factors": ["資金成本下降", "折現率下降"],
        "lag": "short",
        "positive_industries": [
            {"industry": "成長股", "strength": "高", "strength_score": 3},
            {"industry": "房地產", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "金融",   "strength": "中", "strength_score": 2},
        ],
    },
    "inflation_up": {
        "event_name": "通膨上升",
        "factors": ["原物料成本上升", "企業毛利壓縮"],
        "lag": "short",
        "positive_industries": [
            {"industry": "能源",   "strength": "高", "strength_score": 3},
            {"industry": "原物料", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "消費電子",   "strength": "中", "strength_score": 2},
            {"industry": "低毛利製造", "strength": "高", "strength_score": 3},
        ],
    },
    "inflation_down": {
        "event_name": "通膨下降",
        "factors": ["成本壓力減輕", "消費力回升"],
        "lag": "medium",
        "positive_industries": [
            {"industry": "科技",    "strength": "高", "strength_score": 3},
            {"industry": "消費電子","strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "能源",   "strength": "中", "strength_score": 2},
        ],
    },
    "oil_up": {
        "event_name": "油價上升",
        "factors": ["能源收入上升", "運輸成本上升"],
        "lag": "immediate",
        "positive_industries": [
            {"industry": "石油", "strength": "高", "strength_score": 3},
        ],
        "negative_industries": [
            {"industry": "航空", "strength": "高", "strength_score": 3},
            {"industry": "航運", "strength": "中", "strength_score": 2},
        ],
    },
    "oil_down": {
        "event_name": "油價下降",
        "factors": ["能源成本下降", "運輸成本降低"],
        "lag": "short",
        "positive_industries": [
            {"industry": "航空", "strength": "高", "strength_score": 3},
            {"industry": "航運", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "石油", "strength": "高", "strength_score": 3},
        ],
    },
    "war": {
        "event_name": "戰爭升溫",
        "factors": ["軍事需求↑", "油價↑", "避險情緒↑"],
        "lag": "immediate",
        "positive_industries": [
            {"industry": "軍工", "strength": "高", "strength_score": 3},
            {"industry": "能源", "strength": "高", "strength_score": 3},
            {"industry": "黃金", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "航空", "strength": "高", "strength_score": 3},
            {"industry": "旅遊", "strength": "高", "strength_score": 3},
        ],
    },
    "usd_strong": {
        "event_name": "美元升值",
        "factors": ["出口競爭力提升", "進口成本上升"],
        "lag": "short",
        "positive_industries": [
            {"industry": "出口", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "原物料", "strength": "中", "strength_score": 2},
        ],
    },
    "usd_weak": {
        "event_name": "美元貶值",
        "factors": ["出口競爭力下降", "原物料漲價"],
        "lag": "short",
        "positive_industries": [
            {"industry": "原物料", "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [
            {"industry": "出口", "strength": "中", "strength_score": 2},
        ],
    },
    "tariff_war": {
        "event_name": "關稅/貿易戰",
        "factors": ["供應鏈重組", "轉單效益"],
        "lag": "medium",
        "positive_industries": [
            {"industry": "轉單受惠", "strength": "高", "strength_score": 3},
        ],
        "negative_industries": [
            {"industry": "出口依賴", "strength": "高", "strength_score": 3},
        ],
    },
    "ai_boom": {
        "event_name": "AI熱潮",
        "factors": ["GPU需求↑", "伺服器需求↑", "算力建設↑"],
        "lag": "immediate",
        "positive_industries": [
            {"industry": "半導體",  "strength": "高", "strength_score": 3},
            {"industry": "AI伺服器","strength": "高", "strength_score": 3},
            {"industry": "散熱",    "strength": "中", "strength_score": 2},
        ],
        "negative_industries": [],
    },
    "memory_up": {
        "event_name": "記憶體漲價",
        "factors": ["記憶體廠商獲利↑", "消費電子成本↑"],
        "lag": "short",
        "positive_industries": [
            {"industry": "記憶體", "strength": "高", "strength_score": 3},
        ],
        "negative_industries": [
            {"industry": "消費電子", "strength": "中", "strength_score": 2},
        ],
    },
    "shipping_up": {
        "event_name": "航運運價上升",
        "factors": ["運費收入↑", "貨主成本↑"],
        "lag": "immediate",
        "positive_industries": [
            {"industry": "航運", "strength": "高", "strength_score": 3},
        ],
        "negative_industries": [
            {"industry": "消費電子", "strength": "低", "strength_score": 1},
        ],
    },
    "recession": {
        "event_name": "景氣轉弱",
        "factors": ["終端需求↓", "庫存調整↑"],
        "lag": "medium",
        "positive_industries": [],
        "negative_industries": [
            {"industry": "消費電子", "strength": "高", "strength_score": 3},
            {"industry": "半導體",   "strength": "中", "strength_score": 2},
        ],
    },
    "policy_subsidy": {
        "event_name": "政策補助",
        "factors": ["政府資金挹注", "需求刺激"],
        "lag": "short",
        "positive_industries": [
            {"industry": "受補助產業", "strength": "高", "strength_score": 3},
        ],
        "negative_industries": [],
    },
}
