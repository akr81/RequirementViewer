import streamlit as st
import subprocess
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode
from src.requirement_manager import RequirementManager
import hjson
import os
import uuid
import networkx as nx
import atexit
import requests
import zlib
import copy
import shutil


# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
@st.cache_resource
def start_plantuml_server():
    """Launch PlantUML server as a background process."""
    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", "-picoweb"]
    process = subprocess.Popen(command)
    # プロセス終了時にクリーンアップするため、atexitに登録
    atexit.register(lambda: process.terminate())
    return process


# PlantUMLサーバ向けのエンコード関数
def encode_plantuml(text: str) -> str:
    """Encode text to PlantUML server format.

    Args:
        text (str): Text to encode

    Returns:
        str: Encoded text
    """
    # UTF-8にエンコードし、zlibでdeflate圧縮
    data = text.encode("utf-8")
    compressed = zlib.compress(data)
    # zlibヘッダー(最初の2バイト)とチェックサム(最後の4バイト)を除去
    compressed = compressed[2:-4]
    return encode64(compressed)


def encode64(data: bytes) -> str:
    """Encode bytes to PlantUML server format.

    Args:
        data (bytes): Data to encode

    Returns:
        str: Encoded text
    """
    # PlantUML用のカスタム64エンコードテーブル
    char_map = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    res = []
    # 3バイトずつ処理し、24ビット整数にまとめる
    for i in range(0, len(data), 3):
        b = data[i : i + 3]
        # 3バイトに満たない場合は0でパディング
        if len(b) < 3:
            b = b + bytes(3 - len(b))
        n = (b[0] << 16) + (b[1] << 8) + b[2]
        # 6ビットごとに分割して、char_mapの文字に変換
        res.append(char_map[(n >> 18) & 0x3F])
        res.append(char_map[(n >> 12) & 0x3F])
        res.append(char_map[(n >> 6) & 0x3F])
        res.append(char_map[n & 0x3F])
    return "".join(res)


# PlantUMLコードからSVG画像を取得する関数
def get_diagram(plantuml_code: str, plantuml_server: str) -> str:
    """Get SVG diagram from PlantUML code.

    Args:
        plantuml_code (str): PlantUML code
        plantuml_server (str): PlantUML server URL

    Returns:
        str: SVG diagram as text
    """
    # PlantUMLサーバ用にエンコード
    encoded = encode_plantuml(plantuml_code)
    url = "".join([plantuml_server, encoded])
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        st.error("PlantUMLサーバから図を取得できませんでした。")
        st.write(response)
        st.write(url)
        return ""


@st.cache_data
def load_config() -> dict:
    """Load config from JSON file.

    Returns:
        dict: Config dictionary
    """
    with open(os.path.join("setting", "config.json"), "r", encoding="utf-8") as f:
        config = hjson.load(f)
    return config


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


