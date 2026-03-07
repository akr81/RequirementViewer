import streamlit as st
from src.operate_buttons import add_operate_buttons, add_node_selector
from src.page_setup import setup_page_layout_and_data  # 変更
from src.utility import (  # copy_file, get_backup_files_for_current_data のみ使用
    get_backup_files_for_current_data,
    copy_file,
    calculate_text_area_height,
    unescape_newline,
    update_source_data,
    show_backup_diff_preview,
)
import copy


# ページ全体のデータ読み込みと基本設定
page_elements = setup_page_layout_and_data("Evaporating Cloud Viewer")

# setup_page_layout_and_data から返された要素を変数に展開
color_list = page_elements["color_list"]
config_data = page_elements["config_data"]
app_data = page_elements["app_data"]
file_path = page_elements["file_path"]
requirement_data = page_elements["requirement_data"]
requirement_manager = page_elements["requirement_manager"]
graph_data = page_elements["graph_data"]
id_title_dict = page_elements["id_title_dict"]
id_title_list = page_elements["id_title_list"]
unique_id_dict = page_elements["unique_id_dict"]
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
    diagram_title = st.text_input(
        "ECタイトル",
        value=requirement_data.get("title", ""),
        key="diagram_title_input",
    )
    requirement_data["title"] = diagram_title  # タイトルを更新

    add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id)
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定

    # text フィールドが未設定の場合に title からフォールバック（旧データ互換）
    if not tmp_entity.get("text", "") and tmp_entity.get("title", ""):
        tmp_entity["text"] = tmp_entity["title"]

    st.write(tmp_entity["id"])
    if tmp_entity["id"] == "head":
        question = "共通の目的は何か？"
    elif tmp_entity["id"] == "right_shoulder" or tmp_entity["id"] == "left_shoulder":
        question = "目的は何か？"
    elif tmp_entity["id"] == "right_hand" or tmp_entity["id"] == "left_hand":
        question = "行動は何か？"
    else:
        question = "仮定・前提条件は何か？"
    tmp_entity["text"] = st.text_area(
        question,
        unescape_newline(tmp_entity.get("text", "")),
        height=calculate_text_area_height(unescape_newline(tmp_entity.get("text", ""))),
        key=f"ec_text_{selected_unique_id}",
    )

    tmp_entity["color"] = st.selectbox(
        "色",
        color_list,
        index=color_list.index(tmp_entity["color"]),
        key=f"ec_color_{selected_unique_id}",
    )

    # 更新しないが旧フォーマットを更新するために読み込む
    tmp_edges = copy.deepcopy(requirement_data["edges"])

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        no_new=True,
        no_add=True,
        no_remove=True,
        no_duplicate=True,
        tmp_edges=tmp_edges,
        display_key="text",
    )


def _render_ec_checklist(requirement_data: dict, requirement_manager, file_path: str):
    """TOCワークフロー支援チェックリストを描画する。"""
    checklist = requirement_data.get("checklist", {})
    with st.expander("✅ TOC 対立解消チェックリスト", expanded=False):
        st.caption("対立を蒸発させるためのワークフローを確認しましょう。")

        items = [
            ("q1", "共通目的（A）は双方が合意できるものか？"),
            ("q2", "各要望（B, C）はAを達成するために本当に必要か？"),
            ("q3", "各行動（D, D'）はB, Cを満たす唯一の方法か？"),
            ("q4", "各矢印の仮定を検証したか？（特に斜め線の仮定）"),
            ("q5", "仮定を無効化するインジェクション（解決策）は見つかったか？"),
        ]

        changed = False
        for key, label in items:
            old_val = checklist.get(key, False)
            new_val = st.checkbox(label, value=old_val, key=f"ec_ck_{key}")
            if new_val != old_val:
                checklist[key] = new_val
                changed = True

        if changed:
            requirement_data["checklist"] = checklist
            update_source_data(file_path, requirement_manager.requirements)
            st.rerun()

        completed = sum(1 for k, _ in items if checklist.get(k, False))
        st.progress(completed / len(items), text=f"{completed}/{len(items)} 完了")


with edit_column:
    render_edit_panel()
    _render_ec_checklist(requirement_data, requirement_manager, file_path)
    
st.session_state.graph_data = graph_data

