"""一括入力機能モジュール。

テキストベースでエンティティの一括作成・削除と接続関係の設定・削除を行う。
仮ID（#1, #2, ...）はUI表示のみに使用し、データには保存しない。

エンティティ入力欄:
  - テキスト行 → 新規エンティティ作成
  - 数字のみ（既存仮IDに一致） → 該当エンティティを削除

接続関係入力欄:
  - "1 3" → #1→#3 の接続が存在しなければ追加、存在すれば削除
"""
import streamlit as st
import uuid
from typing import Dict, List, Tuple


def build_temp_id_map(nodes: List[Dict], display_key: str = "title") -> Dict[int, Dict]:
    """既存ノードに仮ID（通番）を付与したマップを返す。"""
    temp_map = {}
    for i, node in enumerate(nodes, start=1):
        label = node.get(display_key, "") or node.get("id", "") or node.get("unique_id", "")
        label = label.replace("\n", " ").replace("\r", "")
        temp_map[i] = {
            "unique_id": node.get("unique_id", ""),
            "label": label,
            "is_new": False,
        }
    return temp_map


def parse_entities(
    text: str,
    start_id: int,
    default_type: str,
    existing_map: Dict[int, Dict],
    default_color: str = "None",
) -> Tuple[List[Dict], Dict[int, Dict], List[str]]:
    """テキストからエンティティの追加・削除リストを生成する。

    Returns:
        (新規エンティティリスト, 新規分の仮IDマップ, 削除対象unique_idリスト)
    """
    entities_to_add = []
    new_temp_map = {}
    ids_to_delete = []
    lines = text.strip().split("\n") if text.strip() else []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 数字のみの行で既存仮IDに一致 → 削除
        try:
            num = int(line)
            if num in existing_map and not existing_map[num]["is_new"]:
                ids_to_delete.append(existing_map[num]["unique_id"])
                continue
        except ValueError:
            pass
        # テキスト行 → 新規エンティティ
        temp_id = start_id + len(entities_to_add)
        unique_id = f"{uuid.uuid4()}".replace("-", "")
        entity = {
            "type": default_type,
            "id": "",
            "title": line,
            "color": default_color,
            "unique_id": unique_id,
        }
        entities_to_add.append(entity)
        new_temp_map[temp_id] = {
            "unique_id": unique_id,
            "label": line,
            "is_new": True,
        }
    return entities_to_add, new_temp_map, ids_to_delete


def parse_connections(
    text: str,
    full_temp_map: Dict[int, Dict],
    existing_edges: List[Dict],
) -> Tuple[List[Dict], List[Dict], List[str]]:
    """接続記法からエッジの追加・削除リストを生成する。

    Returns:
        (追加エッジリスト, 削除エッジリスト, エラーメッセージリスト)
    """
    edges_to_add = []
    edges_to_remove = []
    errors = []
    lines = text.strip().split("\n") if text.strip() else []

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            errors.append(f"行{line_num}: 「{line}」— 数字2つをスペース区切りで入力してください")
            continue
        try:
            src_id = int(parts[0])
            dst_id = int(parts[1])
        except ValueError:
            errors.append(f"行{line_num}: 「{line}」— 数字以外が含まれています")
            continue
        if src_id not in full_temp_map:
            errors.append(f"行{line_num}: 仮ID #{src_id} が存在しません")
            continue
        if dst_id not in full_temp_map:
            errors.append(f"行{line_num}: 仮ID #{dst_id} が存在しません")
            continue
        if src_id == dst_id:
            errors.append(f"行{line_num}: 自己参照は設定できません")
            continue

        src_uid = full_temp_map[src_id]["unique_id"]
        dst_uid = full_temp_map[dst_id]["unique_id"]

        existing_edge = next(
            (e for e in existing_edges
             if e.get("source") == src_uid and e.get("destination") == dst_uid),
            None
        )
        if existing_edge:
            edges_to_remove.append(existing_edge)
        else:
            edges_to_add.append({
                "source": src_uid,
                "destination": dst_uid,
                "comment": "",
                "type": "arrow",
            })

    return edges_to_add, edges_to_remove, errors


def _format_edge_label(edge: Dict, full_temp_map: Dict[int, Dict]) -> str:
    """エッジの仮IDとラベルを逆引きして表示用文字列を返す。"""
    src_info = next(
        (f"#{k} {v['label']}" for k, v in full_temp_map.items()
         if v["unique_id"] == edge.get("source")),
        edge.get("source", "?")
    )
    dst_info = next(
        (f"#{k} {v['label']}" for k, v in full_temp_map.items()
         if v["unique_id"] == edge.get("destination")),
        edge.get("destination", "?")
    )
    return f"{src_info}  →  {dst_info}"


