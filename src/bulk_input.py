"""一括入力機能モジュール。

テキストベースでエンティティの一括作成・削除と接続接続の設定・削除を行う。
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
    """既存エンティティに仮ID（通番）を付与したマップを返す。"""
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
    content_field: str = "title",
    default_color: str = "None",
    extra_fields: Dict = None,
    metadata_columns: List[Dict] = None,
) -> Tuple[List[Dict], Dict[int, Dict], Set[str]]:
    """テキストからエンティティの追加・削除リストを生成する。

    Args:
        text: 1行1エンティティのテキスト
        start_id: 仮IDの開始番号
        default_type: デフォルトのエンティティタイプ
        existing_map: 既存エンティティの仮IDマップ
        content_field: テキストを格納するフィールド名（PFD/CCPM: "title", CRT: "id"）
        default_color: デフォルトの色
        extra_fields: エンティティに追加するフィールド（CCPM の days, remains 等）
        metadata_columns: カンマ区切りで入力可能なメタデータの定義リスト
            例: [{"key": "days", "name": "日数", "type": int, "default": 1}]

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
        
        parts = [p.strip() for p in line.split(",")]
        main_text = parts[0]
        
        entity = {
            "type": default_type,
            content_field: main_text,
            "color": default_color,
            "unique_id": unique_id,
        }
        if extra_fields:
            entity.update(extra_fields)
            
        meta_preview_parts = []
        if metadata_columns:
            for i, col in enumerate(metadata_columns):
                val = col.get("default")
                if i + 1 < len(parts) and parts[i+1]:
                    raw_val = parts[i+1]
                    col_type = col.get("type", str)
                    try:
                        # bool型の場合は文字列の"true"/"false"等をハンドルする想定だが、ここは単純に
                        if col_type == bool:
                            val = raw_val.lower() in ("true", "1", "yes", "on")
                        else:
                            val = col_type(raw_val)
                    except ValueError:
                        pass
                entity[col["key"]] = val
                meta_preview_parts.append(f"{col.get('name', col['key'])}:{val}")

        entities_to_add.append(entity)
        
        preview_suffix = f" [{', '.join(meta_preview_parts)}]" if meta_preview_parts else f" [{default_type}]"
        new_temp_map[temp_id] = {
            "unique_id": unique_id,
            "label": main_text,
            "preview_suffix": preview_suffix,
        }
    return entities_to_add, new_temp_map, ids_to_delete


