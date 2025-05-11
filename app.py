# app.py (st.Page と st.switch_page を使う場合)
import streamlit as st
from src.utility import load_config  # 設定ファイル読み込み用

# --- デフォルトアプリの設定読み込み ---
config_data, _ = load_config()
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


def main_landing_page():
    st.set_page_config(layout="wide", page_title="思考ツールメイン")
    st.write("サイドバーから利用したい図を選択してください。")

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
