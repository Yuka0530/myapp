
import streamlit as st
import pandas as pd
import cv2
import pytesseract
import requests
import json
import re
from PIL import Image
from bs4 import BeautifulSoup
import numpy as np
import re
import os
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

st.title("デリッシュ献立スクショ → 栄養計算")

st.markdown("""
<style>

/* dropdown候補 */
body div[data-baseweb="popover"] * {
    font-size: 11px !important;
}

/* selectbox */
body div[data-baseweb="select"] * {
    font-size: 12px !important;
}

</style>
""", unsafe_allow_html=True)

def connect_gsheet():

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(credentials)
    return client
# =========================
# マッピング保存読み込み
# =========================
def save_to_gsheet(original, selected):
    client = connect_gsheet()
    sheet = client.open("food_mapping").sheet1

    data = sheet.get_all_values()

    # ヘッダー除外
    rows = data[1:]

    for i, row in enumerate(rows, start=2):
        if row[0] == original and row[1] == selected:
            count = int(row[2]) if len(row) > 2 and row[2] else 0
            sheet.update_cell(i, 3, count + 1)
            return

    # 新規追加
    sheet.append_row([original, selected, 1])

@st.cache_data
def load_mapping():
    client = connect_gsheet()
    sheet = client.open("food_mapping").sheet1

    data = sheet.get_all_values()[1:]

    mapping = {}

    for original, selected, count in data:
        count = int(count) if count else 0

        if original not in mapping:
            mapping[original] = {}

        mapping[original][selected] = count

    return mapping

# =========================
# 栄養データ読み込み
# =========================
@st.cache_data
def load_nutrition():

    client = connect_gsheet()
    sheet = client.open("nutrition").sheet1

    data = sheet.get_all_values()

    df = pd.DataFrame(data[1:], columns=data[0])

    return df.set_index("食材").to_dict(orient="index")
    
nutrition_dict = load_nutrition()

# =========================
# 文字正規化
# =========================
def normalize(text):
    return str(text).replace("\u3000","").replace(" ","").strip()

# =========================
# 候補検索
# =========================
def get_candidates(word, mapping):
    word_n = normalize(word)

    #まずnutrition_dictを検索
    candidates = [
        food for food in nutrition_dict
        if word_n in normalize(food)
    ]

    # 🔥 mappingに履歴があるなら必ず追加
    if word in mapping:
        for saved_food in mapping[word].keys():
            if saved_food not in candidates:
                candidates.append(saved_food)

    return candidates

############################
# タイトル部分切り出し
############################

def crop_titles(img):

    h, w, _ = img.shape

    titles = []

    coords = [
    (220,240,820,320),
    (220,480,820,570),
    (220,700,820,810),
    (220,930,820,1020)
    ]

    for x1,y1,x2,y2 in coords:
        crop = img[y1:y2,x1:x2]
        titles.append(crop)

    return titles


############################
# OCR
############################

def read_title(img):

    text = pytesseract.image_to_string(img,lang="jpn")

    text = text.replace("\n","").strip()

    return text


############################
# デリッシュキッチン検索
############################
@st.cache_data
def search_recipe(name):
    st.write(name)

    query = requests.utils.quote(name)

    url = f"https://delishkitchen.tv/search?q={query}"

    headers = {"User-Agent":"Mozilla/5.0"}

    r = requests.get(url,headers=headers)

    soup = BeautifulSoup(r.text,"html.parser")

    for a in soup.select("a"):
        #st.write("a:",a)

        link = a.get("href","")
        #st.write("link:",link)

        if "/recipes/" in link:

            return "https://delishkitchen.tv" + link

    return None


# =========================
# URL抽出 & レシピ取得
# =========================

@st.cache_data
def get_recipe_data(url):
    headers={"User-Agent":"Mozilla/5.0"}
    res=requests.get(url,headers=headers)
    soup=BeautifulSoup(res.text,"html.parser")

    title=soup.title.get_text().split("|")[0].strip()

    # ⭐ 人数取得
    servings = 1
    
    block = soup.select_one(".delish-recipe-ingredients")
    
    if block:
        text = block.select_one("h2").get_text(strip=True)
        m = re.search(r"\d+", text)
        if m:
            servings = int(m.group())
    
        ingredients=[]
        for item in soup.select(".ingredient"):
            name=item.select_one(".ingredient-name").get_text(strip=True)
            amount=item.select_one(".ingredient-serving").get_text(strip=True)
            ingredients.append({"name":name,"amount":amount})

    return title, ingredients, servings

