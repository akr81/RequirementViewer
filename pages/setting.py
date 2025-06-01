import streamlit as st
import hjson
import datetime
import shutil

# Streamlit のレイアウトをワイドに設定
st.set_page_config(layout="wide")

st.title("Setting")

st.write("## 現在の設定")

st.write(st.session_state.config_data)


data_key = st.session_state.app_data[st.session_state.app_name]["data"]
postfix_new_file = st.session_state.app_data[st.session_state.app_name]["postfix"]
if data_key in st.session_state.config_data:
    data_file = st.session_state.config_data[data_key]
else:
    data_file = "指定なし"
st.write(f"データファイル: {data_file}")