def load_requirement_data(file_path: str) -> list[dict]:
    """Load requirement data from JSON file.

    Args:
        file_path (str): Path to JSON file

    Returns:
        list[dict]: List of requirement data
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                requirement_data = hjson.load(f)
            except:
                st.error("JSONファイルの読み込みに失敗しました。")
                st.stop()
    else:
        # 存在しない場合は空で始める
        requirement_data = []
    return requirement_data


def update_requirement_data(file_path: str, requirement_data: list[dict]):
    """Update requirements to JSON file.

    Args:
        file_path (str): Path to JSON file
        requirement_data (list[dict]): Requirement data list
    """
    # list内の辞書型データをunique_id順に並び替える
    requirement_data.sort(key=lambda x: x["unique_id"])
    with open(file_path, "w", encoding="utf-8") as f:
        hjson.dump(requirement_data, f, ensure_ascii=False, indent=4)


@st.cache_data
def get_id_title_dict(requirement_data: list[dict]) -> dict:
    """Get ID and title dictionary from requirement data.

    Args:
        requirement_data (list[dict]): Requirement data list

    Returns:
        dict: ID and title dictionary
    """
    id_title_dict = {
        requirement["id"] + ": " + requirement["title"]: requirement["unique_id"]
        for requirement in requirement_data
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
        requirement["unique_id"]: requirement["id"] + ": " + requirement["title"]
        for requirement in requirement_data
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
    id_title_list = [
        requirement["id"] + ": " + requirement["title"]
        for requirement in requirement_data
    ]
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
        "unique_id": f"{uuid.uuid4()}".replace("-", ""),
        "relations": [],
    }


def get_scale_from_query_params() -> float:
    """Get scale from query parameters.

    Returns:
        float: Scale value
    """
    scale = st.query_params.get("scale", [None])
    if scale == [None]:
        scale = 1.0  # デフォルト値
    else:
        scale = float(scale)
    return scale


st.set_page_config(
    layout="wide",
    page_title="Your App Title",
    initial_sidebar_state="collapsed",  # サイドバーを閉じた状態で表示
)

# Configファイルを読み込む
config_data = load_config()

# PlantUMLサーバを起動（キャッシュされるので再度起動されません）
if not ("www.plantuml.com" in config_data["plantuml"]):
    plantuml_process = start_plantuml_server()
# st.write("PlantUMLサーバが立ち上がっています（プロセスID：", plantuml_process.pid, "）")

# エンティティタイプと関係タイプを読み込む
entity_types = load_entity_types()
relation_types = load_relation_types()


st.title("Requirement Diagram Viewer")

# テキストでJSONファイルのパスを指定(デフォルトはdefault.json)
# file_path = st.text_input("JSONファイルのパスを入力してください", "default.json")
# 元に戻すボタンを表示
if st.button("元に戻す"):
    # バックアップのJSONファイルをデフォルトに上書きコピー
    shutil.copyfile("back.json", "default.json")
    st.rerun()
file_path = "default.json"

requirement_data = load_requirement_data(file_path)
requirement_manager = RequirementManager(requirement_data)

# IDとタイトルをキー, ユニークIDを値とする辞書とその逆を作成
id_title_dict = get_id_title_dict(requirement_data)
unique_id_dict = get_unique_id_dict(requirement_data)

id_title_list = get_id_title_list(requirement_data)

# URL のクエリからパラメタを取得
scale = get_scale_from_query_params()
selected_unique_id = st.query_params.get("selected", [None])
filter_direction = st.query_params.get("filter_direction", "All")

# グラフデータをPlantUMLコードに変換
config = {"detail": True, "debug": False, "width": 800, "left_to_right": False}
converter = ConvertPumlCode(config)


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

target = None
with diagram_column:
    title_column, filter_column, filter_direction_column, scale_column = st.columns(
        [2, 1, 1, 1]
    )
    with title_column:
        st.write("## Requirement Diagram")
        st.write("クリックするとエンティティが選択されます")
    with filter_column:
        target = st.query_params.get("target", None)
        if target == None or target == "None" or target not in unique_id_dict:
            target = "None"
        target = id_title_dict[
            st.selectbox(
                "フィルタ",
                id_title_list,
                index=id_title_list.index(unique_id_dict[target]),
            )
        ]

        # 読み込んだデータをグラフデータに変換
        graph_data = RequirementGraph(requirement_manager.requirements)
    with filter_direction_column:
        filter_direction_list = ["All", "Upstream", "Downstream"]
        filter_direction = st.selectbox(
            "フィルタ方向",
            options=filter_direction_list,
            index=filter_direction_list.index(filter_direction),
        )
        # グラフをフィルタリング
        graph_data.extract_subgraph(target, filter_direction)
    with scale_column:
        # 出力svgの拡大縮小倍率を設定
        scale = st.slider(
            "スケール", min_value=0.1, max_value=3.0, value=scale, step=0.1
        )
        # ローカルで PlantUML コードから SVG を生成
        parameters_dict = {}
        parameters_dict["scale"] = scale
        parameters_dict["target"] = target
        parameters_dict["filter_direction"] = filter_direction
        plantuml_code = converter.convert_to_puml(
            graph_data.subgraph, title=None, parameters_dict=parameters_dict
        )
        svg_output = get_diagram(plantuml_code, config_data["plantuml"])
        svg_output = svg_output.replace(
            "<defs/>", "<defs/><style>a {text-decoration: none !important;}</style>"
        )

    # svg出力のデバッグ
    with open("debug.svg", "w") as out:
        out.writelines(svg_output)
    # SVG をそのまま表示
    st.markdown(
        f"""
        <div style="width:100%; height:800px; overflow:auto; border:0px solid black;">
            {svg_output}
        </div>
        """,
        unsafe_allow_html=True,
    )

with edit_column:
    st.write("## データ編集")
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = copy.deepcopy(selected_entity)

    tmp_entity["type"] = st.selectbox(
        "エンティティタイプ",
        entity_types,
        index := entity_types.index(tmp_entity["type"]),
    )
    tmp_entity["id"] = st.text_input("ID", tmp_entity["id"])
    tmp_entity["title"] = st.text_input("タイトル", tmp_entity["title"])
    tmp_entity["text"] = st.text_area("説明", tmp_entity["text"])

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
        expander_title = "関係の注釈" if bool(relation["note"]) else "関係の注釈(なし)"
        with st.expander(expander_title, expanded=bool(relation["note"])):
            if "note" in relation:
                relation["note"] = st.text_input(
                    "関係の注釈", relation["note"], key=f"relation_note{i}"
                )
            else:
                relation["note"] = st.text_input(
                    "関係の注釈", "", key=f"relation_note{i}"
                )

    # 関係追加の操作があるため、1つは常に表示
    relation_column_new, destination_column_new = st.columns(2)

    with relation_column_new:
        relation_type = st.selectbox("関係タイプ", relation_types)
    with destination_column_new:
        destination_unique_id = id_title_dict[
            st.selectbox("接続先", id_title_list, index=id_title_list.index("None"))
        ]  # 末尾に追加用の空要素を追加
    with st.expander("関係の注釈", expanded=True):
        relation_note = st.text_input("関係の注釈", "")

    if not relation_note:
        tmp_entity["relations"].append(
            {"type": relation_type, "destination": destination_unique_id}
        )
    else:
        tmp_entity["relations"].append(
            {
                "type": relation_type,
                "destination": destination_unique_id,
                "note": relation_note,
            }
        )

    space_col, col31, col32, col33 = st.columns([3, 1, 1, 1])
    with col31:
        # 追加ボタンを表示
        if st.button("追加"):
            if (tmp_entity["id"] + ": " + tmp_entity["title"]) in id_title_dict:
                st.error("IDとタイトルが既存のエンティティと重複しています。")
            else:
                added_id = requirement_manager.add(tmp_entity)
                update_requirement_data(file_path, requirement_manager.requirements)
                st.write("エンティティを追加しました。")
                st.query_params.selected = added_id
                st.rerun()
    with col32:
        # 更新ボタンを表示
        if st.button("更新"):
            if not (tmp_entity["unique_id"]) in unique_id_dict:
                st.error("更新すべきエンティティがありません。")
            else:
                requirement_manager.update(tmp_entity)
                update_requirement_data(file_path, requirement_manager.requirements)
                st.write("エンティティを更新しました。")
                st.query_params.selected = tmp_entity["unique_id"]
                st.rerun()
    with col33:
        # 削除ボタンを表示
        if st.button("削除"):
            if not (tmp_entity["id"] + ": " + tmp_entity["title"]) in id_title_dict:
                st.error("削除すべきエンティティがありません。")
            else:
                requirement_manager.remove(tmp_entity["unique_id"])
                update_requirement_data(file_path, requirement_manager.requirements)
                st.write("エンティティを削除しました。")
                st.rerun()

# セッション状態にgraph_dataを追加
st.session_state.graph_data = graph_data

# テキストエリアで PlantUML コードが確認可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
