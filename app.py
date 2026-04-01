
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
import uuid

st.set_page_config(
    page_title="栄養計算アプリ",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
/* 全体背景 */
.stApp {
    background: linear-gradient(180deg, #fffaf7 0%, #fffdfb 100%);
}

/* メイン幅と余白 */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 6rem;
    max-width: 1100px;
}

/* タイトル */
h1, h2, h3 {
    color: #3a312b;
    letter-spacing: 0.02em;
}

h1 {
    font-weight: 700;
    margin-bottom: 0.4rem;
}

h2, h3 {
    font-weight: 600;
}

/* 通常文字 */
p, label, div, span {
    color: #4b4038;
}

/* ボタン */
.stButton > button {
    border-radius: 14px;
    border: 1px solid #eadfd7;
    background: white;
    color: #4b4038;
    font-weight: 600;
    padding: 0.5rem 1rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
}

.stButton > button:hover {
    border-color: #d8b9a3;
    color: #8a5a44;
    transform: translateY(-1px);
}

/* 入力欄 */
.stTextInput input,
.stNumberInput input,
.stDateInput input,
textarea {
    border-radius: 12px !important;
    border: 1px solid #eadfd7 !important;
    background: #fffefe !important;
}

/* selectbox */
div[data-baseweb="select"] > div {
    border-radius: 12px !important;
    border: 1px solid #eadfd7 !important;
    min-height: 44px;
}

/* expander */
.streamlit-expanderHeader {
    font-weight: 600;
    color: #5b4d43;
    background: #fff7f2;
    border-radius: 10px;
}

/* 区切り線 */
hr {
    border: none;
    border-top: 1px solid #f0e4db;
    margin: 1rem 0;
}

/* メトリクスっぽい表示 */
.kpi-card {
    background: white;
    border: 1px solid #f0e4db;
    border-radius: 18px;
    padding: 16px 18px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.04);
    margin-bottom: 12px;
}

/* sectionカード */
.section-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid #f2e7df;
    border-radius: 20px;
    padding: 18px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.04);
    margin-bottom: 16px;
}

/* 小さめ補足 */
.soft-caption {
    color: #8a7b71;
    font-size: 0.9rem;
}

.bottom-spacer {
    height: 120px;
}
            

.bottom-bar-anchor {
    height: 0;
}


.bottom-bar-kcal {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 60px;
}

/* 親コンテナ全体を固定 */
div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.bottom-bar-anchor) {
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: 14px;
    width: min(1000px, calc(100% - 24px));
    z-index: 9999;
    background: rgba(255,255,255,0.94);
    backdrop-filter: blur(10px);
    border: 1px solid #eadfd7;
    border-radius: 18px;
    padding: 12px 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}
            

