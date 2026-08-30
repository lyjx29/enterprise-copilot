"""FinCopilot 简单前端（Streamlit）：对话 + 来源面板。

用法：
    streamlit run ui/app.py
或 docker compose --profile ui up
"""

from __future__ import annotations

import json
import os

import requests
import streamlit as st

st.set_page_config(page_title="FinCopilot", page_icon="📊", layout="wide")

# 容器内默认走 docker 服务名 api:8000；本地跑 streamlit 时用 localhost
DEFAULT_API = os.environ.get("API_URL", "http://localhost:8000")
API_URL = st.sidebar.text_input("API URL", DEFAULT_API)
API_KEY = st.sidebar.text_input("API Key", type="password")
st.sidebar.caption("留空 = 本地开发（未开启鉴权）")

headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

st.title("📊 FinCopilot · 多源自适应财务分析师")
st.caption("问财报 / 员工库 / 实时信息问题，自动路由到 RAG / SQL / Web")

# 会话状态
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "sources" not in st.session_state:
    st.session_state.sources = []

# 来源面板（右侧）
left, right = st.columns([3, 1], gap="large")
with right:
    st.subheader("📚 来源")
    if st.session_state.sources:
        for src in st.session_state.sources:
            st.markdown(
                f"**{src.get('company', '?')}** {src.get('doc_type', '')} "
                f"{src.get('year', '')} p.{src.get('page', '?')}"
            )
    else:
        st.caption("（暂无来源）")
    if st.button("🔄 新会话"):
        st.session_state.thread_id = None
        st.session_state.sources = []
        st.rerun()

with left:
    question = st.chat_input("例如：What was Amazon's revenue in 2023?")

    if question:
        # 创建线程（首次）
        if not st.session_state.thread_id:
            try:
                r = requests.post(f"{API_URL}/v1/threads", headers=headers, timeout=10)
                st.session_state.thread_id = r.json()["thread_id"]
            except requests.RequestException as exc:
                st.error(f"无法连接 API: {exc}")
                st.stop()

        st.chat_message("user").write(question)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            answer = ""
            try:
                resp = requests.post(
                    f"{API_URL}/v1/chat",
                    headers=headers,
                    json={
                        "question": question,
                        "thread_id": st.session_state.thread_id,
                    },
                    stream=True,
                    timeout=180,
                )
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and data.get("content"):
                        answer += data["content"]
                        placeholder.markdown(answer + "▌")
                    elif isinstance(data, dict) and data.get("sources"):
                        st.session_state.sources = data["sources"]
                placeholder.markdown(answer)
            except requests.RequestException as exc:
                placeholder.error(f"请求失败: {exc}")
