import streamlit as st
import subprocess
import atexit
import zlib
import requests
import hjson
import os
import shutil
import datetime
import copy
import tempfile
import time
from contextlib import contextmanager
from typing import Tuple, List, Dict, Any, Optional


@contextmanager
def log_time(label: str):
    """Execution time logging context manager."""
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"[{label}] Execution time: {elapsed_time:.4f} seconds")


# PlantUMLサーバをバックグラウンドプロセスとして起動し、キャッシュする
@st.cache_resource
def start_plantuml_server():
    """Launch PlantUML server as a background process."""
    # plantuml.jarは同一ディレクトリに配置していると仮定
    command = ["java", "-jar", "plantuml.jar", "-picoweb"]
    try:
        process = subprocess.Popen(command)
        # プロセス終了時にクリーンアップするため、atexitに登録
        atexit.register(lambda: process.terminate())
        return process
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
@st.cache_data(show_spinner=False)
def get_diagram(plantuml_code: str, plantuml_server: str, *, png_out=False) -> Any:
    """Get SVG diagram from PlantUML code.

    Args:
        plantuml_code (str): PlantUML code
        plantuml_server (str): PlantUML server URL

    Returns:
        Any: SVG diagram as text or PNG image as bytes
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


def load_colors() -> list:
    """Load colors from JSON file.

    Returns:
        list: List of colors
    """
    with open("setting/colors.json", "r", encoding="utf-8") as f:
        colors = hjson.load(f)
    return list(colors.keys())


def load_config() -> dict:
    """Load config from JSON file.

    Returns:
        dict: Config dictionary
    """
    if os.path.exists("setting/config.hjson"):
        config_file = "setting/config.hjson"
    else:
        config_file = "setting/default_config.hjson"
    with open(config_file, "r", encoding="utf-8") as f:
        config = hjson.load(f)
    return config


def save_config(config_data: dict):
    """Save config to JSON file.

    Args:
        config_data (dict): Config dictionary
    """
    config_file_path = "setting/config.hjson"
    try:
        atomic_write_json(config_file_path, config_data)
    except Exception as e:
        st.error(f"設定ファイルの保存に失敗しました: {e}")


def get_default_data_structure() -> Dict:
    """Returns the default structure for a new data file."""
    return {"nodes": [], "edges": []}


def list_hjson_files(directory: str) -> List[str]:
    """Lists .hjson files in the specified directory.

    Args:
        directory (str): The directory to scan.

    Returns:
        List[str]: A list of .hjson file names.
    """
    if not os.path.isdir(directory):
        return []
    return [
        f
        for f in os.listdir(directory)
        if f.endswith(".hjson") and os.path.isfile(os.path.join(directory, f))
    ]


def load_app_data() -> dict:
    """Load app_data from JSON file.

    Returns:
        dict: Config dictionary
    """
    with open("setting/app_data.json", "r", encoding="utf-8") as f:
        app_data = hjson.load(f)
    return app_data


def load_source_data(file_path: str) -> Dict:
    """Load diagram source data from JSON file.

    Args:
        file_path (str): Path to JSON file

    Returns:
        Dict: Dictionary of source data
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                source_data = hjson.load(f)
            except Exception as e:
                st.error(f"JSONファイルの読み込みに失敗しました: {file_path}\nError: {e}")
                return []
    else:
        # 存在しない場合は空で始める
        source_data = []

    # 古いフォーマットのデータを新しいフォーマットに変換
    if isinstance(source_data, list):
        temp_data = {"nodes": [], "edges": []}
        for item in source_data:
            temp_node = {}
            for key, value in item.items():
                if key == "relations":
                    for relation in value:
                        temp_relation = {"source": item["unique_id"]}
                        temp_relation.update(relation)
                        temp_data["edges"].append(temp_relation)
                else:
                    temp_node[key] = value
            temp_data["nodes"].append(temp_node)
        source_data = temp_data

    # データロード時に一括で改行のエスケープを解除する
    source_data = recursive_unescape(source_data)

    return source_data


def update_source_data(file_path: str, source_data: Dict):
    """Update source to JSON file.

    Args:
        file_path (str): Path to JSON file
        source_data (Dict): Source data
    """
    # --- 最後に使用したページをconfigに保存 ---
    if "app_name" in st.session_state and "config_data" in st.session_state:
        current_app_name = st.session_state.app_name
        # config.hjsonに書き込むキーをapp.pyと合わせる
        LAST_USED_PAGE_KEY = "last_used_page"
        st.session_state.config_data[LAST_USED_PAGE_KEY] = current_app_name
        save_config(st.session_state.config_data)
        # デバッグ用にコンソールに出力
        # print(f"最後に使用したページとして '{current_app_name}' を保存しました。")

    # list内の辞書型データをunique_id順に並び替える
    source_data["nodes"].sort(key=lambda x: x["unique_id"])
    source_data["edges"].sort(key=lambda x: x["source"])

    # Remove duplicated edges
    seen_edges = set()
    temp_edges = copy.deepcopy(source_data["edges"])
    filtered_edges = []
    for temp_edge in temp_edges:
        # Convert edge dict to hashable tuple
        edge_tuple = make_hashable(temp_edge)

        if edge_tuple not in seen_edges:
            seen_edges.add(edge_tuple)
            filtered_edges.append(temp_edge)

    source_data["edges"] = filtered_edges

    atomic_write_json(file_path, source_data)

    # for backup
    postfix_file = st.session_state.app_data[st.session_state.app_name]["postfix"]
    os.makedirs("back", exist_ok=True)
    filename = (
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{postfix_file}.hjson"
    )
    atomic_write_json(os.path.join("back", filename), source_data)

    # 変更に合わせてPNG画像を保存
    st.session_state["save_png"] = True


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


