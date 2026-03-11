import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.markdown(
    """
    <style>
    .stMainBlockContainer { padding-top: 3.0rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Data Table")

graph = st.session_state.graph_data.subgraph

# ノードデータをDataFrameに変換
nodes_data = dict(graph.nodes(data=True))
df = pd.DataFrame.from_dict(nodes_data, orient="index")

# エッジ情報から各ノードの接続元(From)・接続先(To)を集計
from_map = {}  # destination → [source labels]
to_map = {}    # source → [destination labels]

for src, dst, _ in graph.edges(data=True):
    src_label = nodes_data.get(src, {}).get("title") or nodes_data.get(src, {}).get("text") or nodes_data.get(src, {}).get("id") or src
    dst_label = nodes_data.get(dst, {}).get("title") or nodes_data.get(dst, {}).get("text") or nodes_data.get(dst, {}).get("id") or dst
    to_map.setdefault(src, []).append(str(dst_label))
    from_map.setdefault(dst, []).append(str(src_label))

# From/To カラムを追加
df["From"] = df.index.map(lambda uid: ", ".join(from_map.get(uid, [])))
df["To"] = df.index.map(lambda uid: ", ".join(to_map.get(uid, [])))

# unique_id列がindexに入っているのでカラムとしても保持
if "unique_id" not in df.columns:
    df.insert(0, "unique_id", df.index)

# id列があればソート
if "id" in df.columns:
    df = df.sort_values("id")

# テーブル高さをデータ行数に合わせる（1行あたり約35px＋ヘッダー分）
table_height = min(len(df) * 35 + 50, 1200)
st.dataframe(df, height=table_height, width="stretch", hide_index=True)

# CSV保存ボタン
csv_data = df.to_csv(index=False, encoding="utf-8-sig")
st.download_button(
    "📥 CSVダウンロード",
    data=csv_data,
    file_name="data_table.csv",
    mime="text/csv",
    key="download_csv",
)
