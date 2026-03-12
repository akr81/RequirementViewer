import streamlit as st
from src.operate_buttons import add_operate_buttons, add_node_selector
from src.page_setup import setup_page_layout_and_data  # 変更
from src.bulk_input import render_bulk_input_ui
from src.utility import (  # copy_file, get_backup_files_for_current_data のみ使用
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    show_backup_diff_preview,
)
import uuid
import copy


# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data("Strategy and Tactics Tree Viewer")

# setup_page_layout_and_data から返された要素を変数に展開
color_list = page_elements["color_list"]
config_data = page_elements["config_data"]
app_data = page_elements["app_data"]
file_path = page_elements["file_path"]
requirement_data = page_elements["requirement_data"]
nodes = page_elements["nodes"]
edges = page_elements["edges"]  # tmp_edges の元データとして必要
requirement_manager = page_elements["requirement_manager"]
graph_data = page_elements["graph_data"]
id_title_dict = page_elements["id_title_dict"]
unique_id_dict = page_elements["unique_id_dict"]
id_title_list = page_elements["id_title_list"]
selected_unique_id = page_elements["selected_unique_id"]
selected_entity = page_elements["selected_entity"]

# 編集用カラムとPlantUMLコードを page_elements から取得
edit_column = page_elements["edit_column"]
plantuml_code = page_elements["plantuml_code"]

@st.fragment
def render_edit_panel():
    """右側操作パネルの描画（部分再描画対応）"""
    title_column, file_selector_column = st.columns([4, 4])
    with title_column:
        st.write("### データ編集")
    with file_selector_column:
        # ファイル選択boxを表示
        backup_files = get_backup_files_for_current_data()
        st.selectbox(
            "ファイルを選択",
            backup_files,
            0,
            label_visibility="collapsed",
            key="selected_backup_file",
        )
    show_backup_diff_preview(requirement_data)
    # ダイアグラムのタイトルを表示
    diagram_title = st.text_input(
        "S&Tタイトル",
        value=requirement_data.get("title", ""),
        key="diagram_title_input",
    )
    requirement_data["title"] = diagram_title  # タイトルを更新

    # --- タブ切り替え: 個別入力 / 一括入力 ---
    tab_individual, tab_bulk = st.tabs(["✏️ 個別入力", "📝 一括入力"])

    with tab_individual:
        _render_individual_edit()

    with tab_bulk:
        render_bulk_input_ui(
            nodes=requirement_data.get("nodes", []),
            requirement_manager=requirement_manager,
            file_path=file_path,
            type_list=["S&T"],
            display_key="id",
            page_key_prefix="stt",
            content_field="id",
            metadata_columns=[
                {"key": "color", "name": "色", "type": str, "default": "None"},
            ],
        )

def _render_individual_edit():
    """個別エンティティ編集タブの内容を描画する。"""
    add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id)


    # 直接データ操作はせず、コピー(uuidは異なる)に対して操作する
    tmp_entity = copy.deepcopy(selected_entity) or {}
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")
    # 古いデータにフィールドが欠けている場合のフォールバック
    for field in ("id", "necessary_assumption", "strategy", "parallel_assumption", "tactics", "sufficient_assumption"):
        tmp_entity.setdefault(field, "")

    # 後でボタンを配置する
    top_button_container = st.container()

    tmp_entity["id"] = st.text_input(
        "ID",
        tmp_entity.get("id", ""),
        key=f"stt_id_{selected_unique_id}",
    )
    tmp_entity["necessary_assumption"] = st.text_area(
        "なぜこの変化が必要か？",
        unescape_newline(tmp_entity.get("necessary_assumption", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("necessary_assumption", ""))),
        key=f"stt_necessary_{selected_unique_id}",
    )
    
    tmp_entity["strategy"] = st.text_area(
        "**戦略：何がこの変化の具体的な目的なのか？**",
        unescape_newline(tmp_entity.get("strategy", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("strategy", ""))),
        key=f"stt_strategy_{selected_unique_id}",
    )
    tmp_entity["parallel_assumption"] = st.text_area(
        "なぜこの戦術をとるのか？",
        unescape_newline(tmp_entity.get("parallel_assumption", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("parallel_assumption", ""))),
        key=f"stt_parallel_{selected_unique_id}",
    )
    tmp_entity["tactics"] = st.text_area(
        "**戦術：どのようにこの変化を達成するのか？**",
        unescape_newline(tmp_entity.get("tactics", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("tactics", ""))),
        key=f"stt_tactics_{selected_unique_id}",
    )
    tmp_entity["sufficient_assumption"] = st.text_area(
        "なぜより詳細な具体策とアクションが必要なのか？",
        unescape_newline(tmp_entity.get("sufficient_assumption", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("sufficient_assumption", ""))),
        key=f"stt_sufficient_{selected_unique_id}",
    )
    tmp_entity["color"] = st.selectbox(
        "色",
        color_list,
        index=color_list.index(tmp_entity.get("color", "None")),
        key=f"stt_color_{selected_unique_id}",
    )

    # 接続元の関係を取得
    # 直接edgeは操作せず、コピーに対して操作する
    tmp_edges = copy.deepcopy(requirement_data["edges"])
    for i, edge in enumerate(tmp_edges):
        if edge["source"] != selected_unique_id:
            continue
        # unique_id_dict に存在しない ID の場合は "None" にフォールバック
        current_label = unique_id_dict.get(edge["destination"], "None")
        edge["destination"] = id_title_dict[
            st.selectbox(
                "接続先",
                id_title_list,
                id_title_list.index(current_label),
                key=f"destination{i}",
            )
        ]

    # 関係追加の操作があるため、1つは常に表示
    destination_unique_id = id_title_dict[
        st.selectbox("接続先(新規)", id_title_list, index=id_title_list.index("--- 未選択 ---"))
    ]  # 末尾に追加用の空要素を追加

    new_edge = {
        "source": tmp_entity["unique_id"],
        "destination": destination_unique_id,
        "type": "arrow",
    }

    # 上部のボタンを配置
    with top_button_container:
        add_operate_buttons(
            selected_unique_id,
            tmp_entity,
            requirement_manager,
            file_path,
            id_title_dict,
            unique_id_dict,
            tmp_edges=tmp_edges,
            new_edges=[new_edge],
            key_suffix="top"  # 重複エラー回避用
        )

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
        new_edges=[new_edge],
        key_suffix="bottom"  # 重複エラー回避用
    )


with edit_column:
    render_edit_panel()
    
st.session_state.graph_data = graph_data
