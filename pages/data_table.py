import streamlit as st
import networkx as nx
import pandas as pd

# Streamlit のレイアウトをワイドに設定
st.set_page_config(layout="wide")

st.title("Data Table")

st.write(st.session_state.graph_data.subgraph)

# グラフをDataFrameに変換
nodes_data = dict(st.session_state.graph_data.subgraph.nodes(data=True))
df = pd.DataFrame.from_dict(nodes_data, orient="index")

# dfをid列でソート
df = df.sort_values("id")

# データテーブルを表示, 高さを800pxに設定する
st.dataframe(df, height=1200)
