import streamlit as st
from src.utility import update_source_data, undo_last_change


def add_node_selector(id_title_list, id_title_dict, unique_id_dict, selected_unique_id):
    """右パネル上部にノード検索・選択用セレクトボックスを描画する。

    ユーザーがセレクトボックスで別のノードを選ぶと、
    query_params.selected を更新してページ全体を再描画する。
    """
    # 全ての選択肢をそのまま使用 (未選択等も含む)
    node_options = id_title_list
    if not node_options:
        return

    # 現在選択中のノードのラベルを取得
    current_label = unique_id_dict.get(selected_unique_id, "--- 未選択 ---")
    if current_label in node_options:
        current_index = node_options.index(current_label)
    else:
        current_index = 0

    selected_label = st.selectbox(
        "🔍 ノード検索",
        node_options,
        index=current_index,
        key="node_selector",
    )
    new_unique_id = id_title_dict.get(selected_label)
    # selected_unique_id と new_unique_id が異なる場合のみ、かつ現在のURLパラメータとも異なる場合のみ更新
    # ただし、UI上の選択と現在のクエリが異なる（ボタン操作等で既に遷移予定）場合はセレクトボックスによる上書きを防ぐ
    if new_unique_id and new_unique_id != selected_unique_id:
        current_param = st.query_params.get("selected")
        if current_param == selected_unique_id:
            st.query_params.selected = new_unique_id
            st.rerun(scope="app")




def _reset_new_connection_widgets():
    """
    現在のアプリケーションに関連する新規接続ウィジェットの
    セッションステートをリセットする。
    """
    app_name = st.session_state.get("app_name")
    if not app_name:
        return

    clearable_keys_for_app = st.session_state.get(
        "clearable_new_connection_keys", {}
    ).get(app_name)
    if clearable_keys_for_app:
        for key_to_clear in clearable_keys_for_app:
            if key_to_clear in st.session_state:
                del st.session_state[key_to_clear]


def add_operate_buttons(
    selected_unique_id: str,
    tmp_entity,
    requirement_manager,
    file_path,
    id_title_dict,
    unique_id_dict,
    no_new=False,
    no_add=False,
    no_remove=False,
    no_duplicate=False,
    tmp_edges=None,
    new_edges=None,
    key_suffix="",
    display_key="id",
):
    # 既存ノード編集中か新規作成中かを判定
    is_existing = selected_unique_id in unique_id_dict

    (
        new_button_column,
        duplicate_button_column,
        undo_button_column,
        add_button_column,
        update_button_column,
        remove_button_column,
    ) = st.columns([1, 1, 1, 1, 1, 1])
    with new_button_column:
        # 新規ボタンを表示
        # デフォルトエンティティが選択された状態にする
        if not no_new:
            if st.button("新規", key=f"new_button_{key_suffix}"):
                st.query_params.selected = "default"
                st.query_params.detail = "True"
                st.rerun()
    with duplicate_button_column:
        # 複製ボタンを表示（既存ノード選択時のみ有効）
        if not no_duplicate:
            if st.button("複製", key=f"duplicate_button_{key_suffix}", disabled=not is_existing):
                import uuid
                import copy

                # ノードの深いコピーを作成し、新しい unique_id を付与
                new_node = copy.deepcopy(
                    next(
                        n for n in requirement_manager.requirements["nodes"]
                        if n.get("unique_id") == selected_unique_id
                    )
                )
                new_unique_id = f"{uuid.uuid4()}".replace("-", "")
                new_node["unique_id"] = new_unique_id

                # ノードを追加
                requirement_manager.requirements["nodes"].append(new_node)

                # 元ノードの outgoing edges（source が元ノード）を複製
                # 元ノードの incoming edges（destination が元ノード）も複製
                for edge in requirement_manager.requirements["edges"][:]:
                    if edge.get("source") == selected_unique_id:
                        new_edge = copy.deepcopy(edge)
                        new_edge["source"] = new_unique_id
                        requirement_manager.requirements["edges"].append(new_edge)
                    elif edge.get("destination") == selected_unique_id:
                        new_edge = copy.deepcopy(edge)
                        new_edge["destination"] = new_unique_id
                        requirement_manager.requirements["edges"].append(new_edge)

                update_source_data(file_path, requirement_manager.requirements)
                st.query_params.selected = new_unique_id
                st.rerun()
    with undo_button_column:
        # 戻すボタンを表示
        if st.button("戻す", key=f"undo_button_{key_suffix}"):
            if undo_last_change():
                st.rerun(scope="app")
            else:
                st.error("戻せるバックアップがありません。")
    with add_button_column:
        if not no_add:
            # 追加ボタン（新規作成時のみ有効）
            if st.button("追加", key=f"add_button_{key_suffix}", disabled=is_existing):
                entity_title = tmp_entity.get(display_key, "")
                if entity_title in id_title_dict:
                    st.error("入力内容が既存のエンティティと重複しています。")
                else:
                    # 追加の場合、既存のedgeを変更する必要はない
                    added_id = requirement_manager.add(tmp_entity, tmp_edges, new_edges)
                    update_source_data(file_path, requirement_manager.requirements)
                    st.toast("エンティティを追加しました ✅")
                    _reset_new_connection_widgets()
                    st.query_params.selected = added_id
                    st.rerun()
    with update_button_column:
        # 更新ボタン（既存ノード選択時のみ有効）
        if st.button("更新", key=f"update_button_{key_suffix}", disabled=not is_existing):
            requirement_manager.update(
                selected_unique_id, tmp_entity, tmp_edges, new_edges
            )
            update_source_data(file_path, requirement_manager.requirements)
            st.toast("エンティティを更新しました ✅")
            _reset_new_connection_widgets()
            st.query_params.selected = tmp_entity[
                "unique_id"
            ]  # リセット後にselectedを設定
            st.rerun()
    with remove_button_column:
        if not no_remove:
            # 2クリック削除: 1回目で確認状態、2回目で実行
            confirm_key = f"confirm_delete_{key_suffix}"
            is_confirming = st.session_state.get(confirm_key) == selected_unique_id
            if is_confirming:
                if st.button("本当に？", key=f"remove_button_{key_suffix}", disabled=not is_existing, type="primary"):
                    requirement_manager.remove(selected_unique_id)
                    update_source_data(file_path, requirement_manager.requirements)
                    st.session_state.pop(confirm_key, None)
                    st.toast("エンティティを削除しました 🗑️")
                    st.rerun()
            else:
                if st.button("削除", key=f"remove_button_{key_suffix}", disabled=not is_existing):
                    st.session_state[confirm_key] = selected_unique_id
                    st.rerun()


