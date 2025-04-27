import streamlit as st
from src.requirement_manager import RequirementManager
from src.utility import (
    start_plantuml_server,
    load_config,
    load_source_data,
    load_app_data,
    load_colors,
    build_mapping,
    build_sorted_list,
)
from src.diagram_column import draw_diagram_column
from src.operate_buttons import add_operate_buttons
import uuid
import copy


def get_default_entity() -> dict:
    """Get default entity data.

    Returns:
        entity_types: Entity data list
    """
    return {
        "id": "",
        "title": "",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
        "relations": [],
    }


color_list = load_colors()

st.session_state.app_name = "Evaporating Cloud Viewer"

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

# PlantUMLサーバを起動（キャッシュされるので再度起動されません）
if not ("www.plantuml.com" in config_data["plantuml"]):
    plantuml_process = start_plantuml_server()
# st.write("PlantUMLサーバが立ち上がっています（プロセスID：", plantuml_process.pid, "）")


if demo:
    st.title(st.session_state.app_name)

data_key = st.session_state.app_data[st.session_state.app_name]["data"]
if data_key not in config_data:
    st.error(
        """設定ファイルにデータファイル設定がありません。
        settingからファイルを設定してください。"""
    )
    st.stop()

file_path = config_data[data_key]

requirement_data = load_source_data(file_path)
requirement_manager = RequirementManager(requirement_data)

# IDとタイトルをキー, ユニークIDを値とする辞書とその逆を作成
id_title_dict = st.cache_data(
    lambda: build_mapping(requirement_data, "id", "unique_id", add_empty=True)
)()
unique_id_dict = st.cache_data(
    lambda: build_mapping(requirement_data, "unique_id", "id", add_empty=True)
)()
id_title_list = st.cache_data(
    lambda: build_sorted_list(requirement_data, "id", prepend=["None"])
)()

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
    selected_entity = get_default_entity()

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
    tmp_entity.setdefault("color", "None")  # colorがない場合はNoneを設定

    st.write(tmp_entity["id"])
    if tmp_entity["id"] == "head":
        question = "共通の目的は何か？"
    elif tmp_entity["id"] == "right_shoulder" or tmp_entity["id"] == "left_shoulder":
        question = "目的は何か？"
    elif tmp_entity["id"] == "right_hand" or tmp_entity["id"] == "left_hand":
        question = "行動は何か？"
    else:
        question = "仮定・前提条件は何か？"
    tmp_entity["title"] = st.text_area(question, tmp_entity["title"], height=400)
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    add_operate_buttons(
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        no_add=True,
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