# =========================
# 調味料 大さじ・小さじ 重量
# =========================

SPOON_WEIGHT = {
    "しょうゆ": {"tbsp": 18, "tsp": 6},
    "醤油": {"tbsp": 18, "tsp": 6},
    "砂糖": {"tbsp": 9, "tsp": 3},
    "みりん": {"tbsp": 18, "tsp": 6},
    "酒": {"tbsp": 15, "tsp": 5},
    "酢": {"tbsp": 15, "tsp": 5},
    "マヨネーズ": {"tbsp": 14, "tsp": 5},
    "ケチャップ": {"tbsp": 18, "tsp": 6},
    "油": {"tbsp": 12, "tsp": 4},
    "オリーブオイル": {"tbsp": 12, "tsp": 4},
    "でん粉": {"tbsp": 9, "tsp": 3},
}

def get_spoon_weight(food_name, spoon_type):

    if food_name is None:
        return None

    for key in SPOON_WEIGHT:
        if key in food_name:
            return SPOON_WEIGHT[key][spoon_type]

    return None


# =========================
# 分量解析
# =========================
import re

def parse_amount(text, food_name=None, nutrition_dict=None):

    if text is None:
        return 0

    text = str(text)

    # ① g表記
    g_match = re.search(r'(\d+(?:\.\d+)?)\s*g', text)
    if g_match:
        return float(g_match.group(1))

    # ② 大さじ
    if "大さじ" in text:
    
        # ⭐ 分数チェック
        frac_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if frac_match:
            count = float(frac_match.group(1)) / float(frac_match.group(2))
        else:
            num = re.findall(r'\d+(?:\.\d+)?', text)
            count = float(num[0]) if num else 1
    
        gram = get_spoon_weight(food_name, "tbsp")
    
        if gram is None:
            gram = 15
    
        return count * gram

    # ③ 小さじ
    if "小さじ" in text:
    
        frac_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if frac_match:
            count = float(frac_match.group(1)) / float(frac_match.group(2))
        else:
            num = re.findall(r'\d+(?:\.\d+)?', text)
            count = float(num[0]) if num else 1
    
        gram = get_spoon_weight(food_name, "tsp")
    
        if gram is None:
            gram = 5
    
        return count * gram

    # ④ 個数変換
    unit_match = re.search(r'(\d+(?:\.\d+)?)', text)

    if unit_match and food_name and nutrition_dict:

        count = float(unit_match.group(1))

        if food_name in nutrition_dict:

            gram_per_unit = nutrition_dict[food_name].get("1個(g)", None)

            if gram_per_unit is None or pd.isna(gram_per_unit) or gram_per_unit in ["", "-", 0]:
                return 0.0
    
            return count * float(gram_per_unit)

    return 0.0

# =========================
# 水や少々を除外する関数
# ========================= 
IGNORE_INGREDIENTS = [
    "水",
    "お湯",
    "熱湯",
    "氷",
    "湯",
]

IGNORE_WORDS = [
    "適量",
    "少々",
    "適宜",
]

def is_ignored_ingredient(name):
    name_n = normalize(name)

    return any(word in name_n for word in IGNORE_INGREDIENTS)

def is_ignored_amount(amount):

    if amount is None:
        return False

    amount = str(amount)

    return any(word in amount for word in IGNORE_WORDS)


# =========================
# 候補を「選択回数順」にする関数
# =========================    
mapping = load_mapping()

def get_sorted_candidates(original_name, candidates, mapping):
    if original_name not in mapping:
        return candidates

    history = mapping.get(original_name, {})
    #st.write("original_name:", original_name)
    #st.write("mapping:", mapping)
    #st.write("history:", mapping.get(original_name))


    if not isinstance(history, dict):
        return candidates

    return sorted(
        candidates,
        key=lambda x: history.get(x, 0),
        reverse=True
    )


############################
# アプリ
############################

file = st.file_uploader("スクショアップ",type=["png","jpg","jpeg"])

