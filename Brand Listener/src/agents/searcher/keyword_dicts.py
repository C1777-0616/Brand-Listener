"""
共享品牌/产品/成分关键词字典。
供 xiaohongshu_updates_agent.py 和 ocr_agent.py 共用。
"""

BRAND_KEYWORDS = {
    "usmile": ["usmile", "笑容加", "USmile"],
    "参半": ["参半"],
    "倍至": ["倍至", "bixdo"],
    "佳洁士": ["佳洁士", "Crest", "crest"],
    "高露洁": ["高露洁", "Colgate", "colgate"],
    "BOP": ["BOP", "bop", "波普专研"],
    "冷酸灵": ["冷酸灵"],
    "舒客": ["舒客", "Saky", "saky"],
    "云南白药": ["云南白药"],
    "黑人": ["黑人牙膏", "黑人"],
    "狮王": ["狮王", "Lion"],
    "欧乐B": ["欧乐B", "Oral-B", "oral-b"],
    "飞利浦": ["飞利浦", "Philips", "Sonicare"],
    "松下": ["松下", "Panasonic", "panasonic"],
}

PRODUCT_KEYWORDS = {
    "电动牙刷": ["电动牙刷", "声波牙刷", "电刷"],
    "冲牙器": ["冲牙器", "水牙线", "洁牙器"],
    "美白牙膏": ["美白牙膏", "亮白牙膏", "白牙膏", "净白牙膏"],
    "抗敏牙膏": ["抗敏牙膏", "敏感牙膏", "脱敏牙膏"],
    "儿童牙膏": ["儿童牙膏", "宝宝牙膏", "kids牙膏"],
    "漱口水": ["漱口水", "口腔清新剂", "mouthwash"],
    "牙线": ["牙线", "牙线棒", "膨胀牙线"],
    "牙贴": ["牙贴", "美白贴", "美白牙贴"],
    "小光环": ["小光环"],
    "台式冲牙器": ["台式冲牙器", "台式水牙线"],
    "Y1 Pro": ["Y1 Pro", "y1 pro", "Y1Pro"],
    "pro": [" pro"],
}

INGREDIENT_KEYWORDS = {
    "氟化物": ["含氟", "氟化物", "氟化钠", "单氟磷酸钠", "奥拉氟", "氟"],
    "氨基酸": ["氨基酸"],
    "小苏打": ["小苏打", "碳酸氢钠"],
    "益生菌": ["益生菌", "乳酸菌"],
    "酵素": ["酵素", "酶"],
    "竹盐": ["竹盐"],
    "蜂胶": ["蜂胶"],
    "茶多酚": ["茶多酚"],
    "木糖醇": ["木糖醇"],
    "薄荷": ["薄荷", "清凉"],
    "活性炭": ["活性炭", "竹炭"],
    "过氧化氢": ["过氧化氢", "双氧水"],
    "羟基磷灰石": ["羟基磷灰石"],
    "柠檬酸锌": ["柠檬酸锌", "PCA锌"],
    "生物活性玻璃": ["生物活性玻璃"],
    "无氟": ["无氟"],
}


def match_keywords(text: str) -> dict:
    """对文本匹配品牌/产品/成分关键词，返回结果 dict。

    供 OCR Agent 和其他需要关键词匹配的模块使用。
    """
    brands = []
    for brand, kws in BRAND_KEYWORDS.items():
        if any(kw in text for kw in kws):
            brands.append(brand)

    products = []
    for product, kws in PRODUCT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            products.append(product)

    ingredients = []
    for ingredient, kws in INGREDIENT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            ingredients.append(ingredient)

    return {
        "brands": brands,
        "products": products,
        "ingredients": ingredients,
    }