def render_bulk_input_ui(
    nodes: List[Dict],
    requirement_manager,
    file_path: str,
    type_list: List[str],
    display_key: str = "title",
    page_key_prefix: str = "pfd",
):
    """一括入力UIを描画する。"""
    from src.file_io import update_source_data

    # カウンターベースのキー: 実行成功時にインクリメントし、
    # 新しいキーのウィジェットが空の状態で生成される
    counter_key = f"{page_key_prefix}_bulk_counter"
    counter = st.session_state.get(counter_key, 0)

    # デフォルトタイプ選択
    default_type = st.selectbox(
        "デフォルトタイプ",
        type_list,
        key=f"{page_key_prefix}_bulk_default_type",
    )

    # 既存エンティティの仮IDマッピング
    existing_map = build_temp_id_map(nodes, display_key)
    start_id = len(existing_map) + 1

    # エンティティ入力
    st.caption(f"1行1エンティティ（#{start_id}～ 自動採番 / 既存の番号で削除）")
    entity_text = st.text_area(
        "エンティティ入力",
        height=150,
        key=f"{page_key_prefix}_bulk_entities_{counter}",
        label_visibility="collapsed",
        placeholder="テキスト → 新規追加\n数字のみ → 該当エンティティを削除\n例:\nプロセスA\n3",
    )

    # 接続関係入力
    st.caption("接続関係（未存在→追加 / 既存→削除）")
    connection_text = st.text_area(
        "接続関係入力",
        height=100,
        key=f"{page_key_prefix}_bulk_connections_{counter}",
        label_visibility="collapsed",
        placeholder="仮IDをスペース区切りで入力\n例:\n1 3\n2 4",
    )

    # パース
    new_entities, new_temp_map, del_entity_ids = parse_entities(
        entity_text, start_id, default_type, existing_map
    )
    full_temp_map = {**existing_map, **new_temp_map}
    current_edges = requirement_manager.requirements.get("edges", [])
    add_edges, rm_edges, conn_errors = parse_connections(
        connection_text, full_temp_map, current_edges
    )

    # プレビュー
    has_changes = new_entities or del_entity_ids or add_edges or rm_edges
    if has_changes:
        st.write("##### プレビュー")
        for temp_id, info in new_temp_map.items():
            st.text(f"  ＋ #{temp_id}  {info['label']}  [{default_type}]")
        for uid in del_entity_ids:
            info = next(
                (v for v in existing_map.values() if v["unique_id"] == uid), None
            )
            label = info["label"] if info else uid
            tid = next(
                (k for k, v in existing_map.items() if v["unique_id"] == uid), "?"
            )
            st.text(f"  ー #{tid}  {label}  [削除]")
        for edge in add_edges:
            st.text(f"  ＋ {_format_edge_label(edge, full_temp_map)}")
        for edge in rm_edges:
            st.text(f"  ー {_format_edge_label(edge, full_temp_map)}")

    # エラー表示
    for err in conn_errors:
        st.error(err)

    # 一括実行ボタン
    can_execute = has_changes and not conn_errors
    add_count = len(new_entities) + len(add_edges)
    del_count = len(del_entity_ids) + len(rm_edges)
    label_parts = []
    if add_count:
        label_parts.append(f"追加{add_count}")
    if del_count:
        label_parts.append(f"削除{del_count}")
    button_label = f"📥 一括実行（{' / '.join(label_parts or ['0件'])}）"

    if st.button(button_label, disabled=not can_execute,
                 key=f"{page_key_prefix}_bulk_add_button"):
        # エンティティ追加
        for e in new_entities:
            requirement_manager.requirements["nodes"].append(e)
        # エンティティ削除（関連エッジも削除）
        if del_entity_ids:
            requirement_manager.requirements["nodes"] = [
                n for n in requirement_manager.requirements["nodes"]
                if n.get("unique_id") not in del_entity_ids
            ]
            requirement_manager.requirements["edges"] = [
                e for e in requirement_manager.requirements.get("edges", [])
                if e.get("source") not in del_entity_ids
                and e.get("destination") not in del_entity_ids
            ]
        # エッジ追加
        for edge in add_edges:
            requirement_manager.requirements["edges"].append(edge)
        # エッジ削除
        if rm_edges:
            rm_set = {(e["source"], e["destination"]) for e in rm_edges}
            requirement_manager.requirements["edges"] = [
                e for e in requirement_manager.requirements.get("edges", [])
                if (e.get("source"), e.get("destination")) not in rm_set
            ]

        update_source_data(file_path, requirement_manager.requirements)

        # カウンターインクリメント → 次回描画で空のウィジェットが生成
        st.session_state[counter_key] = counter + 1

        # toast メッセージ
        parts = []
        if new_entities:
            parts.append(f"+{len(new_entities)}エンティティ")
        if del_entity_ids:
            parts.append(f"-{len(del_entity_ids)}エンティティ")
        if add_edges:
            parts.append(f"+{len(add_edges)}接続")
        if rm_edges:
            parts.append(f"-{len(rm_edges)}接続")
        st.toast(f"{'  '.join(parts)} を実行しました ✅")

        # フルリランでダイアグラム列も再描画
        st.rerun(scope="app")
