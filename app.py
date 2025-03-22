import streamlit as st
import subprocess
from urllib.parse import urlencode
from src.requirement_graph import RequirementGraph
from src.convert_puml_code import ConvertPumlCode
import json
import os
import uuid
import networkx as nx
import atexit
import requests
import base64
import zlib
import urllib

# Streamlit のレイアウトをワイドに設定
st.set_page_config(layout="wide")

# キャッシュを利用して、同じコードの場合は再実行を防ぐ
@st.cache_data
def plantuml_svg(plantuml_code: str) -> str:
    """
    ローカルの PlantUML jar を利用して、PlantUML コードから SVG を生成する関数
    ※PlantUML jar（plantuml.jar）はこのコードと同じディレクトリに配置すること。
    """
    try:
        process = subprocess.run(
            ["java", "-jar", "plantuml.jar", "-pipe", "-tsvg"],
            input=plantuml_code.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return process.stdout.decode("utf-8")
    except subprocess.CalledProcessError as e:
        st.error("PlantUML の図生成中にエラーが発生しました:")
        st.error(e.stderr.decode("utf-8"))
        return ""

# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
@st.cache_resource
def start_plantuml_server():
    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", "-picoweb"]
    process = subprocess.Popen(command)
    # プロセス終了時にクリーンアップするため、atexitに登録
    atexit.register(lambda: process.terminate())
    return process

# PlantUMLサーバを起動（キャッシュされるので再度起動されません）
plantuml_process = start_plantuml_server()
st.write("PlantUMLサーバが立ち上がっています（プロセスID：", plantuml_process.pid, "）")

# PlantUMLサーバ向けのエンコード関数
def encode_plantuml(text: str) -> str:
    # UTF-8にエンコードし、zlibでdeflate圧縮
    data = text.encode('utf-8')
    compressed = zlib.compress(data)
    # zlibヘッダー(最初の2バイト)とチェックサム(最後の4バイト)を除去
    compressed = compressed[2:-4]
    return encode64(compressed)

def encode64(data: bytes) -> str:
    # PlantUML用のカスタム64エンコードテーブル
    char_map = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    res = []
    # 3バイトずつ処理し、24ビット整数にまとめる
    for i in range(0, len(data), 3):
        b = data[i:i+3]
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
def get_diagram(plantuml_code: str) -> str:
    # PlantUMLサーバ用にエンコード
    encoded = encode_plantuml(plantuml_code)
    url = f"http://localhost:8080/svg/{encoded}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        st.error("PlantUMLサーバから図を取得できませんでした。")
        return ""

st.title("Requirement Diagram Viewer")

# テキストでJSONファイルのパスを指定(デフォルトはdefault.json)
file_path = st.text_input("JSONファイルのパスを入力してください", "default.json")

# ファイルが存在する場合は読み込む
if os.path.exists(file_path):
    # JSONファイルを読み込む。文字コードに注意
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            requirement_data = json.load(f)
        except:
            st.error("JSONファイルの読み込みに失敗しました。")
            st.stop()
else:
    #存在しない場合は空で始める
    requirement_data = []

print(requirement_data)

# 読み込んだデータからIDとタイトルをキーとする辞書を作成
id_title_dict = {requirement["id"] + ": " + requirement["title"]: requirement["unique_id"] for requirement in requirement_data}
id_title_dict["None"] = "None"
# 逆にユニークIDをキーとする辞書も作成
unique_id_dict = {requirement["unique_id"]:  requirement["id"] + ": " + requirement["title"]for requirement in requirement_data}
unique_id_dict["None"] = "None"

id_title_list = [requirement["id"] + ": " + requirement["title"] for requirement in requirement_data]
id_title_list.insert(0, "None")

# 出力svgの拡大縮小倍率を設定
scale = st.slider("拡大縮小倍率", min_value=0.1, max_value=3.0, value=1.0, step=0.1)

# 読み込んだデータをグラフデータに変換
graph_data = RequirementGraph(requirement_data)
print(graph_data)
# graph_data = {
#     "nodes": [],
#     "edges": []
# }

# グラフデータをPlantUMLコードに変換
config = {
    "detail": True,
    "debug": True,
    "width": 800,
    "left_to_right": False
}
converter = ConvertPumlCode(config)
plantuml_code = converter.convert_to_puml(graph_data.graph, title=None, target=None, scale=scale)

# URL のクエリパラメータから、選択されたエンティティを取得
# query_params = st.query_params()
selected_unique_id = st.query_params.get("selected", [None])

# パラメタがない場合はデフォルトのエンティティを選択してリロード
print(selected_unique_id)
selected_entity = {}
if selected_unique_id == [None]:
    print("Set default params")
    default_params = {"selected": "default"}
    st.query_params.setdefault("selected", "default")
    st.rerun()
else:
    if selected_unique_id == "default":
        selected_entity = None
    else:
        if selected_unique_id not in unique_id_dict:
            selected_entity = None
        else:
            selected_entity = [d for d in requirement_data if d["unique_id"] == selected_unique_id][0]
st.write(selected_unique_id)

if not selected_entity:
    selected_entity = {
        "type": "functionalRequirement",
        "id": "",
        "title": "",
        "text": "",
        "unique_id": uuid.uuid4(),
        "relations": []
    }

# ローカルで PlantUML コードから SVG を生成
# svg_output = plantuml_svg(plantuml_code)
svg_output = get_diagram(plantuml_code)
svg_output = svg_output.replace("<defs/>", "<defs/><style>a {text-decoration: none;}</style>")

# svg_output = '''
# <svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
#   <style>
#     a {
#       text-decoration: none;
#     }
#   </style>
#   <a xlink:href="https://example.com">
#     <text x="10" y="40" font-family="Arial" font-size="24" fill="blue">
#       クリックしてリンクへ
#     </text>
#   </a>
# </svg>
# '''

# svg出力のデバッグ
with open("debug.svg", "w") as out:
    out.writelines(svg_output)

# 2つのカラムに表示を分割
col1, col2 = st.columns([4, 1])

with col1:
    st.write("## PlantUML 図")
    st.write("クリックするとエンティティが選択されます")
    # SVG をそのまま表示
    st.markdown(
        f'''
        <div style="width:100%; height:400px; overflow:auto; border:0px solid black;">
            {svg_output}
        </div>
        ''',
        unsafe_allow_html=True)

with col2:
    st.write("## データ操作")
    # 直接データ操作はせず、コピーに対して操作する
    tmp_entity = selected_entity.copy()

    # エンティティタイプを定義
    entity_types = ["functionalRequirement", "performanceRequirement", "designConstraint", "interfaceRequirement", "physicalRequirement"]
    tmp_entity["type"] = st.selectbox("エンティティタイプ", entity_types)
    tmp_entity["id"] = st.text_input("ID", tmp_entity["id"])
    tmp_entity["title"] = st.text_input("タイトル", tmp_entity["title"])
    tmp_entity["text"] = st.text_area("説明", tmp_entity["text"])

    # テキストエリアでエンティティの詳細情報を入力
    # 関係は複数ありえるため、繰り返し表示させる
    # また、関係の追加を行うケースがあるため、最初の項目は空にしておき2つめ以後は設定されているデータを表示する
    relation_types = ["None", "deriveReqt", "satisfy", "refine", "containment", "problem"]

    # 関係追加の操作があるため、1つは常に表示
    col21, col22 = st.columns(2)
    with col21:
        relation_type = st.selectbox("関係タイプ", relation_types)
        for relation in tmp_entity["relations"]:
            relation["type"] = st.selectbox("関係タイプ", relation["type"])
    with col22:
        destination_unique_id = st.selectbox("接続先", id_title_dict.keys(), index=len(id_title_dict) - 1) # 末尾に追加用の空要素を追加
        for relation in tmp_entity["relations"]:
            relation["destination"] = id_title_dict[st.selectbox("接続先", unique_id_dict[relation["destination"]])]


    space_col, col31, col32, col33 = st.columns([3, 1, 1, 1])
    with col31:
        # 追加ボタンを表示
        if st.button("追加"):
            if (tmp_entity["id"] + ": " + tmp_entity["title"]) in id_title_dict:
                st.error("IDとタイトルが既存のエンティティと重複しています。")
            else:
                # ユニークID振り直し
                tmp_entity["unique_id"] = f"{uuid.uuid4()}".replace("-", "")
                requirement_data.append(tmp_entity)
                with open("default.json", "w", encoding="utf-8") as f:
                    json.dump(requirement_data, f, ensure_ascii=False, indent=4)
                st.write("エンティティを追加しました。")
                st.rerun()
    with col32:
        # 更新ボタンを表示
        if st.button("更新"):
            if not (tmp_entity["unique_id"]) in unique_id_dict:
                st.error("更新すべきエンティティがありません。")
            else:
                # 一度削除してから追加
                requirement_data.remove([d for d in requirement_data if d["unique_id"] == tmp_entity["unique_id"]][0])
                requirement_data.append(tmp_entity)
                with open("default.json", "w", encoding="utf-8") as f:
                    json.dump(requirement_data, f, ensure_ascii=False, indent=4)
                st.write("エンティティを更新しました。")
                st.rerun()
    with col33:
        # 削除ボタンを表示
        if st.button("削除"):
            if not (tmp_entity["id"] + ": " + tmp_entity["title"]) in id_title_dict:
                st.error("削除すべきエンティティがありません。")
            else:
                # 削除
                # TODO: 関連エンティティも削除する
                requirement_data.remove([d for d in requirement_data if d["unique_id"] == tmp_entity["unique_id"]][0])
                with open("default.json", "w", encoding="utf-8") as f:
                    json.dump(requirement_data, f, ensure_ascii=False, indent=4)
                st.write("エンティティを削除しました。")
                st.rerun()


# 選択されたエンティティの情報を表示・編集
# if selected_entity:
#     st.subheader(f"選択されたエンティティ: {selected_entity}")
#     # サンプル用のダミーデータ（実際は session_state 等で管理することを検討）
#     entity_info = {
#         "req1": "System Requirement: システムは安全に動作すること",
#         "req2": "User Requirement: ユーザは容易に操作できること",
#         "req3": "Derived Requirement: 操作性と安全性の両立を実現すること"
#     }
#     current_info = entity_info.get(selected_entity, "情報なし")
#     new_info = st.text_area("エンティティ情報", value=current_info)
#     if st.button("更新"):
#         # 更新処理（ここではダミー）
#         st.success(f"{selected_entity} の情報が更新されました。（この例では更新処理はダミーです）")

# テキストエリアで PlantUML コードの編集が可能
st.text_area("PlantUML コード", value=plantuml_code, height=250)
