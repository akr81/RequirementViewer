"""PNGファイルへのhjsonデータ埋め込み・抽出。"""
import subprocess
import json
import base64
import os
from typing import Dict


# hjsonデータ埋め込み用のマーカー
_HJSON_DATA_BEGIN = "HJSON_DATA_BEGIN"
_HJSON_DATA_END = "HJSON_DATA_END"


def embed_hjson_in_puml(plantuml_code: str, hjson_data: Dict) -> str:
    """hjsonデータをPlantUMLコメントとして埋め込む。

    PlantUMLコード内の @startuml 直後にhjsonデータをbase64エンコードして
    コメントブロックとして挿入する。PNG生成時にメタデータとして保存され、
    後からextract_hjson_from_pngで復元できる。

    Args:
        plantuml_code (str): 元のPlantUMLコード
        hjson_data (Dict): 埋め込むhjsonデータ

    Returns:
        str: hjsonデータが埋め込まれたPlantUMLコード
    """
    # hjsonデータをJSON文字列にシリアライズしてbase64エンコード
    json_str = json.dumps(hjson_data, ensure_ascii=False)
    encoded = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

    # base64文字列を76文字ごとに分割してコメント行にする
    comment_lines = [f"' {_HJSON_DATA_BEGIN}"]
    for i in range(0, len(encoded), 76):
        comment_lines.append(f"' {encoded[i:i+76]}")
    comment_lines.append(f"' {_HJSON_DATA_END}")
    comment_block = "\n".join(comment_lines)

    # @startuml の直後に埋め込む
    return plantuml_code.replace("@startuml", f"@startuml\n{comment_block}", 1)


def extract_hjson_from_png(png_path: str) -> Dict:
    """PNGファイルのメタデータからhjsonデータを抽出・復元する。

    plantuml.jar -metadata を使ってPNGに埋め込まれたPlantUMLソースコードを
    取得し、HJSON_DATA_BEGIN/END マーカー間のbase64データをデコードして
    hjsonデータを復元する。

    Args:
        png_path (str): PNGファイルのパス

    Returns:
        Dict: 復元されたhjsonデータ

    Raises:
        FileNotFoundError: PNGファイルが見つからない場合
        ValueError: メタデータにhjsonデータが含まれていない場合
        RuntimeError: plantuml.jarの実行に失敗した場合
    """
    if not os.path.exists(png_path):
        raise FileNotFoundError(f"PNGファイルが見つかりません: {png_path}")

    # plantuml.jar -metadata でメタデータを抽出
    try:
        result = subprocess.run(
            ["java", "-jar", "plantuml.jar", "-metadata", png_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("plantuml.jarのメタデータ抽出がタイムアウトしました。")
    except FileNotFoundError:
        raise RuntimeError(
            "Javaまたはplantuml.jarが見つかりません。"
            "Javaがインストールされているか確認してください。"
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"plantuml.jar の実行に失敗しました (code {result.returncode}): "
            f"{result.stderr}"
        )

    metadata_output = result.stdout

    # HJSON_DATA_BEGIN ~ HJSON_DATA_END 間のbase64データを抽出
    in_data_block = False
    base64_parts = []

    for line in metadata_output.splitlines():
        stripped = line.strip()
        # コメントプレフィックス "' " を除去
        if stripped.startswith("'"):
            content = stripped[1:].strip()
        else:
            content = stripped

        if content == _HJSON_DATA_BEGIN:
            in_data_block = True
            continue
        elif content == _HJSON_DATA_END:
            in_data_block = False
            continue

        if in_data_block:
            base64_parts.append(content)

    if not base64_parts:
        raise ValueError(
            "このPNGファイルにはhjsonデータが埋め込まれていません。\n"
            "hjsonデータ埋め込み機能が有効になった後に保存されたPNGファイルを使用してください。"
        )

    # base64デコード → JSONパース
    encoded_data = "".join(base64_parts)
    try:
        decoded_bytes = base64.b64decode(encoded_data)
        json_str = decoded_bytes.decode("utf-8")
        hjson_data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"hjsonデータのデコードに失敗しました: {e}")

    return hjson_data
