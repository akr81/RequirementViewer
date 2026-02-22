"""utility.py の純粋関数群のユニットテスト

Streamlitランタイムに依存しない関数のみをテスト対象とする。
"""
import pytest
from src.utility import (
    build_mapping,
    build_sorted_list,
    build_and_list,
    get_next_and_number,
    unescape_newline,
    recursive_unescape,
    make_hashable,
    calculate_text_area_height,
    encode64,
    get_default_data_structure,
)


# --- build_mapping ---

class TestBuildMapping:
    def test_基本マッピング(self):
        items = [
            {"name": "A", "id": "1"},
            {"name": "B", "id": "2"},
        ]
        result = build_mapping(items, "name", "id")
        assert result == {"A": "1", "B": "2"}

    def test_add_emptyで空要素追加(self):
        items = [{"name": "A", "id": "1"}]
        result = build_mapping(items, "name", "id", add_empty=True)
        assert "None" in result
        assert result["None"] == "None"

    def test_空リスト(self):
        result = build_mapping([], "name", "id")
        assert result == {}


# --- build_sorted_list ---

class TestBuildSortedList:
    def test_ソート順(self):
        items = [{"v": "C"}, {"v": "A"}, {"v": "B"}]
        result = build_sorted_list(items, "v")
        assert result == ["A", "B", "C"]

    def test_prependで先頭挿入(self):
        items = [{"v": "B"}, {"v": "A"}]
        result = build_sorted_list(items, "v", prepend=["X", "Y"])
        assert result[:2] == ["X", "Y"]
        assert result[2:] == ["A", "B"]


# --- build_and_list ---

class TestBuildAndList:
    def test_ユニーク抽出とソート(self):
        items = [
            {"and": "2"},
            {"and": "1"},
            {"and": "2"},  # 重複
            {"and": "None"},  # 除外される
        ]
        result = build_and_list(items)
        assert result == ["1", "2"]

    def test_prependで先頭挿入(self):
        items = [{"and": "1"}]
        result = build_and_list(items, prepend=["None", "New"])
        assert result[:2] == ["None", "New"]

    def test_空リスト(self):
        result = build_and_list([])
        assert result == []


# --- get_next_and_number ---

class TestGetNextAndNumber:
    def test_Newで空き番号(self):
        existing = ["1", "2"]
        result = get_next_and_number(existing, "New")
        assert result == "3"

    def test_Newで1から開始(self):
        result = get_next_and_number([], "New")
        assert result == "1"

    def test_空文字でNone(self):
        result = get_next_and_number([], "")
        assert result == "None"

    def test_通常値はそのまま(self):
        result = get_next_and_number([], "5")
        assert result == "5"


# --- unescape_newline ---

class TestUnescapeNewline:
    def test_エスケープ改行を戻す(self):
        assert unescape_newline("hello\\nworld") == "hello\nworld"

    def test_改行なしはそのまま(self):
        assert unescape_newline("hello") == "hello"

    def test_非文字列はそのまま(self):
        assert unescape_newline(123) == 123
        assert unescape_newline(None) is None


# --- recursive_unescape ---

class TestRecursiveUnescape:
    def test_文字列(self):
        assert recursive_unescape("a\\nb") == "a\nb"

    def test_リスト(self):
        result = recursive_unescape(["a\\nb", "c"])
        assert result == ["a\nb", "c"]

    def test_辞書(self):
        result = recursive_unescape({"k": "v\\nw"})
        assert result == {"k": "v\nw"}

    def test_ネスト(self):
        data = {"list": ["a\\nb"], "dict": {"k": "x\\ny"}}
        result = recursive_unescape(data)
        assert result["list"][0] == "a\nb"
        assert result["dict"]["k"] == "x\ny"

    def test_数値はそのまま(self):
        assert recursive_unescape(42) == 42


# --- make_hashable ---

class TestMakeHashable:
    def test_辞書がタプルに変換される(self):
        result = make_hashable({"b": 2, "a": 1})
        # キーでソートされたタプルのタプル
        assert result == (("a", 1), ("b", 2))

    def test_リストがタプルに変換される(self):
        result = make_hashable([1, 2, 3])
        assert result == (1, 2, 3)

    def test_セットがfrozensetに変換される(self):
        result = make_hashable({1, 2})
        assert result == frozenset({1, 2})

    def test_ネスト(self):
        data = {"key": [1, {"nested": 2}]}
        result = make_hashable(data)
        assert isinstance(result, tuple)
        # ハッシュ可能であること
        hash(result)

    def test_プリミティブはそのまま(self):
        assert make_hashable(42) == 42
        assert make_hashable("s") == "s"


# --- calculate_text_area_height ---

class TestCalculateTextAreaHeight:
    def test_空文字で最小値(self):
        result = calculate_text_area_height("")
        assert result == 100

    def test_Noneで最小値(self):
        result = calculate_text_area_height(None)
        assert result == 100

    def test_複数行で増加(self):
        text = "line1\nline2\nline3"
        result = calculate_text_area_height(text)
        assert result > 100

    def test_1行でも最小値以上(self):
        result = calculate_text_area_height("hello")
        assert result >= 100


# --- encode64 ---

class TestEncode64:
    def test_空バイト(self):
        result = encode64(b"")
        assert result == ""

    def test_既知入力(self):
        # 3バイト → 4文字
        result = encode64(b"\x00\x00\x00")
        assert len(result) == 4

    def test_決定的(self):
        # 同じ入力に対して同じ出力
        data = b"hello"
        assert encode64(data) == encode64(data)


# --- get_default_data_structure ---

class TestGetDefaultDataStructure:
    def test_デフォルト構造(self):
        result = get_default_data_structure()
        assert "nodes" in result
        assert "edges" in result
        assert result["nodes"] == []
        assert result["edges"] == []
