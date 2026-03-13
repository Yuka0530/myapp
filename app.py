
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
import plotly.graph_objects as go

# =========================
# Google Sheets 接続
# =========================

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
# 食事記録読み込み
# =========================

@st.cache_data
def load_meal_log():

    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_log")

    data = sheet.get_all_values()

    df = pd.DataFrame(data[1:], columns=data[0])

    return df

# =========================
#meal_logシートに保存する関数
# =========================

def save_meal_log(date, meal_type, title, kcal):

    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_log")
    st.write("gsheet:",date,meal_type,title,kcal)

    sheet.append_row([
        str(date),
        meal_type,
        title,
        kcal,
        protein,
        fat,
        carb,
        calcium,
        iron,
        vita,
        vite,
        vitb1,
        vitb2,
        vitc,
        fiber,
        salt
    ])

# =========================
# 画面管理（遷移）
# =========================

if "page" not in st.session_state:
    st.session_state.page = "dashboard"


# =========================
# ダッシュボード
# =========================

def show_dashboard():



    st.title("食事記録")

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = pd.Timestamp.today()
    
    selected_date = st.date_input(
        "日付",
        value=st.session_state.selected_date,
        key="dashboard_date"
    )
    
    st.session_state.selected_date = selected_date

    st.subheader("朝食")

    if st.button("✏ 朝食を編集"):
        st.session_state.meal_type = "朝食"
        st.session_state.page = "meal_add"
        st.rerun()

    st.subheader("昼食")

    if st.button("✏ 昼食を編集"):
        st.session_state.meal_type = "昼食"
        st.session_state.page = "meal_add"
        st.rerun()

    st.subheader("夕食")

    if st.button("✏ 夕食を編集"):
        st.session_state.meal_type = "夕食"
        st.session_state.page = "meal_add"
        st.rerun()

    st.divider()

    if st.button("栄養グラフ"):
        st.session_state.page = "nutrition_graph"
        st.rerun()


    
    logs = load_meal_log()

    today = logs[logs["date"] == str(st.session_state.selected_date)]
    
    for meal in ["朝食","昼食","夕食"]:
    
        st.subheader(meal)
    
        rows = today[today["meal_type"] == meal]
    
        for _, r in rows.iterrows():
            st.write(f"{r['recipe']} {float(r['kcal']):.0f} kcal")

    #for meal in ["朝食","昼食","夕食"]:

        #st.subheader(meal)
    
        #if meal in st.session_state.get("meal_data",{}):
            #for r in st.session_state.meal_data[meal]:
                #st.write(f"{r['title']}  {r['kcal']:.0f} kcal")