def parse_connections(
    text: str,
    full_temp_map: Dict[int, Dict],
    existing_edges: List[Dict],
    extra_edge_fields: Dict = None,
) -> Tuple[List[Dict], Set[Tuple[str, str]], List[str]]:
    """接続記法から接続の追加・削除リストを生成する。

    書式:
      - 「1 3」 — #1→#3 の接続（従来形式・2つの数字）
      - 「2 3 4 > 5 6」 — #2→#5, #2→#6, #3→#5, #3→#6, #4→#5, #4→#6 の直積接続

    既存接続と一致する場合は削除扱い（トグル動作）。

    Returns:
        (追加接続リスト, 削除対象(source,destination)セット, エラーメッセージリスト)
    """
    edges_to_add = []
    edges_to_remove: Set[Tuple[str, str]] = set()
    errors = []
    lines = text.strip().split("\n") if text.strip() else []

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        # 「>」を含む場合: 複数対複数の直積接続
        if ">" in line:
            halves = line.split(">")
            if len(halves) != 2:
                errors.append(f"行{line_num}: 「{line}」— '>' は1行に1つだけ使用してください")
                continue
            src_tokens = halves[0].split()
            dst_tokens = halves[1].split()
            if not src_tokens or not dst_tokens:
                errors.append(f"行{line_num}: 「{line}」— '>' の両側に仮IDを指定してください")
                continue
            # 各トークンを整数に変換
            src_ids = []
            dst_ids = []
            has_error = False
            for token in src_tokens:
                try:
                    src_ids.append(int(token))
                except ValueError:
                    errors.append(f"行{line_num}: 「{token}」は数字ではありません")
                    has_error = True
            for token in dst_tokens:
                try:
                    dst_ids.append(int(token))
                except ValueError:
                    errors.append(f"行{line_num}: 「{token}」は数字ではありません")
                    has_error = True
            if has_error:
                continue
            # 存在チェック・直積ペア生成
            pairs = []
            for sid in src_ids:
                if sid not in full_temp_map:
                    errors.append(f"行{line_num}: 仮ID #{sid} が存在しません")
                    has_error = True
            for did in dst_ids:
                if did not in full_temp_map:
                    errors.append(f"行{line_num}: 仮ID #{did} が存在しません")
                    has_error = True
            if has_error:
                continue
            for sid in src_ids:
                for did in dst_ids:
                    if sid == did:
                        errors.append(f"行{line_num}: #{sid} の自己参照はスキップします")
                        continue
                    pairs.append((sid, did))
        else:
            # 従来形式: 「1 3」（数字2つ）
            parts = line.split()
            if len(parts) != 2:
                errors.append(f"行{line_num}: 「{line}」— 数字2つをスペース区切り、または '>' で複数指定してください")
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
            pairs = [(src_id, dst_id)]

        # ペアごとに追加 or 削除を判定
        for src_id, dst_id in pairs:
            src_uid = full_temp_map[src_id]["unique_id"]
            dst_uid = full_temp_map[dst_id]["unique_id"]

            is_existing = any(
                e.get("source") == src_uid and e.get("destination") == dst_uid
                for e in existing_edges
            )
            if is_existing:
                edges_to_remove.add((src_uid, dst_uid))
            else:
                edge = {
                    "source": src_uid,
                    "destination": dst_uid,
                    "comment": "",
                    "type": "arrow",
                }
                if extra_edge_fields:
                    edge.update(extra_edge_fields)
                edges_to_add.append(edge)

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
    # エンティティ削除（関連接続も同時削除）
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
    # 接続追加
    reqs.setdefault("edges", []).extend(add_edges)
    # 接続削除
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
    content_field: str = "title",
    extra_fields: Dict = None,
    extra_edge_fields: Dict = None,
    metadata_columns: List[Dict] = None,
):
    """一括入力UIを描画する。

    Args:
        content_field: 入力テキストを格納するフィールド名（PFD/CCPM: 'title', CRT: 'id'）
        extra_fields: エンティティに追加するデフォルトフィールド（CCPMの days, remains 等）
        extra_edge_fields: 接続に追加するデフォルトフィールド（CRTの and 等）
        metadata_columns: カンマ区切りで入力可能なメタデータの定義リスト
    """

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

    # エンティティ入力のプレースホルダー・キャプションを動的生成
    format_hint = "テキスト"
    placeholder_example = "プロセスA"
    if metadata_columns:
        meta_names = [col.get("name", col["key"]) for col in metadata_columns]
        format_hint += f", {', '.join(meta_names)}"
        example_vals = [str(col.get("default", "")) for col in metadata_columns]
        placeholder_example += f", {', '.join(example_vals)}"

    st.caption(f"1行1エンティティ（#{start_id}～ 自動採番 / 既存の番号で削除）")
    entity_text = st.text_area(
        "エンティティ入力",
        height=150,
        key=f"{page_key_prefix}_bulk_entities_{counter}",
        label_visibility="collapsed",
        placeholder=f"書式: {format_hint}\n例:\n{placeholder_example}\n3",
    )

    # 接続関係入力
    st.caption("接続関係（未存在→追加 / 既存→削除）")
    connection_text = st.text_area(
        "接続関係入力",
        height=100,
        key=f"{page_key_prefix}_bulk_connections_{counter}",
        label_visibility="collapsed",
        placeholder="仮IDをスペース区切りで入力（'>'で複数対複数）\n例:\n1 3\n2 3 4 > 5 6",
    )

    # パース
    new_entities, new_temp_map, del_entity_ids = parse_entities(
        entity_text, start_id, default_type, existing_map,
        content_field=content_field, extra_fields=extra_fields,
        metadata_columns=metadata_columns,
    )
    full_temp_map = {**existing_map, **new_temp_map}
    current_edges = requirement_manager.requirements.get("edges", [])
    add_edges, rm_edge_keys, conn_errors = parse_connections(
        connection_text, full_temp_map, current_edges,
        extra_edge_fields=extra_edge_fields,
    )

    # プレビュー
    has_changes = bool(new_entities or del_entity_ids or add_edges or rm_edge_keys)
    if has_changes:
        st.write("##### プレビュー")
        for temp_id, info in new_temp_map.items():
            st.text(f"  ＋ #{temp_id}  {info['label']}  {info.get('preview_suffix', '')}")
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
