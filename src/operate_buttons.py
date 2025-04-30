import streamlit as st
from src.utility import update_source_data


def add_operate_buttons(
    tmp_entity,
    requirement_manager,
    file_path,
    id_title_dict,
    unique_id_dict,
    no_add=False,
    from_relations=None,
):
    _, add_button_column, update_button_column, remove_button_column = st.columns(
        [2, 1, 1, 1]
    )
    with add_button_column:
        if not no_add:
            # 追加ボタンを表示
            if st.button("追加"):
                if (tmp_entity["id"]) in id_title_dict:
                    st.error("IDが既存のエンティティと重複しています。")
                else:
                    added_id = requirement_manager.add(tmp_entity)
                    if from_relations is not None:
                        requirement_manager.update_reverse_relations(
                            tmp_entity["unique_id"], from_relations
                        )
                    update_source_data(file_path, requirement_manager.requirements)
                    st.write("エンティティを追加しました。")
                    st.query_params.selected = added_id
                    st.rerun()
    with update_button_column:
        # 更新ボタンを表示
        if st.button("更新"):
            if not (tmp_entity["unique_id"]) in unique_id_dict:
                st.error("更新すべきエンティティがありません。")
            else:
                requirement_manager.update(tmp_entity)
                if from_relations is not None:
                    requirement_manager.update_reverse_relations(
                        tmp_entity["unique_id"], from_relations
                    )
                update_source_data(file_path, requirement_manager.requirements)
                st.write("エンティティを更新しました。")
                st.query_params.selected = tmp_entity["unique_id"]
                st.rerun()
    with remove_button_column:
        # 削除ボタンを表示
        if st.button("削除"):
            if not (tmp_entity["id"]) in id_title_dict:
                st.error("削除すべきエンティティがありません。")
            else:
                requirement_manager.remove(tmp_entity["unique_id"])
                update_source_data(file_path, requirement_manager.requirements)
                st.write("エンティティを削除しました。")
                st.rerun()
