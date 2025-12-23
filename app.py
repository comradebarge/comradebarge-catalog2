import streamlit as st
import requests
import pandas as pd
import re
import time

# --- 設定部分 ---
APP_ID = "1062630541952752738"    # アプリID
SHOP_CODE = "comradebarge"        # ショップコード

# --- テキスト処理関数（修正版） ---
def parse_caption(caption):
    """
    商品説明文から情報を抽出する関数
    修正点: 「状態」というキーワードが「状態ランク」と誤認しないよう削除しました
    """
    if not caption:
        return {}

    text = re.sub(r'<br\s*/?>', '\n', str(caption), flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    
    # 抽出したい項目の定義
    target_keywords = {
        "表記サイズ": ["表記サイズ", "サイズ表記"],
        "実寸サイズ": ["実寸サイズ", "実寸"],
        "状態ランク": ["状態ランク", "商品ランク"], 
        # ★修正: ここから「状態」を削除しました
        "状態説明":   ["状態説明", "コンディション"]
    }
    
    # 区切りとなるその他のキーワード
    stop_keywords = ["素材", "色", "カラー", "付属品", "備考", "管理番号", "商品番号", "注意事項", "状態ランク注意事項"]
    
    all_keywords = []
    for k, v_list in target_keywords.items():
        all_keywords.extend(v_list)
    all_keywords.extend(stop_keywords)
    
    # テキスト内のキーワード位置を特定
    positions = []
    for kw in all_keywords:
        # 見出しの前にある記号などを考慮して検索
        matches = list(re.finditer(f"(?:^|\\s|■|】|\\|){re.escape(kw)}", text))
        for m in matches:
            positions.append({
                "start": m.start(),
                "end": m.end(),
                "name": kw
            })
    
    positions.sort(key=lambda x: x["start"])
    
    extracted = {}
    
    # 各項目の内容を抽出
    for target_key, aliases in target_keywords.items():
        current_pos = None
        # 最も適したキーワード位置を探す
        for p in positions:
            if p["name"] in aliases:
                current_pos = p
                break
        
        if current_pos:
            start_index = current_pos["end"]
            end_index = len(text)
            
            # 次のキーワードが始まる場所を終了位置とする
            for p in positions:
                if p["start"] > start_index:
                    end_index = p["start"]
                    break
            
            content = text[start_index:end_index]
            
            # クリーニング処理
            content = content.strip()
            content = re.sub(r'^[:：\]】]+', '', content).strip()
            content = re.sub(r'[\[【]+$', '', content).strip()
            content = content.replace('"', '') # 不要なダブルクォーテーション削除
            
            if not content or content in ["【】", "[]", "()"]:
                extracted[target_key] = "-"
            else:
                extracted[target_key] = content
        else:
            extracted[target_key] = "-"

    return extracted

# --- 楽天API連携（全件取得対応） ---
@st.cache_data(ttl=3600)
def search_rakuten_items(keyword="", min_price=None, max_price=None, sort_type="standard"):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    
    sort_params = {
        "標準": "standard",
        "価格が高い順": "-itemPrice",
        "価格が安い順": "+itemPrice",
        "新着順": "-updateTimestamp"
    }
    
    base_params = {
        "applicationId": APP_ID,
        "shopCode": SHOP_CODE,
        "keyword": keyword,
        "format": "json",
        "imageFlag": 1,
        "hits": 30,
        "sort": sort_params.get(sort_type, "standard")
    }
    
    if min_price and min_price > 0: base_params["minPrice"] = min_price
    if max_price and max_price < 1000000: base_params["maxPrice"] = max_price

    all_items = []
    page = 1
    max_pages = 30 # 最大取得ページ数（安全のため制限）
    
    progress_text = "データを取得中..."
    my_bar = st.progress(0, text=progress_text)

    try:
        while page <= max_pages:
            params = base_params.copy()
            params["page"] = page
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                break
                
            data = response.json()
            
            if "Items" in data:
                page_count = data.get("pageCount", 1)
                
                for item in data["Items"]:
                    i = item["Item"]
                    image_url = i["mediumImageUrls"][0]["imageUrl"].split("?")[0] if i.get("mediumImageUrls") else "https://via.placeholder.com/300?text=No+Image"
                    details = parse_caption(i.get("itemCaption", ""))
                    
                    all_items.append({
                        "name": i["itemName"],
                        "price": i["itemPrice"],
                        "image": image_url,
                        "details": details
                    })
                
                progress_percent = min(page / page_count, 1.0)
                my_bar.progress(progress_percent, text=f"取得中... {page}/{page_count}ページ ({len(all_items)}件)")

                if page >= page_count:
                    break
                page += 1
                time.sleep(0.1)
            else:
                break
        
        my_bar.empty()
        return pd.DataFrame(all_items)

    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return pd.DataFrame(all_items)

# --- 画面表示 ---
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
            font-size: 1.1em;
            font-weight: bold;
            color: #BF0000;
            margin-bottom: 2px;
        }
        .info-box {
            background-color: #f9f9f9;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #eee;
            margin-bottom: 8px;
        }
        .info-title {
            font-weight: bold;
            color: #333;
            border-bottom: 2px solid #ddd;
            margin-bottom: 4px;
            padding-bottom: 2px;
            font-size: 0.9em;
        }
        .info-content {
            font-size: 0.9em;
            color: #555;
            white-space: pre-wrap;
        }
        
        /* スマホ用4列強制CSS */
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
            overflow-x: auto;
        }
        div[data-testid="stColumn"] {
            flex: 1 1 0px !important;
            min-width: 0px !important;
            padding: 0 2px !important;
        }
        @media (max-width: 640px) {
            .price-tag { font-size: 0.8rem; }
            p, span, div { font-size: 0.7rem; }
            button { padding: 0.2rem !important; font-size: 0.7rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.title(f"🛍️ COMRADE 商品カタログ")

    with st.sidebar:
        st.header("🔍 検索メニュー")
        keyword = st.text_input("キーワード", "")
        price_min = st.number_input("下限 (円)", value=0, step=1000)
        price_max = st.number_input("上限 (円)", value=1000000, step=10000)
        sort_order = st.selectbox("並び順", ["標準", "価格が高い順", "価格が安い順", "新着順"])
        st.divider()
        search_btn = st.button("検索")

    if search_btn or 'df_items' not in st.session_state:
        df = search_rakuten_items(keyword, price_min, price_max, sort_order)
        st.session_state['df_items'] = df
    
    df = st.session_state['df_items']

    if df.empty:
        st.warning("商品が見つかりませんでした。")
    else:
        st.markdown(f"**全 {len(df)} 件** を表示中")
        st.divider()
        
        cols_per_row = 4
        for i in range(0, len(df), cols_per_row):
            row_items = df.iloc[i : i + cols_per_row]
            cols = st.columns(cols_per_row)
            
            for idx, (_, row) in enumerate(row_items.iterrows()):
                with cols[idx]:
                    with st.container(border=True):
                        st.image(row['image'], use_container_width=True)
                        st.markdown(f"<div class='price-tag'>¥{row['price']:,}</div>", unsafe_allow_html=True)
                        
                        short_name = row['name'][:15] + "..." if len(row['name']) > 15 else row['name']
                        st.caption(short_name)
                        
                        with st.popover("詳細"):
                            c1, c2 = st.columns([1, 1.5])
                            with c1:
                                st.image(row['image'])
                            with c2:
                                st.markdown(f"### ¥{row['price']:,}")
                                st.write(row['name'])
                            
                            st.divider()
                            d = row['details']
                            
                            html_content = f"""
                            <div class='info-box'>
                                <div class='info-title'>■ 表記サイズ</div>
                                <div class='info-content'>{d.get('表記サイズ', '-')}</div>
                            </div>
                            <div class='info-box'>
                                <div class='info-title'>■ 実寸サイズ</div>
                                <div class='info-content'>{d.get('実寸サイズ', '-')}</div>
                            </div>
                            <div class='info-box'>
                                <div class='info-title'>■ 状態説明</div>
                                <div class='info-content'>{d.get('状態説明', '-')}</div>
                            </div>
                            """
                            st.markdown(html_content, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