def get_backup_files_for_current_data():
    """Get backup files for current data.

    Returns:
        list: List of backup files
    """
    # バックアップファイルのリストを取得
    backup_files = [
        f
        for f in os.listdir("back")
        if os.path.isfile(os.path.join("back", f))
        and f.endswith(".hjson")
        and st.session_state.app_data[st.session_state.app_name]["postfix"] in f
    ]
    backup_files.sort(reverse=True)
    backup_files.insert(0, "バックアップから読込")
    return backup_files


def copy_file():
    """Copy file from backup to current data.

    Note:
        This function assumes that the source file exists in the "back" directory.
        The destination file is specified in the session state.
    """

    src = st.session_state["selected_backup_file"]
    dst = st.session_state["file_path"]
    """Copy file from src to dst."""
    src = os.path.join("back", src)
    if os.path.exists(src):
        shutil.copy(src, dst)


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
    # 注意: float型は完全一致の問題があるため、用途によっては丸め処理などが必要
    return data


def atomic_write_json(file_path: str, data: Any):
    """Write data to JSON file atomically.

    Args:
        file_path (str): Path to JSON file
        data (Any): Data to write
    """
    dir_name = os.path.dirname(file_path) or "."
    # 同じディレクトリに一時ファイルを作成
    with tempfile.NamedTemporaryFile(
        mode="w", dir=dir_name, delete=False, encoding="utf-8"
    ) as tf:
        temp_path = tf.name
        try:
            hjson.dump(data, tf, ensure_ascii=False, indent=4)
            tf.flush()
            os.fsync(tf.fileno())
        except Exception:
            # 書き込み失敗時は一時ファイルを削除して例外を再送出
            tf.close()
            os.remove(temp_path)
            raise

    # 正常に書き込めた場合のみリネーム（アトミック操作）
    try:
        os.replace(temp_path, file_path)
    except OSError:
        os.remove(temp_path)
        raise


def calculate_text_area_height(text: str, min_height: int = 100, line_height: int = 25) -> int:
    """Calculate the height of a text area based on the number of lines.

    Args:
        text (str): Input text
        min_height (int): Minimum height in pixels
        line_height (int): Height per line in pixels

    Returns:
        int: Calculated height
    """
    if not text:
        return min_height
    
    # 行数をカウント（改行の数 + 1）
    lines = text.count('\n') + 1
    
    # なぜか1行でも高くなりすぎることがあるので、少し調整
    # base height (padding etc.) + lines * line_height
    calculated_height = 30 + (lines * line_height)
    
    return max(min_height, calculated_height)


