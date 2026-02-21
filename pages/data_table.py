import streamlit as st
import networkx as nx
import pandas as pd

st.set_page_config(layout="wide")

st.title("Data Table")

st.write(st.session_state.graph_data.subgraph)

nodes_data = dict(st.session_state.graph_data.subgraph.nodes(data=True))
df = pd.DataFrame.from_dict(nodes_data, orient="index")

df = df.sort_values("id")

st.dataframe(df, height=1200)
