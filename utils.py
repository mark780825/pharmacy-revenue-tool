# 定義類別與手續費邏輯

# 收入類別結構 (Categorized based on User Images)
INCOME_CATEGORIES = {
    "銷貨收入": {
        "Line Pay收入": 0.977,   # 1000 * 0.977 = 977
        "信用卡收入": 0.98,      # 1000 * 0.98 = 980
        "現金收入": 1.0
    },
    "健保收入": {
        "健保一暫": 1.0,
        "健保二暫": 1.0,
        "健保補助": 1.0
    },
    "業主資本": {
        "一般投入": 1.0,
        "上期結轉": 1.0
    }
}

# 支出類別結構
EXPENSE_CATEGORIES = {
    "薪資支出": [
        "月薪",
        "獎金",
        "特休代金"
    ],
    "水電雜費": [
        "水費",
        "電費",
        "瓦斯",
        "電信費",
        "地墊清潔",
        "其他雜費"
    ],
    "勞健保勞退": [
        "勞保",
        "健保",
        "勞退"
    ],
    "銷貨成本": [
        "調劑藥品",
        "銷售商品"
    ],
    "稅務支出": [
        "營業稅"
    ],
    "家庭支出": [
        "家事費",
        "菜錢",
        "雞蛋",
        "停車費",
        "其他"
    ],
    "帳戶類別": [ # This seems to be a list of accounts, but maybe User meant Bank fees? 
                  # Looking at image 1, it lists "帳戶類別" with "銀行", "現金" at the bottom.
                  # I will treat this as Account Types, not Expense Categories.
    ]
}

ACCOUNT_TYPES = ["銀行", "現金"]

def calculate_net_amount(category, subcategory, amount):
    """
    根據子科目計算淨額。
    return: (net_amount, is_adjusted)
    """
    if category == "銷貨收入":
        rate = INCOME_CATEGORIES[category].get(subcategory, 1.0)
        if rate != 1.0:
            return amount * rate, True
    return amount, False

# 使用者帳號 (Simple hardcoded users for now)
USERS = {
    "admin": "admin123",
    "staff": "staff123"
}

def verify_user(username, password):
    """
    驗證使用者，成功回傳角色 (admin/staff)，失敗回傳 None。
    """
    if username in USERS and USERS[username] == password:
        if username == "admin":
            return "admin"
        else:
            return "staff"
    return None