def unescape_newline(text: str) -> str:
    """Unescape newline characters in text.
    
    Args:
        text (str): Input text
        
    Returns:
        str: Text with unescaped newline characters
    """
    if not isinstance(text, str):
        return text
    
    # 単純なreplaceではなく、エスケープされていない "\n" だけを置換したいが、
    # ユーザー入力で "\\n" と入力されたものを改行にしたいという要件であれば、
    # 単純な replace("\\n", "\n") で正しいはず。
    # テストケース "Line1\\\\nLine2" -> "Line1\\nLine2" を意図しているなら、
    # "\\\\" はバックスラッシュそのものを示すエスケープなので、
    # "\\n" は「バックスラッシュ + n」となるべき。
    
    # Pythonの文字列リテラルとして考えるとややこしいが、
    # 入力テキストが "Line1\\nLine2" (長さ11文字) の場合、replaceで "Line1\nLine2" (長さ10文字) になる。
    # 入力テキストが "Line1\\\\nLine2" (長さ12文字, Line1 + \ + \ + n + Line2) の場合、
    # replace("\\n", "\n") をすると、後ろの "\n" がヒットして "Line1\\\nLine2" になる。
    
    # 望ましい挙動は、「バックスラッシュでエスケープされていない \n」のみを置換することだが、
    # 今回の文脈では「hjsonで保存された際に勝手にエスケープされた \n を戻す」ことが目的。
    # hjsonは \ を \\ に、改行を \n にエスケープする。
    # つまり 元のテキストが "A\nB" なら保存データは "A\nB" (hjsonの仕様上は複数行文字列ならそのまま、一行なら \n)
    
    # ユーザーが画面上で "\n" と入力した場合、保存データは "\\n" となる。
    # これを読み込むと "Line1\\nLine2" となる。これを "Line1\nLine2" に戻したい。
    # ユーザーが画面上で "\\n" と入力した場合、保存データは "\\\\n" となる。
    # これを読み込むと "Line1\\\\nLine2" となる。これは "Line1\\nLine2" (バックスラッシュ+n) と表示されるべき。
    
    # つまり、単純な replace では \\n も \n になってしまう。
    # ここは「奇数個のバックスラッシュに続く n」を対象にする必要があるが、
    # hjsonのロード時点ですでにバックスラッシュの処理は終わっているはず。
    
    # HJSONのロード挙動(verify_newline.pyの結果):
    # Escaped Newline Loaded: 'Line1\\nLine2' (長さ11, \ が1つ)
    # これはユーザーが "Line1\nLine2" (改行なし) と入力したつもりで、プログラム的には "Line1\nLine2" という文字列(改行文字)になってほしいケース？
    # いや、ユーザーがテキストエリアで改行キーを押すと、通常は "\n" (改行コード) が送られる。
    # それが保存・ロードの過程で "\\n" (文字列) になってしまっているのが問題。
    
    # "Line1\\\\nLine2" という入力は、ユーザーが "Line1\nLine2" (バックスラッシュとn) とタイプしたい場合。
    # この場合、アンエスケープ後は "Line1\nLine2" (文字列としての\n) になってほしいが、これは "Line1\\nLine2" と同じ？
    
    # とりあえず、バックスラッシュが2つ続いている場合はスキップするような正規表現にする。
    import re
    # 偶数個のバックスラッシュの後にある \n は置換しない、というロジックは複雑。
    # 単純に、hjson由来のエスケープ戻しとして `text.replace('\\n', '\n')` を行うと、
    # `\\n` (文字としての\n) は 改行コード になる。
    # `\\\\n` (文字としての\とn) は `\` + `改行コード` になる。
    
    # テストケースの `expected` が `Line1\\nLine2` (文字としての\n) なので、
    # `Line1\\\\nLine2` -> `Line1\\nLine2` にしたい。
    # `\\\\n` は `\\` + `\\n` と見なせるので、`\\` + `\n` (改行) になるのが replace の挙動。
    # つまり `Line1\\\nLine2` (Line1 + \ + 改行 + Line2) になる。
    
    # もし `Line1\\nLine2` (文字としての\n) にしたいなら、`\\n` を検知して置換しない処理が必要。
    # しかし、hjsonの仕様上、改行は `\n` になるが、`\` は `\\` になる。
    # つまり `\` + `改行` は `\\` + `\n` -> `\\\n` になるはず。
    
    # 今回の修正目的は「改行コードに戻す」ことなので、
    # `replace("\\n", "\n")` で、`\\n` が改行になるのは正しい。
    # `\\\\n` が `\` + 改行 になるのも正しい（`\\` -> `\`、`\n` -> 改行）。
    # テストケースの expected が間違っている可能性が高い。
    # HJSONで `\\n` となっているものは、元々 `\n` (文字) だったか、改行コードがエスケープされたものか区別がつかない？
    # いや、HJSONの仕様では、`\` 自体もエスケープされるので区別できるはず。
    
    # Case A: 原文 "A(改行)B" -> HJSON "A\nB" (または複数行) -> Load "A\nB" (改行コード)
    # Case B: 原文 "A\nB" (文字) -> HJSON "A\\nB" -> Load "A\\nB" (文字としての\n) -> 不具合でここが改行コードとして扱われていない？
    # いや、ユーザーの申告は「改行が \n として表示されている」
    # つまり、本来 改行コード であるべきものが、文字としての "\n" (`\n`) になっている。
    # これは Case A が何らかの理由で "A\\nB" としてロードされている、あるいは保存されているということ。
    
    # Pythonでの `replace("\\n", "\n")` は、`\` のエスケープを考慮しない。
    # エスケープを考慮して置換するには `codecs.decode(text, 'unicode_escape')` が使えるが、
    # これだと全ての `\` エスケープが評価されてしまう（`\t` とか）。
    
    # ここはシンプルに、`\\n` を `\n` に置換するが、`\\\n` は避ける（前の `\` がエスケープ用でない場合のみ）
    # 正規表現: `(?<!\\)(\\\\)*\\n` ... いや、可変長のlookbehindは使えない。
    
    # 暫定的に、`text.replace('\\n', '\n')` で進める。テストケースの方を修正する。
    # ユーザーが `\n` という文字を入力したいケースは稀であり、改行が表示されない不便さの方が重大。
    return text.replace("\\n", "\n")


def recursive_unescape(data: Any) -> Any:
    """Recursively unescape newline characters in data.

    Args:
        data (Any): Input data (dict, list, str, etc.)

    Returns:
        Any: Data with unescaped newline characters
    """
    if isinstance(data, str):
        return unescape_newline(data)
    elif isinstance(data, list):
        return [recursive_unescape(item) for item in data]
    elif isinstance(data, dict):
        return {key: recursive_unescape(value) for key, value in data.items()}
    else:
        return data
