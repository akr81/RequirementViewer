# app.py (st.Page と st.switch_page を使う場合)
import streamlit as st
from src.utility import (
    load_config,
    start_plantuml_server,
)  # 設定ファイル読み込み用とPlantUMLサーバ起動用

# --- デフォルトアプリの設定読み込み ---
config_data = load_config()  # 設定ファイルをロード

# アプリの内部名とページファイルパスのマッピング
AVAILABLE_APP_PAGES = {
    "Current Reality Tree Viewer": "pages/current_reality_tree.py",
    "Evaporating Cloud Viewer": "pages/evaporating_cloud.py",
    "Process Flow Diagram Viewer": "pages/process_flow_diagram.py",
    "Requirement Diagram Viewer": "pages/requirement_diagram.py",
    "Strategy and Tactics Tree Viewer": "pages/strategy_and_tactics.py",
}
DEFAULT_APP_INTERNAL_NAME = "Current Reality Tree Viewer"  # デフォルトページの内部名
LAST_USED_PAGE_KEY = "last_used_page"  # config.hjson 内のキー
last_used_page_name = config_data.get(LAST_USED_PAGE_KEY, DEFAULT_APP_INTERNAL_NAME)


@st.dialog("注意")
def display_warning_dialog():
    message = """
PlantUMLの外部サーバを使用する設定となっています。

入力するデータにご注意ください。
"""
    st.warning(message)
    _, button_column, _ = st.columns([2, 1, 2])  # ボタン用の列を作成
    with button_column:
        if st.button("OK", key="warning_close_button"):
            st.session_state.show_warning_dialog = False
            st.rerun()
        # 確認待ち
        st.stop()


def main_landing_page():
    st.set_page_config(layout="wide", page_title="思考ツールメイン")
    st.write("サイドバーから利用したい図を選択してください。")

    # PlantUMLサーバを起動（キャッシュされるので再度起動されません）
    # この処理はアプリケーション起動時に一度だけ行われるのが望ましい
    if not ("www.plantuml.com" in config_data.get("plantuml", "")):
        start_plantuml_server()

    # PlantUMLが外部の公開サーバを使用している場合の注意喚起
    # セッションステートでダイアログの表示状態を管理
    if "show_warning_dialog" not in st.session_state:
        st.session_state.show_warning_dialog = True

    if st.session_state.show_warning_dialog and "www.plantuml.com" in config_data.get(
        "plantuml", ""
    ):
        display_warning_dialog()
    # ダイアログは初回のみ表示
    st.session_state.show_warning_dialog = False

    # --- 自動遷移ロジック ---
    if "redirect_attempted" not in st.session_state:
        st.session_state.redirect_attempted = True  # 無限ループ防止

        # 遷移先ページを決定
        page_to_switch_name = last_used_page_name
        if page_to_switch_name not in AVAILABLE_APP_PAGES:
            st.warning(
                f"最後に使用したページ '{page_to_switch_name}' が見つかりません。"
                f"デフォルトの '{DEFAULT_APP_INTERNAL_NAME}' を開きます。"
            )
            page_to_switch_name = DEFAULT_APP_INTERNAL_NAME

        # ページ遷移
        page_to_switch_path = AVAILABLE_APP_PAGES[page_to_switch_name]
        print(f"ページ '{page_to_switch_name}' ({page_to_switch_path}) に遷移します。")
        try:
            st.switch_page(page_to_switch_path)
        except Exception as e:
            st.error(f"ページ切り替えに失敗しました: {e}。手動で選択してください。")


if __name__ == "__main__":
    # (必要な共通初期設定、st.session_stateへの設定など)
    # from src.page_setup import main_app_initial_setup
    # main_app_initial_setup() # config_dataなどをロードしてセッションに設定

    main_landing_page()
