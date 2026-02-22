"""テキスト処理ユーティリティ。"""
from typing import Any


def calculate_text_area_height(text: str, min_height: int = 100, line_height: int = 25) -> int:
    """行数に基づいてテキストエリアの高さを計算する。

    Args:
        text (str): 入力テキスト
        min_height (int): 最小の高さ（ピクセル）
        line_height (int): 1行あたりの高さ（ピクセル）

    Returns:
        int: 計算された高さ
    """
    if not text:
        return min_height
    
    # 行数をカウント（改行の数 + 1 + 末尾の空行分1）
    lines = text.count('\n') + 2
    
    # base height (padding etc.) + lines * line_height
    calculated_height = 30 + (lines * line_height)
    
    return max(min_height, calculated_height)


def unescape_newline(text: str) -> str:
    """テキスト内のエスケープされた改行文字を元に戻す。
    
    Args:
        text (str): 入力テキスト
        
    Returns:
        str: 改行文字がデコードされたテキスト
    """
    if not isinstance(text, str):
        return text
    
    # hjsonで保存された際にエスケープされた改行文字を戻す
    return text.replace("\\n", "\n")


def recursive_unescape(data: Any) -> Any:
    """データ内のエスケープされた改行文字を再帰的に元に戻す。

    Args:
        data (Any): 入力データ (dict, list, str など)

    Returns:
        Any: 改行文字がデコードされたデータ
    """
    if isinstance(data, str):
        return unescape_newline(data)
    elif isinstance(data, list):
        return [recursive_unescape(item) for item in data]
    elif isinstance(data, dict):
        return {key: recursive_unescape(value) for key, value in data.items()}
    else:
        return data
