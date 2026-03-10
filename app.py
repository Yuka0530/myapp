
import streamlit as st
import cv2
import pytesseract
import requests
import json
import re
from PIL import Image
from bs4 import BeautifulSoup
import numpy as np

st.set_page_config(layout="wide")

st.title("デリッシュ献立スクショ → 栄養計算")

############################
# タイトル部分切り出し
############################

def crop_titles(img):

    h, w, _ = img.shape

    titles = []

    coords = [
    (220,240,820,320),
    (220,510,820,590),
    (220,730,820,810),
    (220,1000,1080)
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
# Google検索
############################

def search_recipe(name):

    query = f"site:delishkitchen.tv {name}"

    url = f"https://www.google.com/search?q={query}"

    headers={"User-Agent":"Mozilla/5.0"}

    r = requests.get(url,headers=headers)

    soup = BeautifulSoup(r.text,"html.parser")

    for a in soup.select("a"):

        link = a.get("href","")

        if "delishkitchen.tv/recipes" in link:

            return link.split("&")[0].replace("/url?q=","")

    return None


############################
# JSON取得
############################

def get_recipe_json(url):

    headers={"User-Agent":"Mozilla/5.0"}

    r = requests.get(url,headers=headers)

    soup = BeautifulSoup(r.text,"html.parser")

    scripts = soup.find_all("script",type="application/ld+json")

    for s in scripts:

        data=json.loads(s.string)

        if isinstance(data,dict) and data.get("@type")=="Recipe":

            return data

    return None


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

        data=get_recipe_json(url)

        if not data:
            continue

        st.subheader(data["name"])

        for ing in data["recipeIngredient"]:

            st.write(ing)

        if "nutrition" in data:

            kcal=data["nutrition"].get("calories")

            if kcal:

                st.write("カロリー:",kcal)

                num=float(re.findall(r"\d+",kcal)[0])

                total_kcal+=num


    st.header("献立合計カロリー")

    st.write(total_kcal,"kcal")
    






