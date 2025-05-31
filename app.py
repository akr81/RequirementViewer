# app.py (st.Page と st.switch_page を使う場合)
import streamlit as st
from src.utility import (
    load_config,
    start_plantuml_server,
)  # 設定ファイル読み込み用とPlantUMLサーバ起動用

# --- デフォルトアプリの設定読み込み ---
config_data = load_config()
AVAILABLE_APP_PAGES = {  # 表示名とページファイルパスのマッピング
    "Current Reality Tree": "pages/current_reality_tree.py",  # pages/ ディレクトリ内のパス
    # ... 他のアプリ ...
}
DEFAULT_APP_DISPLAY_NAME_KEY = (
    "default_app_display_name_on_startup"  # config.hjson 内のキー
)
default_app_display_name = config_data.get(
    DEFAULT_APP_DISPLAY_NAME_KEY, "Current Reality Tree"
)


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
    # PlantUMLサーバを起動（キャッシュされるので再度起動されません）
    # この処理はアプリケーション起動時に一度だけ行われるのが望ましい
    if not ("www.plantuml.com" in config_data.get("plantuml", "")):
        start_plantuml_server()

    st.set_page_config(layout="wide", page_title="思考ツールメイン")
    st.write("サイドバーから利用したい図を選択してください。")

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
        if default_app_display_name in AVAILABLE_APP_PAGES:
            page_to_switch = AVAILABLE_APP_PAGES[default_app_display_name]
            print(
                f"デフォルトアプリ '{default_app_display_name}' ({page_to_switch}) に遷移します。"
            )
            try:
                st.switch_page(page_to_switch)  # Streamlit 1.29+
            except Exception as e:
                st.error(f"ページ切り替えに失敗しました: {e}。手動で選択してください。")
        else:
            st.warning(
                f"デフォルトアプリ '{default_app_display_name}' が見つかりません。"
            )


if __name__ == "__main__":
    # (必要な共通初期設定、st.session_stateへの設定など)
    # from src.page_setup import main_app_initial_setup
    # main_app_initial_setup() # config_dataなどをロードしてセッションに設定

    main_landing_page()