if file:

    pil_img = Image.open(file).convert("RGB")

    st.image(pil_img,width=400)

    img = np.array(pil_img)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    st.header("①タイトル抽出")

    title_imgs = crop_titles(img)

    titles=[]

    for i,t in enumerate(title_imgs):

        text = read_title(t)

        titles.append(text)

        st.image(t,width=300)

        st.write(text)


    st.header("②レシピURL取得")

    urls=[]

    for t in titles:

        url = search_recipe(t)

        urls.append(url)

        st.write(url)


    st.header("③材料取得")

    total_kcal=0

    for url in urls:

        if not url:
            continue

        st.markdown("---")

        title, ingredients, servings = get_recipe_data(url)
        st.subheader(title)
        st.caption(f"📖 レシピは {servings} 人分")

        col1, col2 = st.columns(2)

        with col1:
            servings_selected = st.selectbox(
                "🍽 何人分作る？",
                [1,2,3,4,5,6,8,10],
                index=[1,2,3,4,5,6,8,10].index(servings) if servings in [1,2,3,4,5,6,8,10] else 1
            )
        
        with col2:
            multiplier = st.selectbox(
                "🔢 分量倍率",
                [0.5,0.75,1,1.25,1.5,2,3],
                index=2   # 1倍
            )

        total_cal = 0
        selected_foods = {}
        if "selected_foods" not in st.session_state:
            st.session_state.selected_foods = {}

        IGNORE_INGREDIENTS = ["水", "氷", "お湯", "熱湯"]

        for i, ing in enumerate(ingredients):
            # ⭐ 食材名で除外
            if is_ignored_ingredient(ing["name"]):
                continue
        
            # ⭐ 分量で除外
            if is_ignored_amount(ing["amount"]):
                continue
            st.divider()
            st.write(f"### {ing['name']}")

            candidates = get_candidates(ing["name"], mapping)

            # ⭐ 過去データで並べ替え
            
            candidates = get_sorted_candidates(
                ing["name"],
                candidates,
                mapping
            )

            selected = None

            # ===== 候補 =====
            if candidates:
                selected = st.selectbox(
                    "候補",
                    candidates,
                    key=f"{i}_{ing['name']}_candidate",
                    label_visibility="visible"
                )
            else:
                st.warning("候補が見つかりません")
            
            # ===== 常に検索欄 =====
            search_word = st.text_input(
                "🔎 食材名を検索（候補に無い場合）",
                key=f"{i}_{ing['name']}_search"
            )
            
            if search_word:
                results = [
                    food for food in nutrition_dict
                    if normalize(search_word) in normalize(food)
                ]
            
                if results:
                    selected = st.selectbox(
                        "検索結果",
                        results,
                        key=f"{i}_{ing['name']}_manual",
                        label_visibility="visible"
                    )
                else:
                    st.error("見つかりません")

            #st.write("selected:", selected)
            if selected:
                
                default_g = parse_amount(
                ing["amount"],
                food_name=selected,
                nutrition_dict=nutrition_dict
                )

                display_g = default_g * multiplier
                
                # ===== 材料ごと倍率 =====
                colA, colB = st.columns([3,1])
                
                with colB:
                    item_multiplier = st.selectbox(
                        "倍率",
                        [0.25,0.5,0.75,1,1.25,1.5,2,3],
                        index=3,
                        key=f"{i}_{ing['name']}_multi"
                    )
                
                display_g = default_g * multiplier * item_multiplier
                
                with colA:
                    amount = st.number_input(
                        "グラム",
                        value=int(display_g),
                        step=1,
                        key=f"{i}_{ing['name']}_amt_{multiplier}_{item_multiplier}"
                    )

                
                st.session_state.selected_foods[ing["name"]] = selected

                st.caption(f"📖 レシピ分量：{ing['amount']}")
             
                st.divider()


                kcal_per100 = float(nutrition_dict[selected]["エネルギー"])
                kcal = kcal_per100 * amount / 100

                st.write(f"👉 {kcal:.1f} kcal")
                total_cal += kcal

        st.divider()
        st.subheader(f"合計カロリー: {total_cal:.1f} kcal")
        per_person = total_cal / servings_selected

        st.subheader(f"🍽 1人分カロリー: {per_person:.1f} kcal")


        if st.button("📌 レシピとして追加"):
        
            for original, selected in st.session_state.selected_foods.items():
                save_to_gsheet(original, selected)
        
            st.success("Google Sheetsに保存しました！✨")






















