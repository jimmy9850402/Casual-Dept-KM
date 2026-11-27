import os
import streamlit as st
from pypdf import PdfReader
from docx import Document
from google import genai
from google.genai import types

# 1. 網頁基本設定
st.set_page_config(page_title="內部條款 AI 查詢助理", page_icon="📑", layout="wide")
st.title("📑 內部條款 AI 查詢助理")
st.caption("回覆範圍嚴格限定於已上傳之條款文件，不採用外部資訊。")

# 讀取後台機密設定 (API Key 與 管理員密碼)
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "123456")

if not API_KEY:
    st.error("系統尚未設定 GEMINI_API_KEY，請聯繫管理員於後台 Secrets 設定。")
    st.stop()

client = genai.Client(api_key=API_KEY)

# 2. 解析檔案文字的函式
def extract_text_from_file(uploaded_file):
    text = ""
    filename = uploaded_file.name
    if filename.endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            text += f"\n--- [{filename} 第 {i+1} 頁] ---\n{page_text}"
    elif filename.endswith(".docx"):
        doc = Document(uploaded_file)
        text += f"\n--- [{filename}] ---\n"
        text += "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    elif filename.endswith(".txt"):
        text += f"\n--- [{filename}] ---\n"
        text += uploaded_file.read().decode("utf-8", errors="ignore")
    return text

# 自動讀取 GitHub 內 docs/ 資料夾的預設條款（避免主機休眠重啟後檔案清空）
@st.cache_resource
def load_default_docs():
    default_text = ""
    loaded_files = []
    docs_dir = "docs"
    if os.path.exists(docs_dir):
        for fname in os.listdir(docs_dir):
            fpath = os.path.join(docs_dir, fname)
            if fname.endswith(".pdf"):
                reader = PdfReader(fpath)
                for i, page in enumerate(reader.pages):
                    default_text += f"\n--- [{fname} 第 {i+1} 頁] ---\n{page.extract_text() or ''}"
                loaded_files.append(fname)
            elif fname.endswith(".docx"):
                doc = Document(fpath)
                default_text += f"\n--- [{fname}] ---\n" + "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                loaded_files.append(fname)
            elif fname.endswith(".txt"):
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    default_text += f"\n--- [{fname}] ---\n" + f.read()
                loaded_files.append(fname)
    return default_text, loaded_files

# 初始化 Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_context" not in st.session_state:
    st.session_state.uploaded_context = ""
if "uploaded_filenames" not in st.session_state:
    st.session_state.uploaded_filenames = []

default_context, default_files = load_default_docs()

# 3. 側邊欄：管理員上傳區
with st.sidebar:
    st.header("📂 條款知識庫管理")
    
    # 顯示目前已載入的文件
    all_files = default_files + st.session_state.uploaded_filenames
    if all_files:
        st.success(f"目前生效條款（共 {len(all_files)} 份）：")
        for f in all_files:
            st.markdown(f"- `{f}`")
    else:
        st.warning("目前尚未載入任何條款，請由管理員上傳。")

    st.divider()
    st.subheader("🔒 管理員即時上傳（做法 B）")
    pwd = st.text_input("輸入管理員密碼解鎖上傳", type="password")
    
    if pwd == ADMIN_PASSWORD:
        uploaded_files = st.file_uploader(
            "上傳條款文件 (支援 PDF, Word, TXT)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True
        )
        if st.button("載入並更新知識庫", type="primary"):
            if uploaded_files:
                combined_text = ""
                names = []
                with st.spinner("正在解析文件..."):
                    for uf in uploaded_files:
                        combined_text += extract_text_from_file(uf)
                        names.append(uf.name)
                st.session_state.uploaded_context = combined_text
                st.session_state.uploaded_filenames = names
                st.success("條款更新完成！現在可以開始提問。")
                st.rerun()
            else:
                st.warning("請先選擇檔案。")
    elif pwd:
        st.error("密碼錯誤")

    st.divider()
    if st.button("🗑️ 清除對話紀錄"):
        st.session_state.messages = []
        st.rerun()

# 合併預設條款與網頁上傳條款
full_context = default_context + "\n" + st.session_state.uploaded_context

# 4. 顯示歷史對話
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 5. 處理使用者提問
if prompt := st.chat_input("請輸入您想查詢的條款問題..."):
    if not full_context.strip():
        st.warning("目前知識庫是空的，請先由左側上傳條款文件。")
        st.stop()

    # 顯示使用者問題
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 嚴格防幻覺 System Prompt
    system_instruction = f"""
你是一位極度嚴謹的企業條款查詢助理。
你「只能」根據下方【參考條款】的內容來回答使用者的問題。

【最高原則】
1. 嚴禁使用你的外部知識、常識或自行推測。
2. 如果【參考條款】中沒有明確提及答案，請直接回覆：「抱歉，目前提供的條款中查無相關資訊，請洽詢相關承辦人員。」絕對不要嘗試編造。
3. 回答時，請務必標註引用的「檔案名稱」或「頁碼 / 條文內容」，方便使用者核對。
4. 請使用繁體中文，語氣專業、條理分明。

【參考條款】
{full_context}
"""

    # 組合對話歷史
    contents = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))

    # 呼叫 Gemini API (temperature=0.0 關閉發散)
    with st.chat_message("assistant"):
        with st.spinner("正在檢索條款並生成回覆..."):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.0,
                    ),
                )
                answer = response.text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"系統發生錯誤，請稍後再試。（錯誤訊息：{e}）")
