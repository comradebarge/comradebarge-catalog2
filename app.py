import streamlit as st
import requests
import pandas as pd
import re

# --- 設定部分 ---
APP_ID = "1062630541952752738"    # アプリID
SHOP_CODE = "comradebarge"        # ショップコード

# --- テキスト処理関数（詳細情報の抽出・改良版） ---
def parse_caption(caption):
    """
    商品説明文から特定の項目を抽出する関数
    画像のフォーマット（【】など）に合わせて改良
    """
    if not caption:
        return {}

    # 1. HTMLタグを改行に変換して除去
    text = re.sub(r'<br\s*/?>', '\n', str(caption), flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    
    # 2. 抽出したい項目と、それを「どこまで読み取るか（次の見出し）」の定義
    # パターン: "見出し" の後にある文字を、"次の見出し" が来るまで全部取る
    extract_rules = [
        ("表記サイズ", r"(?:■?表記サイズ|サイズ表記)\s*(.*?)\s*(?=■?実寸サイズ|■?素材|■?色|■?状態ランク|■?状態説明|$)"),
        ("実寸サイズ", r"(?:■?実寸サイズ|実寸)\s*(.*?)\s*(?=■?素材|■?色|■?状態ランク|■?状態説明|$)"),
        ("状態ランク", r"(?:■?状態ランク|商品ランク)\s*(.*?)\s*(?=■?状態説明|■?管理番号|$)"),
        ("状態説明",   r"(?:■?状態説明|コンディション)\s*(.*?)\s*(?=■?管理番号|■?商品番号|$)")
    ]
    
    extracted = {}
    for key, pattern in extract_rules:
        # re.DOTALL で改行も含めて検索
        match = re.search(pattern, text, re.DOTALL)
        if match:
            # 前後の空白を除去して格納
            content = match.group(1).strip()
            # もし中身が空なら「-」にする
            extracted[key] = content if content else "-"
        else:
            extracted[key] = "-"
            
    return extracted

# --- 楽天APIからデータを取得する関数 ---
@st.cache_data(ttl=3600)
def search_rakuten_items(keyword="", min_price=None, max_price=None, sort_type="standard"):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    
    sort_params = {
        "標準": "standard",
        "価格が高い順": "-itemPrice",
        "価格が安い順": "+itemPrice",
        "新着順": "-updateTimestamp"
    }
    
    params = {
        "applicationId": APP_ID,
        "shopCode": SHOP_CODE,
        "keyword": keyword,
        "format": "json",
        "imageFlag": 1,
        "hits": 30,
        "sort": sort_params.get(sort_type, "standard")
    }
    
    if min_price and min_price > 0: params["minPrice"] = min_price
    if max_price and max_price < 1000000: params["maxPrice"] = max_price

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        items = []
        if "Items" in data:
            for item in data["Items"]:
                i = item["Item"]
                # 画像を高画質化
                image_url = i["mediumImageUrls"][0]["imageUrl"].split("?")[0] if i.get("mediumImageUrls") else "https://via.placeholder.com/300?text=No+Image"
                
                # 詳細情報を抽出
                details = parse_caption(i.get("itemCaption", ""))
                
                items.append({
                    "name": i["itemName"],
                    "price": i["itemPrice"],
                    "image": image_url,
                    "details": details # 抽出済みデータ
                })
        return pd.DataFrame(items)

    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return pd.DataFrame()

# --- アプリ画面のデザイン ---
def main():
    st.set_page_config(page_title="COMRADE 商品カタログ", layout="wide")
    
    st.markdown("""
        <style>
        .stButton>button {
            background-color: #BF0000;
            color: white;
            border-radius: 5px;
            width: 100%;
        }
        .price-tag {
            font-size: 1.2em;
            font-weight: bold;
            color: #BF0000;
            margin-bottom: 5px;
        }
        /* 詳細情報のデザイン */
        .info-box {
            background-color: #f9f9f9;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #eee;
            margin-bottom: 10px;
        }
        .info-title {
            font-weight: bold;
            color: #333;
            border-bottom: 2px solid #ddd;
            margin-bottom: 5px;
            padding-bottom: 2px;
        }
        .info-content {
            font-size: 0.95em;
            color: #555;
            white-space: pre-wrap; /* 改行をそのまま表示 */
        }
        </style>
    """, unsafe_allow_html=True)

    st.title(f"🛍️ COMRADE 商品カタログ")

    # サイドバー設定
    with st.sidebar:
        st.header("🔍 検索メニュー")
        keyword = st.text_input("キーワード", "")
        price_min = st.number_input("下限 (円)", value=0, step=1000)
        price_max = st.number_input("上限 (円)", value=1000000, step=10000)
        sort_order = st.selectbox("並び順", ["標準", "価格が高い順", "価格が安い順", "新着順"])
        st.divider()
        search_btn = st.button("検索")

    # データ取得
    if search_btn or 'df_items' not in st.session_state:
        with st.spinner('データを更新中...'):
            df = search_rakuten_items(keyword, price_min, price_max, sort_order)
            st.session_state['df_items'] = df
    
    df = st.session_state['df_items']

    # 表示処理
    if df.empty:
        st.warning("商品が見つかりませんでした。")
    else:
        st.markdown(f"**{len(df)}** 件を表示中")
        st.divider()
        
        cols = st.columns(4)
        for idx, row in df.iterrows():
            with cols[idx % 4]:
                with st.container(border=True):
                    st.image(row['image'], use_container_width=True)
                    st.markdown(f"<div class='price-tag'>¥{row['price']:,}</div>", unsafe_allow_html=True)
                    # 商品名（長すぎる場合は省略）
                    display_name = row['name'][:40] + "..." if len(row['name']) > 40 else row['name']
                    st.markdown(f"**{display_name}**")
                    
                    # 詳細ポップアップ
                    with st.popover("詳細を見る"):
                        c1, c2 = st.columns([1, 1.5])
                        with c1:
                            st.image(row['image'])
                        with c2:
                            st.markdown(f"### ¥{row['price']:,}")
                            st.write(row['name'])
                        
                        st.divider()
                        
                        # 抽出データの表示エリア
                        d = row['details']
                        
                        # HTMLを使って見やすくレイアウト
                        html_content = f"""
                        <div class='info-box'>
                            <div class='info-title'>■ 表記サイズ</div>
                            <div class='info-content'>{d['表記サイズ']}</div>
                        </div>
                        <div class='info-box'>
                            <div class='info-title'>■ 実寸サイズ</div>
                            <div class='info-content'>{d['実寸サイズ']}</div>
                        </div>
                        <div class='info-box'>
                            <div class='info-title'>■ 状態ランク</div>
                            <div class='info-content'>{d['状態ランク']}</div>
                        </div>
                        <div class='info-box'>
                            <div class='info-title'>■ 状態説明</div>
                            <div class='info-content'>{d['状態説明']}</div>
                        </div>
                        """
                        st.markdown(html_content, unsafe_allow_html=True)

if __name__ == "__main__":
    main()