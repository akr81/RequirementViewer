"""データ変換・マッピングユーティリティ。"""
from typing import Dict, List, Any, Optional


def build_mapping(
    items: List[Dict[str, Any]],
    key_field: str,
    value_field: str,
    *,
    add_empty: bool = False,
    empty_key: str = "None",
    empty_value: str = "None",
) -> Dict[str, str]:
    """
    items の各 dict から key_field→value_field マッピングを作成。
    add_empty=True なら空要素を追加。
    """
    mapping = {item[key_field]: item[value_field] for item in items}

    if add_empty:
        mapping[empty_key] = empty_value
    return mapping


def build_sorted_list(
    items: List[Dict[str, Any]], field: str, *, prepend: Optional[List[str]] = None
) -> List[str]:
    """
    items の各 dict から field を取り出してソートしたリストを返す。
    prepend が渡されれば、先頭に順番に挿入。
    """
    lst = sorted(item[field] for item in items)
    if prepend:
        for x in reversed(prepend):
            lst.insert(0, x)
    return lst


def build_and_list(
    items: List[Dict[str, Any]], *, prepend: Optional[List[str]] = None
) -> List[str]:
    """
    全 edges の and をユニークに集めてソートしたリスト。
    prepend（例: ["None","New"]）を先頭に挿入可能。
    """
    vals = []
    for item in items:
        if item.get("and", "None") not in (None, "", "None"):
            vals.append(str(item["and"]))
    sorted_vals = sorted(list(set(vals)), key=lambda v: (not v.isdigit(), v))
    if prepend:
        for x in reversed(prepend):
            sorted_vals.insert(0, x)
    return sorted_vals


def get_next_and_number(existing: List[str], candidate: str) -> str:
    """
    candidate=="New" → 1〜99 の空き番号を返す。
    candidate=="" → "None"
    それ以外はそのまま返す。
    """
    if candidate == "New":
        for i in range(1, 100):
            s = str(i)
            if s not in existing:
                return s
        return "None"
    if not candidate:
        return "None"
    return candidate


def make_hashable(data):
    """
    入れ子になった辞書やリストを含むデータを、ハッシュ可能で順序不変な形に変換する。
    """
    if isinstance(data, dict):
        # 辞書の場合: キーでソートし、値も再帰的に変換したタプルのタプルにする
        return tuple(sorted((key, make_hashable(value)) for key, value in data.items()))
    elif isinstance(data, list):
        # リストの場合: 各要素を再帰的に変換したタプルにする
        return tuple(make_hashable(element) for element in data)
    elif isinstance(data, set):
        # セットの場合: frozensetに変換し、要素も再帰的に変換
        return frozenset(make_hashable(element) for element in data)
    # 他のハッシュ可能な型 (int, str, tuple, frozensetなど) はそのまま返す
    return data
