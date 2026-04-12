import streamlit as st

from src.file_io import save_config

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

PARAM_DESCRIPTIONS = {
    "plantuml": "PlantUML サーバーの URL",
    "viewer_height": "ビューア高さ(px)",
    "upstream_filter_max": "上流ノードの最大表示数",
    "downstream_filter_max": "下流ノードの最大表示数",
    "backup_retention_days": "バックアップ保持日数",
    "requirement_data": "Requirement Diagram のデータファイル",
    "strategy_and_tactics_data": "Strategy and Tactics Tree のデータファイル",
    "current_reality_tree_data": "Current Reality Tree のデータファイル",
    "process_flow_diagram_data": "Process Flow Diagram のデータファイル",
    "evaporating_cloud_data": "Evaporating Cloud のデータファイル",
    "ccpm_data": "CCPM のデータファイル",
    "multi_project_fever_data": "フィーバーチャートのデータファイル",
    "last_used_page": "最後に使用したページ",
}

NUMERIC_KEYS = {
    "viewer_height",
    "upstream_filter_max",
    "downstream_filter_max",
    "backup_retention_days",
}

config_data = st.session_state.config_data

st.write("## 設定")
st.caption("値を編集して保存すると `config.hjson` に反映されます。")

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

if st.button("保存", key="save_settings"):
    for key in NUMERIC_KEYS:
        if key in updated_config:
            try:
                updated_config[key] = int(updated_config[key])
            except (ValueError, TypeError):
                pass

    save_config(updated_config)
    st.session_state.config_data = updated_config
    st.toast("設定を保存しました。")

st.divider()

data_key = st.session_state.app_data[st.session_state.app_name]["data"]
data_file = config_data.get(data_key, "未設定")
st.write(f"**現在のデータファイル:** `{data_file}`")
