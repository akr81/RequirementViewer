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
from typing import Dict, List, Set, Tuple


def build_temp_id_map(nodes: List[Dict], display_key: str = "title") -> Dict[int, Dict]:
    """既存ノードに仮ID（通番）を付与したマップを返す。"""
    temp_map = {}
    for i, node in enumerate(nodes, start=1):
        label = node.get(display_key, "") or node.get("id", "") or node.get("unique_id", "")
        label = label.replace("\n", " ").replace("\r", "")
        temp_map[i] = {
            "unique_id": node.get("unique_id", ""),
            "label": label,
        }
    return temp_map


def parse_entities(
    text: str,
    start_id: int,
    default_type: str,
    existing_map: Dict[int, Dict],
    default_color: str = "None",
) -> Tuple[List[Dict], Dict[int, Dict], Set[str]]:
    """テキストからエンティティの追加・削除リストを生成する。

    Returns:
        (新規エンティティリスト, 新規分の仮IDマップ, 削除対象unique_idセット)
    """
    entities_to_add = []
    new_temp_map = {}
    ids_to_delete: Set[str] = set()
    lines = text.strip().split("\n") if text.strip() else []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 数字のみの行で既存仮IDに一致 → 削除
        try:
            num = int(line)
            if num in existing_map:
                ids_to_delete.add(existing_map[num]["unique_id"])
                continue
        except ValueError:
            pass
        # テキスト行 → 新規エンティティ
        temp_id = start_id + len(entities_to_add)
        unique_id = f"{uuid.uuid4()}".replace("-", "")
        entities_to_add.append({
            "type": default_type,
            "id": "",
            "title": line,
            "color": default_color,
            "unique_id": unique_id,
        })
        new_temp_map[temp_id] = {
            "unique_id": unique_id,
            "label": line,
        }
    return entities_to_add, new_temp_map, ids_to_delete


def parse_connections(
    text: str,
    full_temp_map: Dict[int, Dict],
    existing_edges: List[Dict],
) -> Tuple[List[Dict], Set[Tuple[str, str]], List[str]]:
    """接続記法からエッジの追加・削除リストを生成する。

    Returns:
        (追加エッジリスト, 削除対象(source,destination)セット, エラーメッセージリスト)
    """
    edges_to_add = []
    edges_to_remove: Set[Tuple[str, str]] = set()
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
            src_id, dst_id = int(parts[0]), int(parts[1])
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

        # 既存エッジに同じ source→destination があれば削除、なければ追加
        is_existing = any(
            e.get("source") == src_uid and e.get("destination") == dst_uid
            for e in existing_edges
        )
        if is_existing:
            edges_to_remove.add((src_uid, dst_uid))
        else:
            edges_to_add.append({
                "source": src_uid,
                "destination": dst_uid,
                "comment": "",
                "type": "arrow",
            })

    return edges_to_add, edges_to_remove, errors


def _uid_to_display(uid: str, temp_map: Dict[int, Dict]) -> str:
    """unique_id から「#仮ID ラベル」の表示文字列を逆引きする。"""
    for k, v in temp_map.items():
        if v["unique_id"] == uid:
            return f"#{k} {v['label']}"
    return uid


def _apply_changes(
    requirement_manager,
    file_path: str,
    new_entities: List[Dict],
    del_entity_ids: Set[str],
    add_edges: List[Dict],
    rm_edge_keys: Set[Tuple[str, str]],
):
    """データへの追加・削除を適用してファイルに保存する。"""
    from src.file_io import update_source_data

    reqs = requirement_manager.requirements
    # エンティティ追加
    reqs["nodes"].extend(new_entities)
    # エンティティ削除（関連エッジも同時削除）
    if del_entity_ids:
        reqs["nodes"] = [
            n for n in reqs["nodes"]
            if n.get("unique_id") not in del_entity_ids
        ]
        reqs["edges"] = [
            e for e in reqs.get("edges", [])
            if e.get("source") not in del_entity_ids
            and e.get("destination") not in del_entity_ids
        ]
    # エッジ追加
    reqs.setdefault("edges", []).extend(add_edges)
    # エッジ削除
    if rm_edge_keys:
        reqs["edges"] = [
            e for e in reqs.get("edges", [])
            if (e.get("source"), e.get("destination")) not in rm_edge_keys
        ]

    update_source_data(file_path, reqs)


def render_bulk_input_ui(
    nodes: List[Dict],
    requirement_manager,
    file_path: str,
    type_list: List[str],
    display_key: str = "title",
    page_key_prefix: str = "pfd",
):
    """一括入力UIを描画する。"""

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
    add_edges, rm_edge_keys, conn_errors = parse_connections(
        connection_text, full_temp_map, current_edges
    )

    # プレビュー
    has_changes = bool(new_entities or del_entity_ids or add_edges or rm_edge_keys)
    if has_changes:
        st.write("##### プレビュー")
        for temp_id, info in new_temp_map.items():
            st.text(f"  ＋ #{temp_id}  {info['label']}  [{default_type}]")
        for uid in del_entity_ids:
            st.text(f"  ー {_uid_to_display(uid, existing_map)}  [削除]")
        for edge in add_edges:
            src = _uid_to_display(edge["source"], full_temp_map)
            dst = _uid_to_display(edge["destination"], full_temp_map)
            st.text(f"  ＋ {src}  →  {dst}")
        for src_uid, dst_uid in rm_edge_keys:
            src = _uid_to_display(src_uid, full_temp_map)
            dst = _uid_to_display(dst_uid, full_temp_map)
            st.text(f"  ー {src}  →  {dst}")

    # エラー表示
    for err in conn_errors:
        st.error(err)

    # 一括実行ボタン
    can_execute = has_changes and not conn_errors
    add_count = len(new_entities) + len(add_edges)
    del_count = len(del_entity_ids) + len(rm_edge_keys)
    label_parts = []
    if add_count:
        label_parts.append(f"追加{add_count}")
    if del_count:
        label_parts.append(f"削除{del_count}")
    button_label = f"📥 一括実行（{' / '.join(label_parts or ['0件'])}）"

    if st.button(button_label, disabled=not can_execute,
                 key=f"{page_key_prefix}_bulk_add_button"):
        _apply_changes(
            requirement_manager, file_path,
            new_entities, del_entity_ids, add_edges, rm_edge_keys,
        )
        st.session_state[counter_key] = counter + 1
        # toast メッセージ
        parts = []
        if new_entities:
            parts.append(f"+{len(new_entities)}エンティティ")
        if del_entity_ids:
            parts.append(f"-{len(del_entity_ids)}エンティティ")
        if add_edges:
            parts.append(f"+{len(add_edges)}接続")
        if rm_edge_keys:
            parts.append(f"-{len(rm_edge_keys)}接続")
        st.toast(f"{'  '.join(parts)} を実行しました ✅")
        st.rerun(scope="app")
