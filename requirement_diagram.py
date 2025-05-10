import streamlit as st
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
from src.diagram_configs import *
from src.page_setup import initialize_page, load_and_prepare_data
import hjson
import os
import uuid
import copy
import shutil
import datetime


@st.cache_data
def load_entity_types() -> list[str]:
    """Load entity types from JSON file.

    Returns:
        list[str]: List of entity types
    """
    with open(os.path.join("setting", "entity_types.json"), "r", encoding="utf-8") as f:
        entity_types = hjson.load(f)
    return entity_types


@st.cache_data
def load_relation_types() -> list[str]:
    """Load relation types from JSON file.

    Returns:
        list[str]: List of relation types
    """
    with open(
        os.path.join("setting", "relation_types.json"), "r", encoding="utf-8"
    ) as f:
        relation_types = hjson.load(f)
    return relation_types


@st.cache_data
def load_note_types() -> list[str]:
    """Load note types from JSON file.

    Returns:
        list[str]: List of entity types
    """
    with open(os.path.join("setting", "note_types.json"), "r", encoding="utf-8") as f:
        note_types = hjson.load(f)
    return note_types


color_list, config_data, demo, app_data, plantuml_process = initialize_page(
    "Requirement Diagram Viewer"
)


# エンティティタイプと関係タイプを読み込む
entity_types = load_entity_types()
relation_types = load_relation_types()
note_types = load_note_types()


if demo:
    st.title(f"{st.session_state.app_name} (demo)")

    # テキストでJSONファイルのパスを指定(デフォルトはdefault.json)
    # file_path = st.text_input("JSONファイルのパスを入力してください", "default.json")
    # 元に戻すボタンを表示
    if st.button("元に戻す"):
        # バックアップのJSONファイルをデフォルトに上書きコピー
        shutil.copyfile("default/back.json", "default/requirement.json")
        st.rerun()

data_key = st.session_state.app_data[st.session_state.app_name]["data"]
file_path = config_data[data_key]


# データの読み込みと準備
(
    requirement_data,
    nodes,
    edges,
    requirement_manager,
    graph_data,
    id_title_dict,
    unique_id_dict,
    id_title_list,
    _,
    scale,
    selected_unique_id,
    upstream_distance,
    downstream_distance,
    selected_entity,
) = load_and_prepare_data(file_path, st.session_state.app_name)

if not selected_entity:
    selected_entity = DEFAULT_ENTITY_GETTERS[st.session_state.app_name](entity_types)

# Requirement diagram表示とデータ編集のレイアウトを設定
diagram_column, edit_column = st.columns([4, 1])

plantuml_code = draw_diagram_column(
    st.session_state.app_name,
    diagram_column,
    unique_id_dict,
    id_title_dict,
    id_title_list,
    config_data,
    requirement_data,
    upstream_distance,
    downstream_distance,
    scale,
    graph_data=graph_data,
)

with edit_column:
    st.write("## データ編集")
    # 直接データ操作はせず、コピー(uuidは異なる)に対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定

    tmp_entity["type"] = st.selectbox(
        "エンティティタイプ",
        entity_types,
        index=entity_types.index(tmp_entity["type"]),
    )
    tmp_entity["id"] = st.text_input("ID", tmp_entity["id"])
    tmp_entity["title"] = st.text_input("タイトル", tmp_entity["title"])
    tmp_entity["text"] = st.text_area("説明", tmp_entity["text"])
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    # テキストエリアでエンティティの詳細情報を入力
    # 関係は複数ありえるため、繰り返し表示させる
    # また、関係の追加を行うケースがあるため、最初の項目は空にしておき2つめ以後は設定されているデータを表示する
    relation_column, destination_column = st.columns(2)
    tmp_edges = copy.deepcopy(requirement_data["edges"])
    for i, tmp_edge in enumerate(tmp_edges):

        # 接続元が選択エンティティでないものはスキップ
        if tmp_edge["source"] != selected_unique_id:
            continue

        relation_column, destination_column = st.columns(2)
        with relation_column:
            tmp_edge["type"] = st.selectbox(
                "関係タイプ",
                relation_types,
                relation_types.index(tmp_edge["type"]),
                key=f"relation_type{i}",
            )
        with destination_column:
            tmp_edge["destination"] = id_title_dict[
                st.selectbox(
                    "接続先",
                    id_title_list,
                    id_title_list.index(unique_id_dict[tmp_edge["destination"]]),
                    key=f"destination{i}",
                )
            ]
        expander_title = (
            "関係の注釈"
            if "text" in tmp_edge["note"] and tmp_edge["note"]["text"] != ""
            else "関係の注釈(なし)"
        )
        with st.expander(
            expander_title,
            expanded=bool("text" in tmp_edge["note"] and tmp_edge["note"]["text"]),
        ):
            tmp_edge["note"]["type"] = st.selectbox(
                "注釈タイプ",
                note_types,
                key=f"note_type{i}",
                index=note_types.index(tmp_edge.get("note").get("type", "None")),
            )
            if "note" in tmp_edge:
                tmp_edge["note"]["text"] = st.text_area(
                    "説明",
                    tmp_edge.get("note").get("text", ""),
                    key=f"relation_note{i}",
                )
            else:
                tmp_edge["note"] = st.text_area("説明", "", key=f"relation_note{i}")

    # 関係追加の操作があるため、1つは常に表示
    relation_column_new, destination_column_new = st.columns(2)

    with relation_column_new:
        relation_type = st.selectbox("関係タイプ(新規)", relation_types)
    with destination_column_new:
        destination_unique_id = id_title_dict[
            st.selectbox(
                "接続先(新規)", id_title_list, index=id_title_list.index("None")
            )
        ]  # 末尾に追加用の空要素を追加
    with st.expander("関係の注釈(新規)", expanded=True):
        relation_note = {}
        relation_note["type"] = st.selectbox("注釈タイプ", note_types, key="note_type")
        relation_note["text"] = st.text_area("説明", "", key="relation_text")

    if not relation_note:
        tmp_edges.append(
            {
                "source": selected_unique_id,
                "type": relation_type,
                "destination": destination_unique_id,
                "note": {},
            }
        )
    else:
        tmp_edges.append(
            {
                "source": selected_unique_id,
                "type": relation_type,
                "destination": destination_unique_id,
                "note": relation_note,
            }
        )

    add_operate_buttons(
        selected_unique_id,
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        tmp_edges=tmp_edges,
    )


# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