@media (max-width: 768px) {
    .meal-title {
        font-size: 1.8rem;
    }

    .meal-kcal-box {
        min-width: 100px;
        padding: 8px 12px;
    }

    .meal-kcal-value {
        font-size: 1.2rem;
    }
}
</style>
""", unsafe_allow_html=True)



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

def safe_float(x):
    try:
        return float(x)
    except:
        return 0
    
# =========================
# 文字正規化
# =========================
def normalize(text):
    return str(text).replace("\u3000","").replace(" ","").strip()


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
    #st.write(unit_match)

    if unit_match and food_name and nutrition_dict:

        count = float(unit_match.group(1))
    
        if food_name in nutrition_dict:

            gram_per_unit = nutrition_dict[food_name].get("1個(g)", None)
            
            if gram_per_unit is None or pd.isna(gram_per_unit) or gram_per_unit in ["", "-", 0]:
                return 0.0
    
            return count * float(gram_per_unit)

    return 0.0

def get_spoon_weight(food_name, spoon_type):

    if food_name is None:
        return None

    for key in SPOON_WEIGHT:
        if key in food_name:
            return SPOON_WEIGHT[key][spoon_type]

    return None

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


# =========================
# 候補を「選択回数順」にする関数
# =========================    


def get_sorted_candidates(original_name, candidates, mapping):
    if original_name not in mapping:
        return candidates

    history = mapping.get(original_name, {})

    if not isinstance(history, dict):
        return candidates

    return sorted(
        candidates,
        key=lambda x: history.get(x, 0),
        reverse=True
    )

# =========================
# 栄養データ読み込み、辞書化
# =========================
@st.cache_data
def load_nutrition():

    client = connect_gsheet()
    sheet = client.open("nutrition").sheet1

    data = sheet.get_all_values()

    df = pd.DataFrame(data[1:], columns=data[0])

    return df.set_index("食材").to_dict(orient="index")


nutrition_dict = load_nutrition()
food_master = list(nutrition_dict.keys())
def format_food_label(food):

    kcal = nutrition_dict.get(food, {}).get("エネルギー", "")
    if kcal:
        return f"{food}   ({kcal} kcal/100g)"
    return food

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

def save_meal_log_base(date, meal_type, recipe, servings=1):

    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_log")

    data = sheet.get_all_values()

    new_id = len(data)

    sheet.append_row([
        new_id,
        str(date),
        meal_type,
        recipe,
        servings   # ←追加
    ])

    return new_id

def save_ingredients(meal_id, ingredients):

    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_ingredients")

    rows = []

    for ing in ingredients:

        rows.append([
            meal_id,
            ing["food"],
            ing["gram"]
        ])

    sheet.append_rows(rows)

def calc_nutrition(ingredients, nutrition_dict):

    kcal=protein=fat=carb=0
    calcium=iron=vita=vite=vitb1=vitb2=vitc=fiber=salt=0

    for ing in ingredients:

        food = ing["food"]
        gram = ing["gram"]

        nut = nutrition_dict.get(food)
        
        if not nut:
            continue

        #st.write(ing)

        kcal += safe_float(nut["エネルギー"]) * gram / 100
        protein += safe_float(nut["たんぱく質"]) * gram / 100
        fat += safe_float(nut["脂質"]) * gram / 100
        carb += safe_float(nut["炭水化物"]) * gram / 100
        calcium += safe_float(nut["カルシウム"]) * gram / 100
        iron += safe_float(nut["鉄"]) * gram / 100
        vita += safe_float(nut["ビタミンA"]) * gram / 100
        vite += safe_float(nut["ビタミンE"]) * gram / 100
        vitb1 += safe_float(nut["ビタミンB1"]) * gram / 100
        vitb2 += safe_float(nut["ビタミンB2"]) * gram / 100
        vitc += safe_float(nut["ビタミンC"]) * gram / 100
        fiber += safe_float(nut["食物繊維"]) * gram / 100
        salt += safe_float(nut["食塩相当量"]) * gram / 100

    return {
        "kcal":kcal,
        "protein":protein,
        "fat":fat,
        "carb":carb,
        "calcium":calcium,
        "iron":iron,
        "vitA":vita,
        "vitE":vite,
        "vitB1":vitb1,
        "vitB2":vitb2,
        "vitC":vitc,
        "fiber":fiber,
        "salt":salt
    }

def divide_nutrition(nut, servings):
    if not servings or servings == 0:
        servings = 1

    return {
        "kcal": nut["kcal"] / servings,
        "protein": nut["protein"] / servings,
        "fat": nut["fat"] / servings,
        "carb": nut["carb"] / servings,
        "calcium": nut["calcium"] / servings,
        "iron": nut["iron"] / servings,
        "vitA": nut["vitA"] / servings,
        "vitE": nut["vitE"] / servings,
        "vitB1": nut["vitB1"] / servings,
        "vitB2": nut["vitB2"] / servings,
        "vitC": nut["vitC"] / servings,
        "fiber": nut["fiber"] / servings,
        "salt": nut["salt"] / servings
    }

# =========================
#meal_logシートを更新する関数
# =========================

def update_meal_log(meal_id, nut):

    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_log")

    data = sheet.get_all_values()

    for i, row in enumerate(data):

        if str(row[0]) == str(meal_id):

            sheet.update_cell(i+1, 6, nut["kcal"])
            sheet.update_cell(i+1, 7, nut["protein"])
            sheet.update_cell(i+1, 8, nut["fat"])
            sheet.update_cell(i+1, 9, nut["carb"])
            sheet.update_cell(i+1, 10, nut["calcium"])
            sheet.update_cell(i+1, 11, nut["iron"])
            sheet.update_cell(i+1, 12, nut["vitA"])
            sheet.update_cell(i+1, 13, nut["vitE"])
            sheet.update_cell(i+1, 14, nut["vitB1"])
            sheet.update_cell(i+1, 15, nut["vitB2"])
            sheet.update_cell(i+1, 16, nut["vitC"])
            sheet.update_cell(i+1, 17, nut["fiber"])
            sheet.update_cell(i+1, 18, nut["salt"])

            break

 # =========================
#meal_ingredients を読み込む関数
# =========================       
@st.cache_data
def load_meal_ingredients():
    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_ingredients")
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df



# =========================
# nutrition シートを DataFrame で読む関数
# =========================
@st.cache_data
def load_nutrition_df():
    client = connect_gsheet()
    sheet = client.open("nutrition").sheet1
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# =========================
# 保存済み meal_id の材料一覧を取る関数
# =========================
def get_meal_ingredients_by_id(meal_id):
    df = load_meal_ingredients()
    rows = df[df["meal_id"].astype(str) == str(meal_id)]

    ingredients = []
    for _, r in rows.iterrows():
        ingredients.append({
            "uid": str(uuid.uuid4()),
            "food": r["food"],
            "gram": safe_float(r["gram"])
        })
    return ingredients

# =========================
# meal_ingredients を更新する関数
# =========================
def replace_meal_ingredients(meal_id, ingredients):
    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_ingredients")

    data = sheet.get_all_values()
    header = data[0]
    rows = data[1:]

    new_rows = []
    for row in rows:
        if str(row[0]) != str(meal_id):
            new_rows.append(row)

    for ing in ingredients:
        new_rows.append([
            str(meal_id),
            ing["food"],
            ing["gram"]
        ])

    sheet.clear()
    sheet.append_row(header)
    if new_rows:
        sheet.append_rows(new_rows)

# =========================
# meal_id から1件の meal_log を取る関数
# =========================        

def get_meal_log_by_id(meal_id):
    logs = load_meal_log()
    row_df = logs[logs["id"].astype(str) == str(meal_id)]

    if row_df.empty:
        return None

    return row_df.iloc[0].to_dict()

# =========================
# recipe名・servings も更新できる関数
# =========================
def update_meal_log_full(meal_id, recipe, servings, nut):
    client = connect_gsheet()
    sheet = client.open("food_mapping").worksheet("meal_log")

    data = sheet.get_all_values()

    for i, row in enumerate(data):
        if str(row[0]) == str(meal_id):
            sheet.update_cell(i+1, 4, recipe)       # recipe
            sheet.update_cell(i+1, 5, servings)     # servings
            sheet.update_cell(i+1, 6, nut["kcal"])
            sheet.update_cell(i+1, 7, nut["protein"])
            sheet.update_cell(i+1, 8, nut["fat"])
            sheet.update_cell(i+1, 9, nut["carb"])
            sheet.update_cell(i+1, 10, nut["calcium"])
            sheet.update_cell(i+1, 11, nut["iron"])
            sheet.update_cell(i+1, 12, nut["vitA"])
            sheet.update_cell(i+1, 13, nut["vitE"])
            sheet.update_cell(i+1, 14, nut["vitB1"])
            sheet.update_cell(i+1, 15, nut["vitB2"])
            sheet.update_cell(i+1, 16, nut["vitC"])
            sheet.update_cell(i+1, 17, nut["fiber"])
            sheet.update_cell(i+1, 18, nut["salt"])
            break

# =========================
# 過去履歴を複製して登録する関数
# =========================

def copy_meal_from_history(source_meal_id, target_date, target_meal_type):
    source_log = get_meal_log_by_id(source_meal_id)
    if source_log is None:
        return False

    source_ingredients = get_meal_ingredients_by_id(source_meal_id)

    # 新しい meal_log を作成
    new_meal_id = save_meal_log_base(
        target_date,
        target_meal_type,
        source_log["recipe"],
        servings=safe_float(source_log.get("servings", 1)) or 1
    )

    # 材料コピー
    ingredients_to_save = []
    for ing in source_ingredients:
        ingredients_to_save.append({
            "food": ing["food"],
            "gram": safe_float(ing["gram"])
        })

    save_ingredients(new_meal_id, ingredients_to_save)

    # 栄養は再計算
    nutrition_dict = load_nutrition()
    total_nut = calc_nutrition(ingredients_to_save, nutrition_dict)

    servings = safe_float(source_log.get("servings", 1)) or 1
    per_person_nut = divide_nutrition(total_nut, servings)

    update_meal_log_full(
        new_meal_id,
        source_log["recipe"],
        servings,
        per_person_nut
    )

    load_meal_log.clear()
    load_meal_ingredients.clear()
    return True

# =========================
# 画面管理（遷移）
# =========================

if "page" not in st.session_state:
    st.session_state.page = "dashboard"

if "edit_meal_id" not in st.session_state:
    st.session_state.edit_meal_id = None

if "my_item_edit_name" not in st.session_state:
    st.session_state.my_item_edit_name = None


# =========================
# ダッシュボード
# =========================

def show_dashboard():



    st.title("食事記録")
    st.caption("日付ごとの食事を記録して、1日分・食事別の栄養バランスを確認できます")

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = pd.Timestamp.today()
    
    selected_date = st.date_input(
        "日付",
        value=st.session_state.selected_date,
        key="dashboard_date"
    )
    
    st.session_state.selected_date = selected_date

    st.divider()

    if st.button("📊1日分の栄養グラフ"):
        st.session_state.graph_target = "daily"
        st.session_state.page = "nutrition_graph"
        st.rerun()

    logs = load_meal_log().copy()

    if "kcal" in logs.columns:
        logs["kcal_num"] = pd.to_numeric(logs["kcal"], errors="coerce").fillna(0)
    else:
        logs["kcal_num"] = 0

    today = logs[logs["date"] == str(st.session_state.selected_date)]

    meal_icons = {
        "朝食": "🌅",
        "昼食": "☀️",
        "夕食": "🌙",
    }

    for meal in ["朝食", "昼食", "夕食"]:
        rows = today[today["meal_type"] == meal].copy()
        total_kcal = rows["kcal_num"].sum()

        # 1行目：食事名 / 空き / kcal / 編集
        col1, col2, col3, col4 = st.columns([3.6, 0.4, 1.8, 1.0], vertical_alignment="center")

        with col1:
            st.markdown(
                f'<div style="font-size: 1.9rem; font-weight: 700; line-height: 1.1; white-space: nowrap;">{meal}</div>',
                unsafe_allow_html=True
            )

        with col2:
            st.write("")

        with col3:
            st.markdown(
                f'<div style="text-align:right; font-size:1.25rem; font-weight:700; white-space: nowrap;">{total_kcal:.0f} kcal</div>',
                unsafe_allow_html=True
            )

        with col4:
            if st.button("✏編集", key=f"edit_{meal}", use_container_width=True):
                st.session_state.meal_type = meal
                st.session_state.page = "meal_add"
                st.rerun()

        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        # 2行目：登録内容
        if rows.empty:
            st.markdown(
                """
                <div style="
                    color:#8a7b71;
                    padding:10px 2px 14px 2px;
                    font-size:1rem;
                ">
                    未登録
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            for _, r in rows.iterrows():
                st.markdown(
                    f"""
                    <div style="
                        background:#fffaf7;
                        border:1px solid #f0e4db;
                        border-radius:16px;
                        padding:12px 14px;
                        margin-bottom:10px;
                    ">
                        <div style="
                            font-size:1rem;
                            font-weight:600;
                            line-height:1.5;
                            color:#3a312b;
                            margin-bottom:4px;
                        ">
                            {r['recipe']}
                        </div>
                        <div style="
                            font-size:0.95rem;
                            color:#8a7b71;
                        ">
                            {safe_float(r['kcal_num']):.0f} kcal
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # 3行目：栄養グラフ
        if st.button("栄養グラフ", key=f"graph_{meal}", use_container_width=True):
            st.session_state.meal_type = meal
            st.session_state.graph_target = "meal_type"
            st.session_state.page = "nutrition_graph"
            st.rerun()

        st.divider()



# =========================
# 栄養グラフ画面
# =========================
def show_nutrition_graph():

    logs = load_meal_log().copy()

    numeric_cols = [
        "kcal","protein","fat","carb","calcium","iron",
        "vitA","vitE","vitB1","vitB2","vitC","fiber","salt"
    ]

    for c in numeric_cols:
        if c in logs.columns:
            logs[c] = pd.to_numeric(logs[c], errors="coerce").fillna(0)
        else:
            logs[c] = 0

    today = logs[logs["date"] == str(st.session_state.selected_date)].copy()

    graph_target = st.session_state.get("graph_target", "daily")

    full_target = {
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

    if graph_target == "meal_type":
        meal_type = st.session_state.get("meal_type", "朝食")
        today = today[today["meal_type"] == meal_type].copy()

        ratio_map = {
            "朝食": 0.17,
            "昼食": 0.35,
            "夕食": 0.35
        }
        meal_ratio = ratio_map.get(meal_type, 0.35)

        target = {
            k: v * meal_ratio
            for k, v in full_target.items()
        }

        st.title(f"{meal_type} の栄養グラフ")
        st.caption(f"基準値は1日分の {meal_ratio*100:.0f}%")
    else:
        target = full_target
        st.title("1日分の栄養グラフ")

    totals = today[numeric_cols].sum()

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
        intake = totals.get(k, 0)
        base = target[k]

        ratio = intake / base * 100 if base > 0 else 0

        if k in ["kcal", "protein", "fat", "carb"]:
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
            f"{status}<br>{intake:.1f} / {base:.1f}"
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
        height=650,
        xaxis_title="基準値比 (%)",
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.8)",
        margin=dict(l=20, r=20, t=20, b=20),
        font=dict(size=14)
    )

    fig.update_traces(
        textfont_size=12,
        marker_line_width=0
    )

    st.plotly_chart(fig, use_container_width=True)

    if st.button("←戻る"):
        st.session_state.page = "dashboard"
        st.rerun()

#デリッシュキッチン検索
@st.cache_data(show_spinner=False)
def search_delish_recipes(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    q = requests.utils.quote(query)
    url = f"https://delishkitchen.tv/search?q={q}"
    st.write(query)
    st.write(url)

    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    results = []
    seen = set()

    for a in soup.select("a[href*='/recipes/']"):
        st.write(a)
        href = a.get("href", "")
        if not href or "/recipes/" not in href:
            continue

        full_url = href if href.startswith("http") else "https://delishkitchen.tv" + href
        if full_url in seen:
            continue
        seen.add(full_url)

        text = a.get_text(" ", strip=True)
        if not text:
            continue

        results.append({
            "type": "recipe",
            "title": text,
            "url": full_url
        })

    return results[:10]

#レシピ詳細取得
@st.cache_data(show_spinner=False)
def get_delish_recipe_detail(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    # タイトル
    title = ""
    title_el = soup.select_one("span.title") or soup.select_one("h1")
    if title_el:
        title = title_el.get_text(strip=True)

    # 栄養
    nutrients = {
        "kcal": 0,
        "protein": 0,
        "fat": 0,
        "carb": 0,
        "salt": 0
    }

    for li in soup.select("ul.recipe-nutrients li.recipe-nutrient"):
        name_el = li.select_one(".nutrient-name p")
        amount_el = li.select_one(".nutrient-amount p")
        if not name_el or not amount_el:
            continue

        name = name_el.get_text(strip=True)
        amount_text = amount_el.get_text(strip=True)

        num_match = re.search(r"(\d+(?:\.\d+)?)", amount_text)
        value = float(num_match.group(1)) if num_match else 0

        if name == "カロリー":
            nutrients["kcal"] = value
        elif name == "たんぱく質":
            nutrients["protein"] = value
        elif name == "脂質":
            nutrients["fat"] = value
        elif name == "炭水化物":
            nutrients["carb"] = value
        elif name == "塩分":
            nutrients["salt"] = value

    # 人数
    servings = 1
    ingredients_block = soup.select_one(".delish-recipe-ingredients")
    if ingredients_block:
        h2 = ingredients_block.select_one("h2")
        if h2:
            text = h2.get_text(strip=True)
            m = re.search(r"(\d+)", text)
            if m:
                servings = int(m.group(1))

    # 材料
    ingredients = []
    for item in soup.select(".ingredient"):
        name_el = item.select_one(".ingredient-name")
        amt_el = item.select_one(".ingredient-serving")
        if not name_el or not amt_el:
            continue

        ingredients.append({
            "name": name_el.get_text(strip=True),
            "amount": amt_el.get_text(strip=True)
        })

    return {
        "title": title,
        "url": url,
        "servings": servings,
        "ingredients": ingredients,
        "nutrients": nutrients
    }

#nutrition候補 + デリッシュ候補をまとめて返す
def search_foods_and_recipes(words):
    food_df = load_nutrition_df()

    results = {}

    for w in words:
        if not w.strip():
            continue

        food_rows = food_df[food_df["食材"].str.contains(w, na=False)].copy()

        food_items = []
        for _, row in food_rows.iterrows():
            food_items.append({
                "type": "food",
                "title": row["食材"],
                "kcal": safe_float(row.get("エネルギー", 0)),
                "row": row.to_dict()
            })

        recipe_items = []
        try:
            delish_hits = search_delish_recipes(w)
            for r in delish_hits:
                try:
                    detail = get_delish_recipe_detail(r["url"])
                    recipe_items.append({
                        "type": "recipe",
                        "title": detail["title"],
                        "kcal": detail["nutrients"]["kcal"],
                        "url": detail["url"],
                        "detail": detail
                    })
                except:
                    continue
        except:
            pass

        results[w] = food_items + recipe_items

    return results

# =========================
# 食事追加画面
# =========================

def show_meal_add():

    mapping = load_mapping()

    @st.cache_data
    def load_food_master():
    
        client = connect_gsheet()
        sheet = client.open("nutrition").sheet1
    
        data = sheet.get_all_values()
    
        df = pd.DataFrame(data[1:], columns=data[0])
    
        return df
    


    st.title(f"{st.session_state.meal_type} を追加")

    def save_multiple_to_mapping(items_to_save):
        """
        items_to_save: [(original, selected), ...]
        """
        if not items_to_save:
            return

        client = connect_gsheet()
        sheet = client.open("food_mapping").sheet1

        all_data = sheet.get_all_values()
        rows_to_append = []

        for original, selected in items_to_save:
            found = False

            for i, row in enumerate(all_data[1:], start=2):
                if len(row) >= 2 and row[0] == original and row[1] == selected:
                    count = int(row[2]) if len(row) > 2 and row[2] else 0
                    sheet.update_cell(i, 3, count + 1)
                    found = True
                    break

            if not found:
                rows_to_append.append([original, selected, 1])

        if rows_to_append:
            sheet.append_rows(rows_to_append)

        load_mapping.clear()

    # =========================
    # 検索ステップ管理
    # =========================
    
    if "search_step" not in st.session_state:
        st.session_state.search_step = 0
    
    if "search_words" not in st.session_state:
        st.session_state.search_words = []
    
    if "search_results" not in st.session_state:
        st.session_state.search_results = {}
    
    if "remaining_words" not in st.session_state:
        st.session_state.remaining_words = []
    
    if "selected_foods_temp" not in st.session_state:
        st.session_state.selected_foods_temp = []

    if "history_filter_mode" not in st.session_state:
        st.session_state.history_filter_mode = "meal_type"

    if "meal_add_recipe_selected_foods" not in st.session_state:
        st.session_state.meal_add_recipe_selected_foods = {}
    



    # =========================
    # 1検索バー
    # =========================

    if st.session_state.search_step == 0:
    
        if st.button("🔍 食材検索を開始"):
            st.session_state.search_step = 1
            st.rerun()

    #2検索ワード入力
    elif st.session_state.search_step == 1:
    
        st.subheader("検索ワード入力")
    
        words = []
    
        for i in range(10):
            w = st.text_input(f"検索{i+1}", key=f"word_{i}")
            words.append(w)
    
        if st.button("検索"):
    
            words = [w for w in words if w]
            
    #nutritionからワードを含む言葉を探しデータで返す（辞書、keyは検索したワード）
            results = search_foods_and_recipes(words)
    
            st.session_state.search_results = results
            st.session_state.remaining_words = list(results.keys())
    
            st.session_state.search_step = 2
            st.rerun()
            

    #③候補数表示
    elif st.session_state.search_step == 2:
    
        st.subheader("検索結果")
    
        for word in st.session_state.remaining_words:
            items = st.session_state.search_results[word]

            if st.button(f"{word} ({len(items)}件)", key=f"btn_{word}"):
                st.session_state.current_word = word
                st.session_state.search_step = 3
                st.rerun()

    #④候補一覧
    elif st.session_state.search_step == 3:
    
        word = st.session_state.current_word
        items = st.session_state.search_results[word]

        st.subheader(word)

        for i, item in enumerate(items):
            if item["type"] == "food":
                label = f"【食材】{item['title']} {safe_float(item['kcal']):.0f} kcal/100g"
                if st.button(label, key=f"food_{word}_{i}"):
                    st.session_state.selected_foods_temp.append(item)
                    st.session_state.remaining_words.remove(word)

                    if len(st.session_state.remaining_words) == 0:
                        st.session_state.search_step = 4
                    else:
                        st.session_state.search_step = 2

                    st.rerun()

            elif item["type"] == "recipe":
                label = f"【レシピ】{item['title']} {safe_float(item['kcal']):.0f} kcal/1人分"
                if st.button(label, key=f"recipe_{word}_{i}"):
                    st.session_state.selected_foods_temp.append(item)
                    st.session_state.remaining_words.remove(word)

                    if len(st.session_state.remaining_words) == 0:
                        st.session_state.search_step = 4
                    else:
                        st.session_state.search_step = 2

                    st.rerun()

                st.markdown(f"[レシピを開く]({item['url']})")

    #⑤最終登録確認
    elif st.session_state.search_step == 4:
        st.subheader("登録確認")

        items = st.session_state.selected_foods_temp
        nutrition_dict = load_nutrition()
        food_master = list(nutrition_dict.keys())

        save_queue = []

        for i, item in enumerate(items):
            st.divider()

            # -------------------------
            # 通常の食材候補
            # -------------------------
            if item["type"] == "food":
                st.write(f"**{item['title']}**")

                amount = st.number_input(
                    f"分量(g) {i}",
                    value=100.0,
                    step=10.0,
                    key=f"amt_food_{i}"
                )

                ratio = amount / 100
                kcal = safe_float(item["row"]["エネルギー"]) * ratio
                st.write(f"{kcal:.1f} kcal")

                save_queue.append({
                    "type": "food",
                    "title": item["title"],
                    "ingredients": [{
                        "food": item["title"],
                        "gram": amount
                    }],
                    "servings": 1
                })

            # -------------------------
            # デリッシュ候補
            # -------------------------
            elif item["type"] == "recipe":
                detail = item["detail"]
                title = detail["title"]
                url = detail["url"]
                servings = detail["servings"]
                raw_ingredients = detail["ingredients"]

                st.write(f"**{title}**")
                st.caption(f"デリッシュキッチン: 1人分 {safe_float(detail['nutrients']['kcal']):.1f} kcal")
                st.markdown(f"[レシピを開く]({url})")

                recipe_key = f"meal_add_recipe_{i}"

                with st.expander("材料と分量を確認・編集", expanded=True):
                    selected_ingredients = []
                    mapping_items_to_save = []

                    for j, ing in enumerate(raw_ingredients):
                        ing_name = ing["name"]
                        ing_amount = ing["amount"]

                        st.markdown(f"### {ing_name}")
                        st.caption(f"元の表記: {ing_amount}")

                        # =========================
                        # 自動検索候補
                        # =========================
                        candidates = [
                            food for food in food_master
                            if normalize(ing_name) in normalize(food)
                        ]

                        # mapping履歴があるなら必ず追加
                        if ing_name in mapping:
                            for saved_food in mapping[ing_name].keys():
                                if saved_food not in candidates:
                                    candidates.append(saved_food)

                        candidates = get_sorted_candidates(
                            ing_name,
                            candidates,
                            mapping
                        )

                        if not candidates:
                            candidates = food_master[:30]
                        else:
                            candidates = candidates[:50]

                        selected_food = st.selectbox(
                            "自動検索",
                            candidates,
                            format_func=format_food_label,
                            key=f"{recipe_key}_food_{j}"
                        )

                        # =========================
                        # 手動検索
                        # =========================
                        manual_search = st.text_input(
                            "手動検索",
                            key=f"{recipe_key}_search_{j}"
                        )

                        if manual_search.strip():
                            manual_candidates = [
                                food for food in food_master
                                if normalize(manual_search) in normalize(food)
                            ]

                            # 手動検索候補にも現在選択中のものを残す
                            if selected_food not in manual_candidates and selected_food in food_master:
                                manual_candidates = [selected_food] + manual_candidates

                            manual_candidates = manual_candidates[:50]

                            if manual_candidates:
                                selected_food = st.selectbox(
                                    "手動検索候補",
                                    manual_candidates,
                                    format_func=format_food_label,
                                    key=f"{recipe_key}_manual_food_{j}"
                                )
                            else:
                                st.warning("手動検索候補が見つかりません")

                        default_g = parse_amount(
                            ing_amount,
                            food_name=selected_food,
                            nutrition_dict=nutrition_dict
                        )

                        gram = st.number_input(
                            "分量（g）",
                            value=float(default_g),
                            step=1.0,
                            key=f"{recipe_key}_gram_{j}"
                        )

                        selected_ingredients.append({
                            "food": selected_food,
                            "gram": gram
                        })

                        mapping_items_to_save.append((
                            ing_name,
                            selected_food
                        ))

                    preview_nut = calc_nutrition(selected_ingredients, nutrition_dict)
                    per_person_preview = divide_nutrition(preview_nut, servings)

                    st.write(f"推定 1人分: {per_person_preview['kcal']:.1f} kcal")

                    save_queue.append({
                        "type": "recipe",
                        "title": title,
                        "ingredients": selected_ingredients,
                        "servings": servings,
                        "mapping_items": mapping_items_to_save
                    })
    
        if st.button("完了"):
            all_mapping_items = []

            for item in save_queue:
                meal_id = save_meal_log_base(
                    st.session_state.selected_date,
                    st.session_state.meal_type,
                    item["title"],
                    servings=item["servings"]
                )

                save_ingredients(meal_id, item["ingredients"])

                total_nut = calc_nutrition(item["ingredients"], nutrition_dict)
                per_person_nut = divide_nutrition(total_nut, item["servings"])

                update_meal_log(
                    meal_id,
                    per_person_nut
                )

                if item["type"] == "recipe":
                    all_mapping_items.extend(item.get("mapping_items", []))

            if all_mapping_items:
                save_multiple_to_mapping(all_mapping_items)

            st.success("登録しました")

            st.session_state.search_step = 0
            st.session_state.selected_foods_temp = []
            st.session_state.search_results = {}

            load_meal_log.clear()
            load_meal_ingredients.clear()

            st.rerun()

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("レシピサイトを検索"):
            st.session_state.page = "recipe_search"
            st.rerun()

    with col_b:
        if st.button("⭐マイアイテム"):
            st.session_state.page = "my_items"
            st.rerun()


    #履歴表示
    st.divider()

    st.subheader("📚登録履歴から追加")

    col_hist1, col_hist2 = st.columns(2)

    with col_hist1:
        if st.button(f"{st.session_state.meal_type}の履歴", use_container_width=True):
            st.session_state.history_filter_mode = "meal_type"
            st.rerun()

    with col_hist2:
        if st.button("すべての履歴", use_container_width=True):
            st.session_state.history_filter_mode = "all"
            st.rerun()

    logs = load_meal_log().copy()

    # 数値列を安全変換
    if "kcal" in logs.columns:
        logs["kcal_num"] = pd.to_numeric(logs["kcal"], errors="coerce").fillna(0)
    else:
        logs["kcal_num"] = 0

    # フィルター
    if st.session_state.history_filter_mode == "meal_type":
        history_rows = logs[
            logs["meal_type"] == st.session_state.meal_type
        ].copy()
    else:
        history_rows = logs.copy()

    # 新しい順に並べる
    if "id" in history_rows.columns:
        history_rows["id_num"] = pd.to_numeric(history_rows["id"], errors="coerce").fillna(0)
        history_rows = history_rows.sort_values("id_num", ascending=False)

    # 同じ recipe が何回も並びすぎるのが嫌なら recipe単位で最新1件だけにする
    history_rows = history_rows.drop_duplicates(subset=["recipe"], keep="first")

    if history_rows.empty:
        st.info("履歴がありません")
    else:
        for _, r in history_rows.iterrows():
            col1, col2, col3 = st.columns([4, 2, 1])

            with col1:
                st.write(f"**{r['recipe']}**")
                if st.session_state.history_filter_mode == "all":
                    st.caption(f"{r['meal_type']} / {r['date']}")

            with col2:
                st.write(f"{safe_float(r['kcal_num']):.0f} kcal")

            with col3:
                if st.button("＋", key=f"add_history_{r['id']}"):
                    ok = copy_meal_from_history(
                        source_meal_id=r["id"],
                        target_date=st.session_state.selected_date,
                        target_meal_type=st.session_state.meal_type
                    )

                    if ok:
                        st.success("登録しました")
                        st.rerun()
                    else:
                        st.error("履歴の登録に失敗しました")


    if st.button("←戻る"):
    
        st.session_state.search_step = 0
        st.session_state.search_results = {}
        st.session_state.selected_foods_temp = []
    
        st.session_state.page = "dashboard"
        st.rerun()


    logs = load_meal_log()
    target_rows = logs[
        (logs["date"] == str(st.session_state.selected_date)) &
        (logs["meal_type"] == st.session_state.meal_type)
    ]

    total_kcal = pd.to_numeric(target_rows["kcal"], errors="coerce").fillna(0).sum()
    total_count = len(target_rows)

    bottom_bar = st.container()

    st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

    with bottom_bar:
        st.markdown('<div class="bottom-bar-anchor"></div>', unsafe_allow_html=True)
        col1, col2 = st.columns([2, 5], vertical_alignment="center")

        with col1:
            st.markdown(f"""
            <div class="bottom-bar-kcal">
                <div class="soft-caption">現在の合計</div>
                <div style="font-size:1.5rem;font-weight:700;">{total_kcal:.0f} kcal</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            if st.button(
                f"登録を確認 ({total_count})",
                use_container_width=True,
                key="go_saved_confirm"
            ):
                st.session_state.page = "saved_meal_confirm"
                st.rerun()

        

# =========================
# レシピ検索画面
# =========================

def show_recipe_search():


    
    if st.session_state.get("recipe_page_init") != True:
        st.session_state.selected_foods = {}
        st.session_state.ingredients = []
        st.session_state.recipe_page_init = True

    if "manual_recipe_urls" not in st.session_state:
        st.session_state.manual_recipe_urls = []

    if "manual_recipe_url_input" not in st.session_state:
        st.session_state.manual_recipe_url_input = ""

    if "recipe_ingredients_state" not in st.session_state:
        st.session_state.recipe_ingredients_state = {}

    if "recipe_delete_target" not in st.session_state:
        st.session_state.recipe_delete_target = None
    
    st.title("デリッシュ献立スクショ → 栄養計算")
    st.caption("スクリーンショットやURLからレシピを取り込み、材料を調整して栄養計算できます")
    
    if st.button("←戻る"):
        st.session_state.recipes_current_page = {}
        st.session_state.manual_recipe_urls = []
        st.session_state.manual_recipe_url_input = ""
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
    

    

        
    nutrition_dict = load_nutrition()
    

    
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
        (220,240,820,340),
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
        #st.write(name)

        # 日本語の料理名をURLで使える形式（%E8%82%89...など）に変換
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
    # 分量解析
    # =========================
    import re
    


    


    
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
    
    
    mapping = load_mapping()
    ############################
    # アプリ
    ############################
    
    
    file = st.file_uploader("スクショアップ", type=["png", "jpg", "jpeg"])
    
    st.header("①タイトル抽出")
    
    titles = []
    
    # -------------------------
    # OCRエリア
    # -------------------------
    if file:
        pil_img = Image.open(file).convert("RGB")
    
        st.image(pil_img, width=400)
    
        img = np.array(pil_img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
        st.subheader("スクショからタイトル抽出")
    
        title_imgs = crop_titles(img)
    
        for i, t in enumerate(title_imgs):
            text = read_title(t)
    
            if text.strip():
                titles.append(text)
    
            st.image(t, width=300)
            st.write(text)
    
    # 重複削除
    titles = [t.strip() for t in titles if str(t).strip()]
    titles = list(dict.fromkeys(titles))
    
    ocr_urls = []

    if titles:
        st.header("②レシピURL取得")

        for t in titles:
            url = search_recipe(t)
            st.write(f"抽出タイトル: {t}")
            st.write(url)

            if url:
                ocr_urls.append(url)

    # -------------------------
    # URL手動追加
    # -------------------------
    st.subheader("URLを手動追加")

    if "manual_recipe_urls" not in st.session_state:
        st.session_state.manual_recipe_urls = []

    if "manual_recipe_url_input_counter" not in st.session_state:
        st.session_state.manual_recipe_url_input_counter = 0

    url_input_key = f"manual_recipe_url_input_{st.session_state.manual_recipe_url_input_counter}"
    
    manual_url = st.text_input(
        "レシピURLを入力",
        key=url_input_key
    )

    if st.button("URL追加"):
        url = manual_url.strip()
        if url:
            if "delishkitchen.tv/recipes/" in url:
                if url not in st.session_state.manual_recipe_urls:
                    st.session_state.manual_recipe_urls.append(url)
                    st.session_state.manual_recipe_url_input_counter += 1
                    st.rerun()
            else:
                st.warning("デリッシュキッチンのレシピURLを入力してください")
            st.session_state.manual_recipe_url_input = ""
            st.rerun()

    if st.session_state.manual_recipe_urls:
        st.write("追加済みURL")
        for idx, url in enumerate(st.session_state.manual_recipe_urls):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.write(url)
            with c2:
                if st.button("削除", key=f"delete_manual_url_{idx}"):
                    st.session_state.manual_recipe_urls.pop(idx)
                    st.rerun()

    urls = ocr_urls + st.session_state.manual_recipe_urls
    urls = [u for u in urls if u]
    urls = list(dict.fromkeys(urls))
    
    if urls:
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

            if url not in st.session_state.recipe_ingredients_state:
                st.session_state.recipe_ingredients_state[url] = []
                for ing in ingredients:
                    st.session_state.recipe_ingredients_state[url].append({
                        "uid": str(uuid.uuid4()),
                        "name": ing["name"],
                        "amount": ing["amount"],
                        "is_manual": False
                    })
    
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
    
          
            IGNORE_INGREDIENTS = ["水", "氷", "お湯", "熱湯"]

            if st.session_state.recipe_delete_target is not None:
                target = st.session_state.recipe_delete_target
                target_url = target["url"]
                target_uid = target["uid"]

                if target_url in st.session_state.recipe_ingredients_state:
                    st.session_state.recipe_ingredients_state[target_url] = [
                        ing for ing in st.session_state.recipe_ingredients_state[target_url]
                        if ing["uid"] != target_uid
                    ]

                st.session_state.recipe_delete_target = None
                st.rerun()
    
            editable_ingredients = st.session_state.recipe_ingredients_state[url]

            for i, ing in enumerate(editable_ingredients):
                st.divider()

                col_title, col_delete = st.columns([5, 1])

                with col_title:
                    if ing["is_manual"]:
                        st.write(f"### {ing['name']}（追加）")
                    else:
                        st.write(f"### {ing['name']}")

                with col_delete:
                    st.write("")
                    st.write("")
                    if st.button("削除", key=f"delete_ing_{url}_{ing['uid']}"):
                        st.session_state.recipe_delete_target = {
                            "url": url,
                            "uid": ing["uid"]
                        }
                        st.rerun()

                # ⭐ 食材名で除外
                if is_ignored_ingredient(ing["name"]):
                    continue
            
                # ⭐ 分量で除外
                if is_ignored_amount(ing["amount"]):
                    continue

                selected = None


                # =========================
                # 既存の取得材料
                # =========================
                if not ing["is_manual"]:
                    candidates = get_candidates(ing["name"], mapping)
                    candidates = get_sorted_candidates(
                        ing["name"],
                        candidates,
                        mapping
                    )

                    if candidates:
                        selected = st.selectbox(
                            "候補",
                            candidates,
                            format_func=format_food_label,
                            key=f"{url}_{ing['uid']}_candidate"
                        )
                    else:
                        st.warning("候補が見つかりません")

                    search_word = st.text_input(
                        "🔎 食材名を検索（候補に無い場合）",
                        key=f"{url}_{ing['uid']}_search"
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
                                key=f"{url}_{ing['uid']}_manual"
                            )
                        else:
                            st.error("見つかりません")

                    if selected:
                        default_g = parse_amount(
                            ing["amount"],
                            food_name=selected,
                            nutrition_dict=nutrition_dict
                        )

                        colA, colB = st.columns([3, 1])

                        with colB:
                            item_multiplier = st.selectbox(
                                "倍率",
                                [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3],
                                index=3,
                                key=f"{url}_{ing['uid']}_multi"
                            )

                        display_g = default_g * multiplier * item_multiplier

                        with colA:
                            amount = st.number_input(
                                "グラム",
                                value=int(display_g),
                                step=1,
                                key=f"{url}_{ing['uid']}_amt_{multiplier}_{item_multiplier}"
                            )

                        st.caption(f"📖 レシピ分量：{ing['amount']}")

                # =========================
                # 手動追加材料
                # =========================
                else:
                    search_word = st.text_input(
                        "追加する食材名を検索",
                        value=ing["name"],
                        key=f"{url}_{ing['uid']}_add_search"
                    )

                    results = []
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
                            key=f"{url}_{ing['uid']}_add_candidate"
                        )
                    else:
                        st.info("食材名を入力して候補を選んでください")

                    amount = st.number_input(
                        "グラム",
                        min_value=0.0,
                        step=1.0,
                        value=100.0,
                        key=f"{url}_{ing['uid']}_add_gram"
                    )

                if selected:
                    st.session_state[f"{url}_{ing['uid']}_gram"] = amount

                    if url not in st.session_state.selected_foods:
                        st.session_state.selected_foods[url] = {}

                    original_name = ing["name"] if ing["name"] else search_word

                    st.session_state.selected_foods[url][ing["uid"]] = {
                        "original_name": original_name,
                        "selected_food": selected
                    }

                    nut = nutrition_dict[selected]

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

                    st.write(f"👉 {safe_float(nut['エネルギー']) * amount / 100:.1f} kcal")
    
            st.divider()
            st.subheader(f"合計カロリー: {kcal:.1f} kcal")
            per_person = kcal / servings_selected

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
                "servings": servings_selected,
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
    
            if st.button("＋ 材料を追加", key=f"add_manual_ing_{url}"):
                st.session_state.recipe_ingredients_state[url].append({
                    "uid": str(uuid.uuid4()),
                    "name": "",
                    "amount": "",
                    "is_manual": True
                })
                st.rerun()    
    
            if st.button("📌 レシピとして追加", key=f"save_{url}"):

                meal = st.session_state.meal_type
                date = st.session_state.selected_date
            
                ingredients_for_save = []
            
                for uid, item in st.session_state.selected_foods.get(url, {}).items():
                    gram = st.session_state.get(f"{url}_{uid}_gram", 0)

                    ingredients_for_save.append({
                        "food": item["selected_food"],
                        "gram": gram
                    })
            
                meal_id = save_meal_log_base(
                    date,
                    meal,
                    title,
                    servings=servings_selected
                )
                
                save_ingredients(
                    meal_id,
                    ingredients_for_save
                )
                
                total_nut = calc_nutrition(
                    ingredients_for_save,
                    nutrition_dict
                )
                
                per_person_nut = divide_nutrition(total_nut, servings_selected)
                
                update_meal_log(
                    meal_id,
                    per_person_nut
                )
            
                load_meal_log.clear()
            
                st.success("保存しました")

                

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
                for uid, item in st.session_state.selected_foods.get(url, {}).items():
                    items_to_save.append((
                        item["original_name"],
                        item["selected_food"]
                    ))
                
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
        
            for url, r in recipes.items():
        
                ingredients_for_save = []
        
                for uid, item in st.session_state.selected_foods.get(url, {}).items():
                    gram = st.session_state.get(f"{url}_{uid}_gram", 0)

                    ingredients_for_save.append({
                        "food": item["selected_food"],
                        "gram": gram
                    })
        
                meal_id = save_meal_log_base(
                    date,
                    meal,
                    r["title"],
                    servings=r["servings"]
                )
                
                save_ingredients(
                    meal_id,
                    ingredients_for_save
                )
                
                total_nut = calc_nutrition(
                    ingredients_for_save,
                    nutrition_dict
                )
                
                per_person_nut = divide_nutrition(total_nut, r["servings"])
                
                update_meal_log(
                    meal_id,
                    per_person_nut
                )
        
            load_meal_log.clear()
        
            st.session_state.recipes_current_page = {}
        
            st.success(f"{meal}に{len(recipes)}レシピ追加しました")

            
            # 1. 保存したいデータをすべて一つのリストに集める
            all_items = []
            for url_key in st.session_state.selected_foods:
                for uid, item in st.session_state.selected_foods[url_key].items():
                    all_items.append((
                        item["original_name"],
                        item["selected_food"]
                    ))
            
            # 2. まとめて保存関数を1回だけ呼ぶ
            if all_items:
                save_multiple_to_gsheet(all_items)
                st.success(f"全 {len(all_items)} 件の食材データを保存しました！")
            else:
                st.warning("保存するデータがありません")

        if st.button("←topに戻る"):
            st.session_state.recipes_current_page = {}
            st.session_state.manual_recipe_urls = []
            st.session_state.manual_recipe_url_input = ""
            st.session_state.page = "dashboard"
            st.rerun()

#登録内容の確認画面
def show_saved_meal_confirm():
    st.title("登録内容の確認")

    logs = load_meal_log()

    rows = logs[
        (logs["date"] == str(st.session_state.selected_date)) &
        (logs["meal_type"] == st.session_state.meal_type)
    ].copy()

    if rows.empty:
        st.info("まだ登録がありません")

        if st.button("← 戻る"):
            st.session_state.page = "meal_add"
            st.rerun()
        return

    rows["kcal_num"] = pd.to_numeric(rows["kcal"], errors="coerce").fillna(0)

    st.subheader(f"{st.session_state.selected_date} {st.session_state.meal_type}")
    st.write(f"合計 {rows['kcal_num'].sum():.1f} kcal")

    for _, r in rows.iterrows():
        col1, col2 = st.columns([5, 1])

        with col1:
            st.write(f"**{r['recipe']}**")
            st.caption(f"{r['kcal_num']:.1f} kcal")

        with col2:
            if st.button("編集", key=f"edit_saved_{r['id']}"):
                st.session_state.edit_meal_id = r["id"]
                st.session_state.page = "saved_meal_edit"
                st.rerun()

    if st.button("← 戻る"):
        st.session_state.page = "meal_add"
        st.rerun()


#登録完了したレシピの編集画面
def show_saved_meal_edit():
    st.title("登録内容を編集")

    meal_id = st.session_state.get("edit_meal_id")
    if meal_id is None:
        st.warning("編集対象がありません")
        if st.button("← 戻る"):
            st.session_state.page = "saved_meal_confirm"
            st.rerun()
        return

    logs = load_meal_log()
    row_df = logs[logs["id"].astype(str) == str(meal_id)]

    if row_df.empty:
        st.error("対象データが見つかりません")
        if st.button("← 戻る"):
            st.session_state.page = "saved_meal_confirm"
            st.rerun()
        return

    row = row_df.iloc[0]
    nutrition_dict = load_nutrition()
    food_master = list(nutrition_dict.keys())

    edit_key = f"edit_ingredients_{meal_id}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = get_meal_ingredients_by_id(meal_id)

    recipe_name = st.text_input("料理名", value=row["recipe"])
    servings = st.number_input(
        "人数",
        min_value=1,
        step=1,
        value=int(float(row["servings"])) if str(row["servings"]).strip() else 1
    )

    delete_key = f"delete_target_{meal_id}"

    if delete_key not in st.session_state:
        st.session_state[delete_key] = None

    # 前回押された削除をここで実行
    if st.session_state[delete_key] is not None:
        delete_uid = st.session_state[delete_key]

        st.session_state[edit_key] = [
            ing for ing in st.session_state[edit_key]
            if ing["uid"] != delete_uid
        ]

        st.session_state[delete_key] = None
        st.rerun()

    def normalize(text):
        return str(text).replace("\u3000", "").replace(" ", "").strip()

    edited_ingredients = []

    for i, ing in enumerate(st.session_state[edit_key]):
        st.divider()
        st.write(f"材料 {i+1}")

        # 現在値
        current_food = ing["food"]
        uid = ing["uid"]

        # 検索ワード入力
        search_key = f"saved_edit_search_{meal_id}_{uid}"
        default_search = st.session_state.get(search_key, current_food)

        search_word = st.text_input(
            f"食材検索 {i+1}",
            value=default_search,
            key=search_key
        )

        # nutrition_dictから候補検索
        if search_word.strip():
            candidates = [
                food for food in food_master
                if normalize(search_word) in normalize(food)
            ]
        else:
            candidates = []

        # 候補が0件なら現在の食材だけは候補に残す
        if current_food not in candidates and current_food in food_master:
            candidates = [current_food] + candidates

        # 候補が多すぎると見づらいので上位50件まで
        candidates = candidates[:50]

        if not candidates:
            st.warning("候補が見つかりません。検索語を変えてください。")
            selected_food = current_food if current_food in food_master else food_master[0]
            st.write(f"現在の食材: {selected_food}")
        else:
            selected_index = candidates.index(current_food) if current_food in candidates else 0

            selected_food = st.selectbox(
                f"候補 {i+1}",
                candidates,
                index=selected_index,
                key=f"saved_edit_food_{meal_id}_{uid}"
            )

        col1, col2 = st.columns([4, 1])

        with col1:
            gram = st.number_input(
                f"グラム {i+1}",
                min_value=0.0,
                step=1.0,
                value=float(ing["gram"]),
                key=f"saved_edit_gram_{meal_id}_{uid}"
            )

        with col2:
            st.write("")
            st.write("")
            if st.button("削除", key=f"delete_ing_{meal_id}_{uid}"):
                st.session_state[delete_key] = uid
                st.rerun()

        edited_ingredients.append({
            "uid": uid,
            "food": selected_food,
            "gram": gram
        })

    if len(st.session_state[edit_key]) == 0:
        st.info("材料がありません。材料を追加してください。")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("材料を追加"):
            st.session_state[edit_key].append({
                "uid": str(uuid.uuid4()),
                "food": food_master[0],
                "gram": 100.0
            })
            st.rerun()

    with col2:
        if len(st.session_state[edit_key]) > 1:
            if st.button("最後の材料を削除"):
                st.session_state[edit_key].pop()
                st.rerun()

    preview_total_nut = calc_nutrition(edited_ingredients, nutrition_dict)
    preview_per_person = divide_nutrition(preview_total_nut, servings)

    st.subheader(f"1人分 {preview_per_person['kcal']:.1f} kcal")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("保存"):
            ingredients_to_save = [
                {
                    "food": ing["food"],
                    "gram": ing["gram"]
                }
                for ing in edited_ingredients
    ]
            replace_meal_ingredients(meal_id, ingredients_to_save)
            update_meal_log_full(
                meal_id,
                recipe_name,
                servings,
                preview_per_person
            )

            load_meal_log.clear()
            load_meal_ingredients.clear()
            del st.session_state[edit_key]
            if delete_key in st.session_state:
                st.session_state[delete_key] = None

            st.success("更新しました")
            st.session_state.page = "saved_meal_confirm"
            st.rerun()

    with col2:
        if st.button("キャンセル"):
            if edit_key in st.session_state:
                del st.session_state[edit_key]
            if delete_key in st.session_state:
                st.session_state[delete_key] = None
            st.session_state.page = "saved_meal_confirm"
            st.rerun()

#マイアイテムを新規登録
def save_my_item(item_data):
    client = connect_gsheet()
    sheet = client.open("nutrition").sheet1

    headers = sheet.row_values(1)

    row = []
    for col in headers:
        row.append(item_data.get(col, 0))

    sheet.append_row(row)
    load_nutrition.clear()
    load_nutrition_df.clear()

#マイアイテムを更新
def update_my_item(original_name, item_data):
    client = connect_gsheet()
    sheet = client.open("nutrition").sheet1

    data = sheet.get_all_values()
    headers = data[0]

    for i, row in enumerate(data[1:], start=2):
        if len(row) > 0 and row[0] == original_name:
            new_row = []
            for col in headers:
                new_row.append(item_data.get(col, 0))

            cell_range = f"A{i}:{chr(64+len(headers))}{i}"
            sheet.update(cell_range, [new_row])

            load_nutrition.clear()
            load_nutrition_df.clear()
            return True

    return False

#空欄を0にする補助関数
def empty_to_zero(x):
    if x is None:
        return 0
    if str(x).strip() == "":
        return 0
    return safe_float(x)

#マイアイテムだけ取得する関数
def get_my_items():
    df = load_nutrition_df().copy()

    if "source" not in df.columns:
        return pd.DataFrame(columns=df.columns)

    df = df[df["source"] == "my_item"].copy()
    return df

#＋ボタンで食事登録する関数
def add_my_item_to_meal(item_row, target_date, target_meal_type):
    nutrition_dict = load_nutrition()

    food_name = item_row["食材"]
    gram = safe_float(item_row.get("1個(g)", 0))

    if gram <= 0:
        return False, "1個(g) が未登録のため追加できません"

    ingredients = [{
        "food": food_name,
        "gram": gram
    }]

    meal_id = save_meal_log_base(
        target_date,
        target_meal_type,
        food_name,
        servings=1
    )

    save_ingredients(meal_id, ingredients)

    nut = calc_nutrition(ingredients, nutrition_dict)

    update_meal_log(
        meal_id,
        nut
    )

    load_meal_log.clear()
    load_meal_ingredients.clear()
    load_nutrition.clear()
    load_nutrition_df.clear()

    return True, f"{gram:.0f}g で登録しました"


#マイアイテム一覧画面
def show_my_items():
    st.title("⭐マイアイテム")

    df = get_my_items()

    keyword = st.text_input("キーワードで絞り込み")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("登録", use_container_width=True):
            st.session_state.my_item_edit_name = None
            st.session_state.page = "my_item_form"
            st.rerun()

    with col2:
        if st.button("← 戻る", use_container_width=True):
            st.session_state.page = "meal_add"
            st.rerun()

    if keyword.strip():
        df = df[df["食材"].str.contains(keyword, na=False)]

    if df.empty:
        st.info("マイアイテムはまだありません")
        return

    for _, r in df.iterrows():
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])

        with col1:
            st.write(f"**{r['食材']}**")
            gram_1 = safe_float(r.get("1個(g)", 0))
            if gram_1 > 0:
                st.caption(f"1個: {gram_1:.0f}g")
            else:
                st.caption("1個(g) 未登録")

        with col2:
            st.write(f"{safe_float(r.get('エネルギー', 0)):.1f} kcal/100g")

        with col3:
            if st.button("＋", key=f"add_my_item_{r['食材']}"):
                ok, msg = add_my_item_to_meal(
                    item_row=r,
                    target_date=st.session_state.selected_date,
                    target_meal_type=st.session_state.meal_type
                )

                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with col4:
            if st.button("編集", key=f"edit_my_item_{r['食材']}"):
                st.session_state.my_item_edit_name = r["食材"]
                st.session_state.page = "my_item_form"
                st.rerun()

