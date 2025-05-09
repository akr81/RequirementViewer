import streamlit as st
from src.utility import load_colors, load_config, load_app_data


def initialize_page(app_name: str):
    # 色のリストを読み込む
    color_list = load_colors()

    # アプリ名を設定
    st.session_state.app_name = app_name

    # ページの設定
    st.set_page_config(
        layout="wide",
        page_title=st.session_state.app_name,
        initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
    )

    # configファイルを読み込む
    config_data, demo = load_config()
    st.session_state.config_data = config_data
    app_data = load_app_data()
    st.session_state.app_data = app_data

    return color_list, config_data, demo, app_data