# =========================
# 栄養グラフ画面
# =========================
def show_nutrition_graph():

    st.title("栄養グラフ")

    logs = load_meal_log()
    #st.write(logs.dtypes)

    numeric_cols = [
        "kcal","protein","fat","carb","calcium","iron",
        "vitA","vitE","vitB1","vitB2","vitC","fiber","salt"
    ]
    
    for c in numeric_cols:
        logs[c] = pd.to_numeric(logs[c], errors="coerce").fillna(0)

    today = logs[logs["date"] == str(st.session_state.selected_date)]

    totals = today[numeric_cols].sum()

    target = {
        "kcal":1600,
        "protein":60,
        "fat":44,
        "carb":240,
        "fiber":18,
        "salt":6.5,
        "calcium":700,
        "iron":8,
        "vitA":750,
        "vitE":6.5,
        "vitB1":1,
        "vitB2":1.2,
        "vitC":100
    }

    upper_limit = {
        "vitA":2700,
        "vitE":700,
        "iron":40,
        "calcium":2500
    }

    labels = {
        "kcal":"エネルギー",
        "protein":"たんぱく質",
        "fat":"脂質",
        "carb":"炭水化物",
        "fiber":"食物繊維",
        "salt":"塩分",
        "calcium":"カルシウム",
        "iron":"鉄",
        "vitA":"ビタミンA",
        "vitE":"ビタミンE",
        "vitB1":"ビタミンB1",
        "vitB2":"ビタミンB2",
        "vitC":"ビタミンC"
    }

    fig = go.Figure()

    y_labels = []
    ratios = []
    colors = []
    texts = []

    for k in target:

        intake = totals.get(k,0)
        base = target[k]

        ratio = intake/base*100 if base > 0 else 0

        if k in ["kcal","protein","fat","carb"]:
        
            low = 90
            high = 120
        
        elif k in upper_limit:
        
            low = 100
            high = min(upper_limit[k] / base * 100, 200)

        elif k == "salt":
        
            low = 0
            high = 100
        
        else:
        
            low = 100
            high = None

        if ratio < low:
            status = "不足"
            color = "#4da3ff"
        elif high and ratio > high:
            status = "過剰"
            color = "#ff6b3d"
        else:
            status = "適正"
            color = "#66bb44"

        y_labels.append(labels[k])
        ratios.append(ratio)
        colors.append(color)

        texts.append(
            f"{status}<br>"
            f"{intake:.1f} / {base}"
        )

        if high:
            fig.add_shape(
                type="rect",
                x0=low,
                x1=high,
                y0=len(y_labels)-1.4,
                y1=len(y_labels)-0.6,
                fillcolor="rgba(120,200,120,0.25)",
                line_width=0
            )

        fig.add_shape(
            type="line",
            x0=100,
            x1=100,
            y0=len(y_labels)-1.4,
            y1=len(y_labels)-0.6,
            line=dict(
                color="gray",
                width=2,
                dash="dot"
            )
        )

    fig.add_trace(go.Bar(
        x=ratios,
        y=y_labels,
        orientation="h",
        marker_color=colors,
        text=texts,
        textposition="outside"
    ))

    fig.update_layout(
        height=600,
        xaxis_title="基準値比 (%)",
        yaxis=dict(autorange="reversed"),
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

    

    if st.button("←戻る"):
        st.session_state.page="dashboard"
        st.rerun()


# =========================
# 食事追加画面
# =========================

def show_meal_add():
    @st.cache_data
    def load_food_master():
    
        client = connect_gsheet()
        sheet = client.open("nutrition").sheet1
    
        data = sheet.get_all_values()
    
        df = pd.DataFrame(data[1:], columns=data[0])
    
        return df
    
    
    def search_foods(words):
    
        df = load_food_master()
    
        results = {}
    
        for w in words:
    
            if w.strip() == "":
                continue
    
            r = df[df["食材"].str.contains(w, na=False)]
    
            results[w] = r
    
        return results    
    



    st.title(f"{st.session_state.meal_type} を追加")

    # 検索UI表示フラグ
    if "show_search" not in st.session_state:
        st.session_state.show_search = False

    if "search_results" not in st.session_state:
        st.session_state.search_results = {}

    if "selected_food" not in st.session_state:
        st.session_state.selected_food = None

    # =========================
    # 検索バー
    # =========================

    if st.text_input("🔍 料理名・食材名で検索", key="search_bar"):
        st.session_state.show_search = True


    # =========================
    # ②検索ワード10個入力
    # =========================

    if st.session_state.show_search:

        st.info("一度に10件検索できます")

        words = []

        for i in range(10):

            w = st.text_input(
                f"検索{i+1}",
                key=f"word_{i}"
            )

            words.append(w)

        if st.button("検索"):

            st.session_state.search_results = search_foods(words)

            st.rerun()


    # =========================
    # ③候補数表示
    # =========================

    if st.session_state.search_results:

        for word, df in st.session_state.search_results.items():

            if df.empty:
                continue

            if st.button(f"{word} ({len(df)}件)", key=f"btn_{word}"):

                st.session_state.selected_word = word
                st.rerun()


    # =========================
    # ④候補一覧
    # =========================

    if "selected_word" in st.session_state:

        word = st.session_state.selected_word
        df = st.session_state.search_results[word]

        st.subheader(word)

        for i,row in df.iterrows():

            food = row["食材"]
            kcal = row["エネルギー"]

            if st.button(f"{food} {kcal} kcal", key=f"food_{i}"):

                st.session_state.selected_food = row
                st.rerun()


    # =========================
    # ⑤登録確認
    # =========================

    if st.session_state.selected_food is not None:

        food = st.session_state.selected_food

        st.divider()

        st.subheader("登録確認")

        st.write(food["食材"])
        st.write(f"{food['エネルギー']} kcal")

        if st.button("登録"):
            
            save_meal_log(
                st.session_state.selected_date,
                st.session_state.meal_type,
                food["食材"],
                food["エネルギー"],
                food["たんぱく質"],
                food["脂質"],
                food["炭水化物"],
                food["カルシウム"],
                food["鉄"],
                food["ビタミンA"],
                food["ビタミンE"],
                food["ビタミンB1"],
                food["ビタミンB2"],
                food["ビタミンC"],
                food["食物繊維"],
                food["食塩相当量"]
            )

            st.success("登録しました")

            st.session_state.selected_food = None
            st.session_state.search_results = {}

            load_meal_log.clear()

    if st.button("レシピサイトを検索"):
        st.session_state.page = "recipe_search"
        st.rerun()

    if st.button("←戻る"):
        st.session_state.page = "dashboard"
        st.rerun()

# =========================
# レシピ検索画面
# =========================

def show_recipe_search():

    
    st.set_page_config(layout="wide")

    
    if st.session_state.get("recipe_page_init") != True:
        st.session_state.selected_foods = {}
        st.session_state.ingredients = []
        st.session_state.recipe_page_init = True
    
    st.title("デリッシュ献立スクショ → 栄養計算")
    
    if st.button("←戻る"):
        st.session_state.recipes_current_page = {}
        st.session_state.page = "meal_add"
        st.rerun()

    
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
            #st.write(i,row)
            if row[0] == original and row[1] == selected:
                count = int(row[2]) if len(row) > 2 and row[2] else 0
                sheet.update_cell(i, 3, count + 1)
                return
    
        # 新規追加
        st.write("append:", original, selected)
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
        "コチュジャン": {"tbsp": 18, "tsp": 7},
        "味噌": {"tbsp": 18, "tsp": 6},
        "みそ": {"tbsp": 18, "tsp": 6},
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
        # 分数チェック 例: 1/2個
        frac_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        
        if frac_match and food_name and nutrition_dict:
        
            count = float(frac_match.group(1)) / float(frac_match.group(2))
        
            if food_name in nutrition_dict:
        
                gram_per_unit = nutrition_dict[food_name].get("1個(g)", None)
        
                if gram_per_unit is None or pd.isna(gram_per_unit) or gram_per_unit in ["", "-", 0]:
                    return 0.0
        
                return count * float(gram_per_unit)
        
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
    
        selected_foods = {}
        if "selected_foods" not in st.session_state:
            st.session_state.selected_foods = {}
    
        for url in urls:

            kcal = 0
            protein = 0
            fat = 0
            carb = 0
            calcium = 0
            iron = 0
            vita = 0
            vite = 0
            vitb1 = 0
            vitb2 = 0
            vitc = 0
            fiber = 0
            salt = 0
    
            if not url:
                continue

            #レシピをすべて追加のための辞書作成
            if "recipes_current_page" not in st.session_state:
                st.session_state.recipes_current_page = {}
    
            st.markdown("---")
    
            title, ingredients, servings = get_recipe_data(url)
            st.subheader(title)
            st.caption(f"📖 レシピは {servings} 人分")
    
            col1, col2 = st.columns(2)
    
            with col1:
                servings_selected = st.selectbox(
                    "🍽 何人分作る？",
                    [1,2,3,4,5,6,8,10],
                    index=[1,2,3,4,5,6,8,10].index(servings) if servings in [1,2,3,4,5,6,8,10] else 1,
                    key=f"servings_{url}"
                )
            
            with col2:
                multiplier = st.selectbox(
                    "🔢 分量倍率",
                    [0.5,0.75,1,1.25,1.5,2,3],
                    index=2,   # 1倍
                    key=f"multi_{url}"
                )
    
            total_cal = 0
    
    
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

                def format_food_label(food):
                    kcal = nutrition_dict.get(food, {}).get("エネルギー", "")
                    if kcal:
                        return f"{food}   ({kcal} kcal/100g)"
                    return food
    
                # ===== 候補 =====
                if candidates:
                    selected = st.selectbox(
                        "候補",
                        candidates,
                        format_func=format_food_label,
                        key=f"{url}_{i}_{ing['name']}_candidate",
                        label_visibility="visible"
                    )
                else:
                    st.warning("候補が見つかりません")
                
                # ===== 常に検索欄 =====
                search_word = st.text_input(
                    "🔎 食材名を検索（候補に無い場合）",
                    key=f"{url}_{i}_{ing['name']}_search"
                )
                
                if search_word:
                    results = [
                        food for food in nutrition_dict
                        if normalize(search_word) in normalize(food)
                    ]
                
                    if results:
                          selected = st.selectbox(
                            "候補",
                            results,
                            format_func=format_food_label,
                            key=f"{url}_{i}_{ing['name']}_manual",
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
                            key=f"{url}_{i}_{ing['name']}_multi"
                        )
                    
                    display_g = default_g * multiplier * item_multiplier
                    
                    with colA:
                        amount = st.number_input(
                            "グラム",
                            value=int(display_g),
                            step=1,
                            key=f"{url}_{i}_{ing['name']}_amt_{multiplier}_{item_multiplier}"
                        )
    
                    
                    if url not in st.session_state.selected_foods:
                        st.session_state.selected_foods[url] = {}
                    st.session_state.selected_foods[url][ing["name"]] = selected
    
                    st.caption(f"📖 レシピ分量：{ing['amount']}")
                 
                    st.divider()

                    nut = nutrition_dict[selected]

                    def safe_float(x):
                        try:
                            return float(x)
                        except:
                            return 0

                    kcal += safe_float(nut["エネルギー"]) * amount / 100
                    protein += safe_float(nut["たんぱく質"]) * amount / 100
                    fat += safe_float(nut["脂質"]) * amount / 100
                    carb += safe_float(nut["炭水化物"]) * amount / 100
                    calcium += safe_float(nut["カルシウム"]) * amount / 100
                    iron += safe_float(nut["鉄"]) * amount / 100
                    vita += safe_float(nut["ビタミンA"]) * amount / 100
                    vite += safe_float(nut["ビタミンE"]) * amount / 100
                    vitb1 += safe_float(nut["ビタミンB1"]) * amount / 100
                    vitb2 += safe_float(nut["ビタミンB2"]) * amount / 100
                    vitc += safe_float(nut["ビタミンC"]) * amount / 100
                    fiber += safe_float(nut["食物繊維"]) * amount / 100
                    salt += safe_float(nut["食塩相当量"]) * amount / 100
    
                    st.write(f"👉 {kcal:.1f} kcal")
                    total_cal += kcal
    
            st.divider()
            st.subheader(f"合計カロリー: {total_cal:.1f} kcal")
            per_person = total_cal / servings_selected

            per_person_kcal = kcal / servings_selected
            per_person_protein = protein / servings_selected
            per_person_fat = fat / servings_selected
            per_person_carb = carb / servings_selected
            per_person_calcium = calcium / servings_selected
            per_person_iron = iron / servings_selected
            per_person_vita = vita / servings_selected
            per_person_vite = vite / servings_selected
            per_person_vitb1 = vitb1 / servings_selected
            per_person_vitb2 = vitb2 / servings_selected
            per_person_vitc = vitc / servings_selected
            per_person_fiber = fiber / servings_selected
            per_person_salt = salt / servings_selected

            #この画面のレシピすべて追加用にappend
            st.session_state.recipes_current_page[url] = {
                "title": title,
                "kcal": per_person_kcal,
                "protein": per_person_protein,
                "fat": per_person_fat,
                "carb": per_person_carb,
                "calcium": per_person_calcium,
                "iron": per_person_iron,
                "vitA": per_person_vita,
                "vitE": per_person_vite,
                "vitB1": per_person_vitb1,
                "vitB2": per_person_vitb2,
                "vitC": per_person_vitc,
                "fiber": per_person_fiber,
                "salt": per_person_salt
            }
    
            st.subheader(f"🍽 1人分カロリー: {per_person_kcal:.1f} kcal")
    
    
            if st.button("📌 レシピとして追加", key=f"save_{url}"):
                meal = st.session_state.meal_type

                if "meal_data" not in st.session_state:
                    st.session_state.meal_data = {
                        "朝食": [],
                        "昼食": [],
                        "夕食": []
                    }
            
                recipe = {
                    "title": title,
                    "kcal": per_person_kcal
                }
            
                st.session_state.meal_data[meal].append(recipe)
                

               
                save_meal_log(
                    st.session_state.selected_date,
                    meal,
                    title,
                    per_person_kcal
                )

                load_meal_log.clear()
            
                st.success(f"{meal}に追加しました")

                def save_all_to_gsheet(selected_items_list):
                    """
                    selected_items_list: [(original, selected), (original, selected), ...] 
                    という形式のリストを受け取って一括保存する
                    """
                    client = connect_gsheet()
                    sheet = client.open("food_mapping").sheet1
                    
                    # 現在のデータを1回だけ取得
                    all_data = sheet.get_all_values()
                    
                    # 新しく追加する行を溜めるリスト
                    rows_to_append = []
                    
                    for original, selected in selected_items_list:
                        st.write(original,selected)
                        found = False
                        # 既存データにあるか確認（ここをループ内で回すと重いですが、API通信よりはマシです）
                        for i, row in enumerate(all_data[1:], start=2):
                            #st.write(i,row)
                            if row[0] == original and row[1] == selected:
                                # 既存のカウントアップは、本当は batch_update が理想ですが
                                # まずは簡易的にここだけ通信
                                count = int(row[2]) if len(row) > 2 and row[2] else 0
                                sheet.update_cell(i, 3, count + 1)
                                found = True
                                break
                        
                        if not found:
                            rows_to_append.append([original, selected, 1])
                    
                    # 溜まった新規行を「1回の通信」でドバッと追加
                    if rows_to_append:
                        sheet.append_rows(rows_to_append)

                # 保存したいデータを一旦リストにまとめる
                items_to_save = []
                for original, selected in st.session_state.selected_foods.get(url, {}).items():
                    items_to_save.append((original, selected))
                
                # まとめて一回だけ関数を呼ぶ！
                save_all_to_gsheet(items_to_save)
 
                #for original, selected in st.session_state.selected_foods.get(url, {}).items():
                    #st.write(original,selected)
                    #save_to_gsheet(original, selected)

                st.session_state.recipe_page_init = False
            
                st.success("Google Sheetsに保存しました！✨")

                #st.session_state.page = "dashboard"
                #st.rerun()

        # =========================
        # 一括保存用関数
        # =========================
        def save_multiple_to_gsheet(items_to_save):
            """
            items_to_save: [(original, selected), ...] のリスト
            """
            if not items_to_save:
                return
        
            client = connect_gsheet()
            sheet = client.open("food_mapping").sheet1
            
            # 全データを1回だけ取得（通信節約）
            all_data = sheet.get_all_values()
            new_rows = []
        
            # プログレスバーを出すとユーザーが安心します
            progress_text = "Google Sheetsに保存中..."
            my_bar = st.progress(0, text=progress_text)
        
            for idx, (original, selected) in enumerate(items_to_save):
                st.write(idx,original,selected)
                found = False
                # 既存データにあるかチェック
                for i, row in enumerate(all_data, start=1):
                    if len(row) >= 2 and row[0] == original and row[1] == selected:
                        count = int(row[2]) if len(row) > 2 and row[2] else 0
                        sheet.update_cell(i, 3, count + 1) # ここは1回通信が発生
                        found = True
                        break
                
                if not found:
                    new_rows.append([original, selected, 1])
                
                # 進捗更新
                my_bar.progress((idx + 1) / len(items_to_save), text=progress_text)
        
            # 新規データを一括で末尾に追加（ここが劇的に速い！）
            if new_rows:
                sheet.append_rows(new_rows)
            
            my_bar.empty()

        # =========================
        # ボタン側の処理
        # =========================
        if st.button("📌 この画面のレシピをすべて追加"):
        
            meal = st.session_state.meal_type
            date = st.session_state.selected_date
        
            recipes = st.session_state.get("recipes_current_page", {})
        
            client = connect_gsheet()
            sheet = client.open("food_mapping").worksheet("meal_log")
        
            rows_to_save = []
        
            for r in recipes.values():
                
                # gsheet保存用
                rows_to_save.append([
                    str(date),
                    meal,
                    r["title"],
                    r["kcal"],
                    r["protein"],
                    r["fat"],
                    r["carb"],
                    r["calcium"],
                    r["iron"],
                    r["vitA"],
                    r["vitE"],
                    r["vitB1"],
                    r["vitB2"],
                    r["vitC"],
                    r["fiber"],
                    r["salt"]
                ])
        
            # ⭐ 一括保存（高速）
            if rows_to_save:
                sheet.append_rows(rows_to_save)
        
            load_meal_log.clear()
            st.session_state.recipes_current_page = {}
        
            st.success(f"{meal}に{len(recipes)}レシピ追加しました")

            
            # 1. 保存したいデータをすべて一つのリストに集める
            all_items = []
            for url_key in st.session_state.selected_foods:
                for original, selected in st.session_state.selected_foods[url_key].items():
                    all_items.append((original, selected))
            
            # 2. まとめて保存関数を1回だけ呼ぶ
            if all_items:
                save_multiple_to_gsheet(all_items)
                st.success(f"全 {len(all_items)} 件の食材データを保存しました！")
            else:
                st.warning("保存するデータがありません")

        if st.button("←topに戻る"):
            st.session_state.recipes_current_page = {}
            st.session_state.page = "dashboard"
            st.rerun()



if st.session_state.page == "dashboard":
    show_dashboard()

elif st.session_state.page == "meal_add":
    show_meal_add()

elif st.session_state.page == "recipe_search":
    show_recipe_search()

elif st.session_state.page == "nutrition_graph":
    show_nutrition_graph()





















































