#マイアイテム登録フォーム画面
def show_my_item_form():
    st.title("マイアイテム登録")

    nutrition_df = load_nutrition_df()
    edit_name = st.session_state.get("my_item_edit_name")

    edit_row = None
    if edit_name:
        rows = nutrition_df[nutrition_df["食材"] == edit_name]
        if not rows.empty:
            edit_row = rows.iloc[0]

    def get_default(col, default=""):
        if edit_row is None:
            return default
        v = edit_row.get(col, default)
        return v if str(v).strip() != "" else default

    food_name = st.text_input("メニュー名 *", value=get_default("食材", ""))

    kcal = st.text_input("100gあたりカロリー *", value=get_default("エネルギー", ""))
    protein = st.text_input("たんぱく質", value=get_default("たんぱく質", ""))
    fat = st.text_input("脂質", value=get_default("脂質", ""))
    carb = st.text_input("炭水化物", value=get_default("炭水化物", ""))
    calcium = st.text_input("カルシウム", value=get_default("カルシウム", ""))
    iron = st.text_input("鉄", value=get_default("鉄", ""))
    vitA = st.text_input("ビタミンA", value=get_default("ビタミンA", ""))
    vitE = st.text_input("ビタミンE", value=get_default("ビタミンE", ""))
    vitB1 = st.text_input("ビタミンB1", value=get_default("ビタミンB1", ""))
    vitB2 = st.text_input("ビタミンB2", value=get_default("ビタミンB2", ""))
    vitC = st.text_input("ビタミンC", value=get_default("ビタミンC", ""))
    fiber = st.text_input("食物繊維", value=get_default("食物繊維", ""))
    salt = st.text_input("食塩相当量", value=get_default("食塩相当量", ""))
    unit_g = st.text_input("1個(g)", value=get_default("1個(g)", ""))

    col1, col2 = st.columns(2)

    with col1:
        if st.button("保存", use_container_width=True):
            if not food_name.strip():
                st.error("メニュー名は必須です")
                return

            if str(kcal).strip() == "":
                st.error("100gあたりカロリーは必須です")
                return

            item_data = {
                "食材": food_name.strip(),
                "エネルギー": empty_to_zero(kcal),
                "たんぱく質": empty_to_zero(protein),
                "脂質": empty_to_zero(fat),
                "炭水化物": empty_to_zero(carb),
                "カルシウム": empty_to_zero(calcium),
                "鉄": empty_to_zero(iron),
                "ビタミンA": empty_to_zero(vitA),
                "ビタミンE": empty_to_zero(vitE),
                "ビタミンB1": empty_to_zero(vitB1),
                "ビタミンB2": empty_to_zero(vitB2),
                "ビタミンC": empty_to_zero(vitC),
                "食物繊維": empty_to_zero(fiber),
                "食塩相当量": empty_to_zero(salt),
                "1個(g)": empty_to_zero(unit_g),
                "source": "my_item"
            }

            if edit_name:
                ok = update_my_item(edit_name, item_data)
                if ok:
                    st.success("更新しました")
                else:
                    st.error("更新対象が見つかりません")
                    return
            else:
                existing = nutrition_df[nutrition_df["食材"] == food_name.strip()]
                if not existing.empty:
                    st.error("同じ名前の食材がすでにあります")
                    return

                save_my_item(item_data)
                st.success("登録しました")

            st.session_state.my_item_edit_name = None
            st.session_state.page = "my_items"
            st.rerun()

    with col2:
        if st.button("キャンセル", use_container_width=True):
            st.session_state.my_item_edit_name = None
            st.session_state.page = "my_items"
            st.rerun()

if st.session_state.page == "dashboard":
    show_dashboard()

elif st.session_state.page == "meal_add":
    show_meal_add()

elif st.session_state.page == "saved_meal_confirm":
    show_saved_meal_confirm()

elif st.session_state.page == "saved_meal_edit":
    show_saved_meal_edit()

elif st.session_state.page == "recipe_search":
    show_recipe_search()

elif st.session_state.page == "nutrition_graph":
    show_nutrition_graph()

elif st.session_state.page == "my_items":
    show_my_items()

elif st.session_state.page == "my_item_form":
    show_my_item_form()




