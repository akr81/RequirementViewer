"""PlantUMLサーバーとの通信・エンコード処理。"""
import streamlit as st
import subprocess
import atexit
import zlib
import requests
import socket
from urllib.parse import urlparse
from typing import Any


def find_available_port(start_port: int, max_attempts: int = 20) -> int:
    """指定されたポートから開始して、利用可能なポートを見つける。

    Args:
        start_port (int): 探索開始ポート
        max_attempts (int): 最大試行回数

    Returns:
        int: 利用可能なポート番号
    
    Raises:
        RuntimeError: 利用可能なポートが見つからない場合
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(("localhost", port))
            if result != 0:  # 0以外なら接続不可＝空いている可能性が高い
                return port
    raise RuntimeError(
        f"利用可能なポートが見つかりませんでした (探索範囲: {start_port}-{start_port + max_attempts - 1})"
    )


@st.cache_resource
def start_plantuml_server(config_data: dict = None) -> str:
    """PlantUMLサーバーをバックグラウンドプロセスとして起動する。
    
    Args:
        config_data (dict): 設定データ。plantumlのURL設定を含む。指定がない場合はデフォルト(8080)を使用。

    Returns:
        str: 起動したPlantUMLサーバーのURL (例: http://localhost:8081)
    """
    # configからポートを取得 (デフォルト 8080)
    start_port = 8080
    base_url = "http://localhost"
    
    if config_data and "plantuml" in config_data:
        try:
            parsed = urlparse(config_data["plantuml"])
            if parsed.port:
                start_port = parsed.port
            if parsed.scheme and parsed.hostname:
                 base_url = f"{parsed.scheme}://{parsed.hostname}"
        except Exception:
            pass  # パースエラー時はデフォルトを使用

    # 空きポートを探す
    try:
        port = find_available_port(start_port)
    except RuntimeError as e:
        st.error(f"PlantUMLサーバの起動に失敗しました: {e}")
        return None

    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", f"-picoweb:{port}"]
    try:
        process = subprocess.Popen(command)
        # プロセス終了時にクリーンアップするため、atexitに登録
        atexit.register(lambda: process.terminate())
        
        runtime_url = f"{base_url}:{port}"
        return runtime_url
    except FileNotFoundError:
        st.error(
            "Javaまたはplantuml.jarが見つかりません。Javaがインストールされているか、plantuml.jarが配置されているか確認してください。"
        )
        return None
    except Exception as e:
        st.error(f"PlantUMLサーバの起動に失敗しました: {e}")
        return None


# PlantUMLサーバ向けのエンコード関数
def encode_plantuml(text: str) -> str:
    """テキストをPlantUMLサーバー用のフォーマットにエンコードする。

    Args:
        text (str): エンコードするテキスト

    Returns:
        str: エンコードされたテキスト
    """
    # UTF-8にエンコードし、zlibでdeflate圧縮
    data = text.encode("utf-8")
    compressed = zlib.compress(data)
    # zlibヘッダー(最初の2バイト)とチェックサム(最後の4バイト)を除去
    compressed = compressed[2:-4]
    return encode64(compressed)


def encode64(data: bytes) -> str:
    """バイトデータをPlantUMLサーバー用のフォーマットにエンコードする。

    Args:
        data (bytes): エンコードするバイトデータ

    Returns:
        str: エンコードされたテキスト
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
@st.cache_data(show_spinner=False)
def get_diagram(plantuml_code: str, plantuml_server: str, *, png_out=False) -> Any:
    """PlantUMLコードからSVG/PNG図を取得する。

    Args:
        plantuml_code (str): PlantUMLコード
        plantuml_server (str): PlantUMLサーバーのURL

    Returns:
        Any: SVG図のテキスト、またはPNG画像のバイトデータ
    """
    plantuml_server = plantuml_server + "/svg/"  # デフォルトはSVG出力
    if png_out:
        # PNG出力の場合はURLを変更
        plantuml_server = plantuml_server.replace("svg", "png")
        plantuml_code = plantuml_code.replace(
            "@startuml", "@startuml\nskinparam dpi 200\n"
        )
    # PlantUMLサーバ用にエンコード
    encoded = encode_plantuml(plantuml_code)
    url = "".join([plantuml_server, encoded])
    response = requests.get(url)
    if response.status_code == 200:
        if png_out:
            return response.content
        else:
            return response.text
    else:
        st.error("PlantUMLサーバから図を取得できませんでした。")
        st.write(response)
        st.write(url)
        return ""
