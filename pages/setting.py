import streamlit as st
import hjson
import datetime
import shutil

# Streamlit のレイアウトをワイドに設定
st.set_page_config(layout="wide")

st.title("Setting")

st.write("## 現在の設定")

st.write(st.session_state.config_data)


data_key = st.session_state.app_data[st.session_state.app_name]["data"]
postfix_new_file = st.session_state.app_data[st.session_state.app_name]["postfix"]
if data_key in st.session_state.config_data:
    data_file = st.session_state.config_data[data_key]
else:
    data_file = "指定なし"
st.write(f"データファイル: {data_file}")

st.write("## 読み込みファイルの変更")

# ファイルを変更
file_path = None
uploaded_file = st.file_uploader(
    "ファイル読み込み・アップロード", type=["json", "hjson"]
)
file_path = st.text_input(
    "ローカルファイルのパスを入力", st.session_state.config_data.get(data_key, "")
)
create_new = st.button("新規ファイル作成")
if create_new:
    # YYYYMMDD_hhmmssでファイル名を作成
    now = datetime.datetime.now()
    file_path = now.strftime("%Y%m%d_%H%M%S") + f"_{postfix_new_file}.json"

    if st.session_state.app_name == "Evaporating Cloud Viewer":
        # defaultファイルをコピー
        shutil.copyfile("default/ec.json", file_path)
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("[]")

if file_path is not None:
    # ファイルが選択された場合、configに保存
    with open("setting/config.json", "r", encoding="utf-8") as f:
        config = hjson.load(f)
    config[data_key] = file_path
    with open("setting/config.json", "w", encoding="utf-8") as f:
        hjson.dump(config, f, ensure_ascii=False, indent=4)

    st.info("ファイルを設定しました。")
