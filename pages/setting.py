import streamlit as st
from src.file_io import load_config, save_config

st.set_page_config(layout="wide")
st.markdown(
    """
    <style>
    .stMainBlockContainer { padding-top: 3.0rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Setting")

# 各設定キーの説明を定義
PARAM_DESCRIPTIONS = {
    "plantuml": "PlantUMLサーバーのURL",
    "viewer_height": "図ビューアの高さ（px）",
    "upstream_filter_max": "上流ノードの最大表示数",
    "downstream_filter_max": "下流ノードの最大表示数",
    "backup_retention_days": "バックアップ保持日数（自動削除）",
    "requirement_data": "要求図のデータファイルパス",
    "strategy_and_tactics_data": "S&Tツリーのデータファイルパス",
    "current_reality_tree_data": "CRTのデータファイルパス",
    "process_flow_diagram_data": "PFDのデータファイルパス",
    "evaporating_cloud_data": "ECのデータファイルパス",
    "ccpm_data": "CCPMのデータファイルパス",
    "last_used_page": "最後に使用したページ",
}

# 数値型のキー（text_inputではなくnumber_inputを使う）
NUMERIC_KEYS = {
    "viewer_height",
    "upstream_filter_max",
    "downstream_filter_max",
    "backup_retention_days",
}

config_data = st.session_state.config_data

st.write("## 設定の編集")
st.caption("値を変更して「保存」ボタンを押すと config.hjson に反映されます。")

# 編集用のフォーム
updated_config = {}
for key, value in config_data.items():
    description = PARAM_DESCRIPTIONS.get(key, "")
    col_key, col_value, col_desc = st.columns([2, 3, 3])

    with col_key:
        st.text(key)
    with col_desc:
        st.caption(description)
    with col_value:
        if key in NUMERIC_KEYS:
            updated_config[key] = st.number_input(
                key,
                value=int(value) if value else 0,
                label_visibility="collapsed",
                key=f"setting_{key}",
            )
        else:
            updated_config[key] = st.text_input(
                key,
                value=str(value) if value else "",
                label_visibility="collapsed",
                key=f"setting_{key}",
            )

if st.button("💾 保存", key="save_settings"):
    # 数値型を適切に変換
    for key in NUMERIC_KEYS:
        if key in updated_config:
            try:
                updated_config[key] = int(updated_config[key])
            except (ValueError, TypeError):
                pass

    save_config(updated_config)
    st.session_state.config_data = updated_config
    st.toast("設定を保存しました ✅")

st.divider()

# 現在のデータファイル情報
data_key = st.session_state.app_data[st.session_state.app_name]["data"]
if data_key in config_data:
    data_file = config_data[data_key]
else:
    data_file = "指定なし"
st.write(f"**現在のデータファイル:** `{data_file}`")
