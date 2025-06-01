import streamlit as st
from src.utility import update_source_data


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
    tmp_edges=None,
    new_edges=None,
):
    (
        new_button_column,
        _,
        add_button_column,
        update_button_column,
        remove_button_column,
    ) = st.columns([1, 2, 1, 1, 1])
    with new_button_column:
        # 新規ボタンを表示
        # デフォルトエンティティが選択された状態にする
        if not no_new:
            if st.button("新規"):
                st.query_params.selected = "default"
                st.rerun()
    with add_button_column:
        if not no_add:
            # 追加ボタンを表示
            if st.button("追加"):
                if (tmp_entity["id"]) in id_title_dict:
                    st.error("IDが既存のエンティティと重複しています。")
                else:
                    # 追加の場合、既存のedgeを変更する必要はない
                    added_id = requirement_manager.add(tmp_entity, tmp_edges, new_edges)
                    update_source_data(file_path, requirement_manager.requirements)
                    st.write("エンティティを追加しました。")
                    st.query_params.selected = added_id
                    st.rerun()
    with update_button_column:
        # 更新ボタンを表示
        if st.button("更新"):
            if not selected_unique_id in unique_id_dict:
                st.error("更新すべきエンティティがありません。")
            else:
                requirement_manager.update(
                    selected_unique_id, tmp_entity, tmp_edges, new_edges
                )
                update_source_data(file_path, requirement_manager.requirements)
                st.write("エンティティを更新しました。")
                _reset_new_connection_widgets()
                st.query_params.selected = tmp_entity[
                    "unique_id"
                ]  # リセット後にselectedを設定
                st.rerun()
    with remove_button_column:
        if not no_remove:
            # 削除ボタンを表示
            if st.button("削除"):
                if not (tmp_entity["id"]) in id_title_dict:
                    st.error("削除すべきエンティティがありません。")
                else:
                    requirement_manager.remove(selected_unique_id)
                    update_source_data(file_path, requirement_manager.requirements)
                    st.write("エンティティを削除しました。")
                    st.rerun()
