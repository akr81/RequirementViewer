import streamlit as st
import subprocess
import atexit
import zlib
import requests
import hjson
import os
from typing import Tuple


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
def load_config() -> Tuple[dict, bool]:
    """Load config from JSON file.

    Returns:
        dict: Config dictionary
    """
    if os.path.exists("setting/config.json"):
        config_file = "setting/config.json"
        demo = False
    else:
        config_file = "setting/default_config.json"
        demo = True
    with open(config_file, "r", encoding="utf-8") as f:
        config = hjson.load(f)
    return config, demo


def load_source_data(file_path: str) -> list[dict]:
    """Load diagram source data from JSON file.

    Args:
        file_path (str): Path to JSON file

    Returns:
        list[dict]: List of source data
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                source_data = hjson.load(f)
            except:
                st.error("JSONファイルの読み込みに失敗しました。")
                st.stop()
    else:
        # 存在しない場合は空で始める
        source_data = []
    return source_data


def update_source_data(file_path: str, source_data: list[dict]):
    """Update source to JSON file.

    Args:
        file_path (str): Path to JSON file
        source_data (list[dict]): Source data list
    """
    # list内の辞書型データをunique_id順に並び替える
    source_data.sort(key=lambda x: x["unique_id"])
    with open(file_path, "w", encoding="utf-8") as f:
        hjson.dump(source_data, f, ensure_ascii=False, indent=4)
