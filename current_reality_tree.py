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
    extract_and_list,
    get_next_and_number,
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
        "color": "None",
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
        "relations": [],
    }


entity_list = ["entity", "note"]

color_list = load_colors()

st.session_state.app_name = "Current Reality Tree Viewer"

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

if "current_reality_tree_data" not in config_data:
    st.error(
        """設定ファイルにデータファイル設定がありません。
        settingからファイルを設定してください。"""
    )
    st.stop()
data_key = st.session_state.app_data[st.session_state.app_name]["data"]
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
add_list = extract_and_list(requirement_data, prepend=["None", "New"])

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
    if "color" not in tmp_entity:
        tmp_entity["color"] = "None"
    if "type" not in tmp_entity:
        tmp_entity["type"] = "entity"

    tmp_entity["type"] = st.selectbox(
        "タイプ", entity_list, index=entity_list.index(tmp_entity["type"])
    )
    tmp_entity["id"] = st.text_area("課題・状況", tmp_entity["id"])
    tmp_entity["color"] = st.selectbox(
        "色", color_list, index=color_list.index(tmp_entity["color"])
    )

    from_relations = []
    # ANDの情報の場合はさらにもう1ホップ遡る必要がある
    temp_predecessors = list(graph_data.graph.predecessors(tmp_entity["unique_id"]))
    predecessors = copy.deepcopy(temp_predecessors)
    and_predecessors = []
    for temp_predecessor in temp_predecessors:
        try:
            int(temp_predecessor)
            # 成功した場合はANDなので、候補から削除して、さらに遡る
            predecessors.remove(temp_predecessor)
            predecessors = predecessors + list(
                graph_data.graph.predecessors(temp_predecessor)
            )
            and_predecessors.append(
                (
                    list(graph_data.graph.predecessors(temp_predecessor)),
                    temp_predecessor,
                )
            )
        except:
            # 失敗した場合は何もしない
            pass

    for i, from_relation in enumerate(predecessors):
        temp_from_relation = {"from": None, "and": None}
        temp_from_relation["from"] = id_title_dict[
            st.selectbox(
                "接続元",
                id_title_list,
                index=id_title_list.index(unique_id_dict[from_relation]),
                key=f"from{i}",
            )
        ]
        print(and_predecessors)
        dest = "None"
        for and_predecessor in and_predecessors:
            srcs = and_predecessor[0]
            dest = and_predecessor[1]
        temp_from_relation["and"] = st.selectbox(
            "and", add_list, add_list.index(dest), key=f"and_from{i}"
        )
        from_relations.append(temp_from_relation)

    # 関係追加の操作があるため、1つは常に表示
    temp_from_relation = {"from": None, "and": None}
    temp_from_relation["from"] = id_title_dict[
        st.selectbox("接続元", id_title_list, index=id_title_list.index("None"))
    ]
    temp_from_relation["and"] = st.selectbox(
        "and", add_list, add_list.index("None"), key=f"and_from"
    )
    from_relations.append(temp_from_relation)

    for i, relation in enumerate(tmp_entity["relations"]):
        relation["destination"] = id_title_dict[
            st.selectbox(
                "接続先",
                id_title_list,
                id_title_list.index(unique_id_dict[relation["destination"]]),
                key=f"destination{i}",
            )
        ]
        relation["and"] = st.selectbox(
            "and", add_list, add_list.index(relation["and"]), key=f"and{i}"
        )
        relation["and"] = get_next_and_number(add_list, relation["and"])
        if not relation["and"]:
            relation["and"] = "None"

    # 関係追加の操作があるため、1つは常に表示
    destination_unique_id = id_title_dict[
        st.selectbox("接続先", id_title_list, index=id_title_list.index("None"))
    ]  # 末尾に追加用の空要素を追加
    destination_and = st.selectbox("and", add_list, add_list.index("None"))
    destination_and = get_next_and_number(add_list, destination_and)
    if not destination_and:
        destination_and = "None"

    tmp_entity["relations"].append(
        {
            "destination": destination_unique_id,
            "and": destination_and,
        }
    )

    add_operate_buttons(
        tmp_entity,
        requirement_manager,
        file_path,
        id_title_dict,
        unique_id_dict,
        from_relations=from_relations,
    )

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
