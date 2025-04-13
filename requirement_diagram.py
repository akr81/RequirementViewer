import streamlit as st
from src.requirement_manager import RequirementManager
from src.utility import (
    start_plantuml_server,
    load_config,
    load_source_data,
    load_app_data,
    load_colors,
)
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
import hjson
import os
import uuid
import copy
import shutil


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


@st.cache_data
def get_id_title_dict(requirement_data: list[dict]) -> dict:
    """Get ID and title dictionary from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        dict: ID and title dictionary
    """
    id_title_dict = {
        requirement["id"]: requirement["unique_id"] for requirement in requirement_data
    }
    id_title_dict["None"] = "None"  # 削除用の空要素を追加
    return id_title_dict


@st.cache_data
def get_unique_id_dict(requirement_data: list[dict]) -> dict:
    """Get unique ID dictionary from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        dict: Unique ID dictionary
    """
    unique_id_dict = {
        requirement["unique_id"]: requirement["id"] for requirement in requirement_data
    }
    unique_id_dict["None"] = "None"  # 削除用の空要素を追加
    return unique_id_dict


@st.cache_data
def get_id_title_list(requirement_data: list[dict]) -> list[str]:
    """Get ID and title list from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        list[str]: ID and title list
    """
    id_title_list = [requirement["id"] for requirement in requirement_data]
    id_title_list.sort()
    id_title_list.insert(0, "None")  # 指定がない場合の初期値
    return id_title_list


def get_default_entity(entity_types: list[str]) -> dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    default_type = ""
    if len(entity_types) > 0:
        default_type = entity_types[0]
    return {
        "type": default_type,
        "id": "",
        "title": "",
        "text": "",
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
        "relations": [],
    }


st.session_state.app_name = "Requirement Diagram Viewer"

st.set_page_config(
    layout="wide",
    page_title=st.session_state.app_name,
    initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
)

# Configファイルを読み込む
config_data, demo = load_config()
st.session_state.config_data = config_data
app_data = load_app_data()
st.session_state.app_data = app_data
color_list = load_colors()

# PlantUMLサーバを起動（キャッシュされるので再度起動されません）
if not ("www.plantuml.com" in config_data["plantuml"]):
    plantuml_process = start_plantuml_server()
# st.write("PlantUMLサーバが立ち上がっています（プロセスID：", plantuml_process.pid, "）")

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

requirement_data = load_source_data(file_path)
requirement_manager = RequirementManager(requirement_data)

# IDとタイトルをキー, ユニークIDを値とする辞書とその逆を作成
id_title_dict = get_id_title_dict(requirement_data)
unique_id_dict = get_unique_id_dict(requirement_data)

id_title_list = get_id_title_list(requirement_data)

# URL のクエリからパラメタを取得
scale = float(st.query_params.get("scale", 1.0))
selected_unique_id = st.query_params.get("selected", [None])
upstream_distance = st.query_params.get(
    "upstream_distance", config_data["upstream_filter_max"]
)
downstream_distance = st.query_params.get(
    "downstream_distance", config_data["downstream_filter_max"]
)


selected_entity = None
if selected_unique_id == [None]:
    # エンティティが選択されていない場合はデフォルトのエンティティを選択してリロード
    default_params = {"selected": "default"}
    st.query_params.setdefault("selected", "default")
    st.rerun()
else:
    if selected_unique_id == "default":
        # デフォルトの場合は何もしない
        pass
    else:
        if selected_unique_id not in unique_id_dict:
            # 存在しないユニークIDが指定された場合は何もしない
            pass
        else:
            selected_entity = [
                d for d in requirement_data if d["unique_id"] == selected_unique_id
            ][0]

if not selected_entity:
    selected_entity = get_default_entity(entity_types)

# Requirement diagram表示とデータ編集のレイアウトを設定
diagram_column, edit_column = st.columns([4, 1])

graph_data, plantuml_code = draw_diagram_column(
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
)

with edit_column:
    st.write("## データ編集")
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = copy.deepcopy(selected_entity)
    if "color" not in tmp_entity or tmp_entity["color"] == "":
        tmp_entity["color"] = "None"

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

    for i, relation in enumerate(tmp_entity["relations"]):
        relation_column, destination_column = st.columns(2)
        with relation_column:
            relation["type"] = st.selectbox(
                "関係タイプ",
                relation_types,
                relation_types.index(relation["type"]),
                key=f"relation_type{i}",
            )
        with destination_column:
            relation["destination"] = id_title_dict[
                st.selectbox(
                    "接続先",
                    id_title_list,
                    id_title_list.index(unique_id_dict[relation["destination"]]),
                    key=f"destination{i}",
                )
            ]
        expander_title = (
            "関係の注釈"
            if "text" in relation["note"] and relation["note"]["text"] != ""
            else "関係の注釈(なし)"
        )
        with st.expander(
            expander_title,
            expanded=bool("text" in relation["note"] and relation["note"]["text"]),
        ):
            relation["note"]["type"] = st.selectbox(
                "注釈タイプ",
                note_types,
                key=f"note_type{i}",
                index=note_types.index(relation.get("note").get("type", "None")),
            )
            if "note" in relation:
                relation["note"]["text"] = st.text_area(
                    "説明",
                    relation.get("note").get("text", ""),
                    key=f"relation_note{i}",
                )
            else:
                relation["note"] = st.text_area("説明", "", key=f"relation_note{i}")

    # 関係追加の操作があるため、1つは常に表示
    relation_column_new, destination_column_new = st.columns(2)

    with relation_column_new:
        relation_type = st.selectbox("関係タイプ", relation_types)
    with destination_column_new:
        destination_unique_id = id_title_dict[
            st.selectbox("接続先", id_title_list, index=id_title_list.index("None"))
        ]  # 末尾に追加用の空要素を追加
    with st.expander("関係の注釈", expanded=True):
        relation_note = {}
        relation_note["type"] = st.selectbox("注釈タイプ", note_types, key="note_type")
        relation_note["text"] = st.text_area("説明", "", key="relation_text")

    if not relation_note:
        tmp_entity["relations"].append(
            {"type": relation_type, "destination": destination_unique_id, "note": {}}
        )
    else:
        tmp_entity["relations"].append(
            {
                "type": relation_type,
                "destination": destination_unique_id,
                "note": relation_note,
            }
        )

    add_operate_buttons(
        tmp_entity, requirement_manager, file_path, id_title_dict, unique_id_dict
    )


# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
