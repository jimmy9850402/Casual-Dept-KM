import os
import streamlit as st
from pypdf import PdfReader
from docx import Document
from google import genai
from google.genai import types

# 1. 網頁基本設定
st.set_page_config(
    page_title="內部條款 AI 查詢助理",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 注入現代化富邦配色 CSS (富邦深藍 #005BAC / 富邦亮藍 #008CD6 / 富邦綠 #009944)
st.markdown("""
<style>
    /* 全局背景與字體 */
    .stApp {
        background-color: #F4F7FA;
        font-family: "Microsoft JhengHei", "PingFang TC", -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* 頂部漸層品牌橫幅 */
    .fubon-banner {
        background: linear-gradient(135deg, #004B8D 0%, #008CD6 65%, #009944 100%);
        padding: 1.6rem 2rem;
        border-radius: 16px;
        color: #FFFFFF;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(0, 91, 172, 0.16);
    }
    .fubon-banner h1 {
        margin: 0;
        font-size: 1.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #FFFFFF !important;
    }
    .fubon-banner p {
        margin: 0.45rem 0 0 0;
        font-size: 0.95rem;
        opacity: 0.92;
        color: #EAF6FF !important;
    }
    .fubon-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.18);
        border: 1px solid rgba(255, 255, 255, 0.35);
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 0.6rem;
        letter-spacing: 0.5px;
    }

    /* 側邊欄樣式 */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        color: #005BAC;
    }

    /* 檔案標籤卡片 */
    .doc-pill {
        background-color: #EDF7FD;
        border-left: 4px solid #008CD6;
        color: #004B8D;
        padding: 0.45rem 0.75rem;
        border-radius: 6px;
        font-size: 0.85rem;
        margin-bottom: 0.4rem;
        font-weight: 500;
        word-break: break-all;
    }

    /* 按鈕樣式：富邦藍漸層 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #0077C8 0%, #009944 100%);
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button[kind="primary"]:hover {
        opacity: 0.92;
        box-shadow: 0 4px 12px rgba(0, 140, 214, 0.3);
    }
    .stButton > button[kind="secondary"] {
        border: 1px solid #CBD5E1;
        color: #334155;
        border-radius: 8px;
        background-color: #FFFFFF;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #008CD6;
        color: #008CD6;
    }

    /* 聊天訊息氣泡優化 */
    div[data-testid="stChatMessage"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }

    /* 底部輸入框聚焦外框改為富邦藍 */
    div[data-testid="stChatInput"] textarea:focus {
        border-color: #008CD6 !important;
        box-shadow: 0 0 0 1px #008CD6 !important;
    }

    /* 隱藏右下角多餘浮水印 */
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# 頂部品牌橫幅
st.markdown("""
<div class="fubon-banner">
    <div class="fubon-badge">INTERNAL POLICY AI ASSISTANT</div>
    <h1>🛡️ 內部條款 AI 查詢助理</h1>
    <p>回覆範圍嚴格限定於已載入之內部條款文件，附帶出處依據，不採用外部資訊。</p>
</div>
""", unsafe_allow_html=True)

# 3. 讀取後台機密設定 (API Key 與 管理員密碼)
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "123456")

if not API_KEY:
    st.error("系統尚未設定 GEMINI_API_KEY，請聯繫管理員於後台 Secrets 設定。")
    st.stop()

client = genai.Client(api_key=API_KEY)

# 4. 解析檔案文字的函式
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

# 自動讀取 GitHub 內 docs/ 資料夾的預設條款
@st.cache_resource
def load_default_docs():
    default_text = ""
    loaded_files = []
    docs_dir = "docs"
    if os.path.exists(docs_dir):
        for fname in sorted(os.listdir(docs_dir)):
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

# 5. 側邊欄：條款知識庫管理
with st.sidebar:
    st.markdown("### 📂 條款知識庫狀態")
    
    all_files = default_files + st.session_state.uploaded_filenames
    if all_files:
        st.markdown(f"<span style='color:#009944; font-weight:600;'>● 已啟用 {len(all_files)} 份條款文件</span>", unsafe_allow_html=True)
        for f in all_files:
            st.markdown(f"<div class='doc-pill'>📄 {f}</div>", unsafe_allow_html=True)
    else:
        st.warning("目前尚未載入任何條款，請由下方管理員區上傳。")

    st.divider()
    st.markdown("### 🔒 管理員即時上傳")
    pwd = st.text_input("輸入管理員密碼解鎖", type="password", placeholder="請輸入密碼後按 Enter")
    
    if pwd == ADMIN_PASSWORD:
        uploaded_files = st.file_uploader(
            "上傳條款文件 (PDF / Word / TXT)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True
        )
        if st.button("載入並更新知識庫", type="primary", use_container_width=True):
            if uploaded_files:
                combined_text = ""
                names = []
                with st.spinner("正在解析文件內容..."):
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
        st.error("密碼錯誤，請重新輸入。")

    st.divider()
    if st.button("🗑️ 清除目前對話紀錄", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 合併預設條款與網頁上傳條款
full_context = default_context + "\n" + st.session_state.uploaded_context

# 6. 空對話時的歡迎提示
if not st.session_state.messages:
    st.info("👋 您好！請在下方輸入想查詢的條款問題（例如：「承保範圍有哪些？」、「不保事項包含什麼？」）。系統將嚴格依據已載入的文件為您解答。")

# 顯示歷史對話
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🛡️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 7. 處理使用者提問
if prompt := st.chat_input("請輸入您想查詢的條款問題..."):
    if not full_context.strip():
        st.warning("目前知識庫是空的，請先由左側上傳條款文件。")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    system_instruction = f"""
你是一位極度嚴謹的企業條款查詢助理。
你「只能」根據下方【參考條款】的內容來回答使用者的問題。

【最高原則】
1. 嚴禁使用你的外部知識、常識或自行推測。
2. 如果【參考條款】中沒有明確提及答案，請直接回覆：「抱歉，目前提供的條款中查無相關資訊，請洽詢相關承辦人員。」絕對不要嘗試編造。
3. 回答時，請務必標註引用的「檔案名稱」或「頁碼 / 條文內容」，方便使用者核對。
4. 請使用繁體中文，語氣專業、條理分明，善用條列式呈現重點。

【參考條款】
{full_context}
"""

    contents = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))

    with st.chat_message("assistant", avatar="🛡️"):
        with st.spinner("正在檢索條款並生成回覆..."):
            try:
                # 若未來遇到 429 額度上限，可將模型改為 "gemini-3.5-flash-lite"
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
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
