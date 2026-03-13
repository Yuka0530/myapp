
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

    today = logs[logs["date"] == str(st.session_state.selected_date)]

    totals = today.sum(numeric_only=True)

    recommended = {
        "kcal":2000,
        "protein":65,
        "fat":60,
        "carb":300,
        "calcium":650,
        "iron":7.5,
        "vitA":900,
        "vitE":6,
        "vitB1":1.4,
        "vitB2":1.6,
        "vitC":100,
        "fiber":20,
        "salt":7
    }

    data = []

    for k,v in recommended.items():

        intake = totals[k]

        percent = intake / v * 100

        data.append({
            "栄養素":k,
            "摂取率":percent
        })

    df = pd.DataFrame(data)

    st.bar_chart(df.set_index("栄養素"))

    if st.button("←戻る"):
        st.session_state.page="dashboard"
        st.rerun()


# =========================
# 食事追加画面
# =========================

def show_meal_add():

    st.title(f"{st.session_state.meal_type} を追加")

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
    
            st.subheader(f"🍽 1人分カロリー: {per_person:.1f} kcal")
    
    
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
                    "kcal": per_person
                }
            
                st.session_state.meal_data[meal].append(recipe)
                
                #meal_logシートに保存する関数
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
               
                save_meal_log(
                    st.session_state.selected_date,
                    meal,
                    title,
                    per_person
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






































































