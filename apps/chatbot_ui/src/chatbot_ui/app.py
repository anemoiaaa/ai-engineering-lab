import streamlit as st
from chatbot_ui.core.config import config
import requests


def api_call(method, url, **kwargs):
    try:
        response = getattr(requests, method)(url, timeout=60, **kwargs)
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            response_data = {"message": "Invalid response format from server"}
        if response.ok:
            return True, response_data
        return False, response_data
    except requests.exceptions.ConnectionError:
        return False, {"message": "Cannot connect to the API server. Please ensure the API is running."}
    except requests.exceptions.Timeout:
        return False, {"message": "The request timed out. The model may be processing a large request. Please try again."}
    except Exception as e:
        return False, {"message": f"An unexpected error occurred: {str(e)}"}


# --- Page Config ---
st.set_page_config(
    page_title="Northstar Foods Policy Copilot",
    page_icon="📋",
    layout="wide",
)

# --- Sidebar ---
with st.sidebar:
    st.title("Northstar Foods Policy Copilot")
    st.caption("Your AI assistant for internal policies, onboarding, and HR questions.")

    st.divider()

    # Mode selector
    mode = st.radio(
        "Mode",
        ["Policy Q&A", "Summarize Policy", "Onboarding Checklist", "Data Analysis"],
        help="Choose how you want to interact with company policies.",
    )
    mode_map = {
        "Policy Q&A": "chat",
        "Summarize Policy": "summarize",
        "Onboarding Checklist": "checklist",
        "Data Analysis": "analyze",
    }
    current_mode = mode_map[mode]

    st.divider()

    # Provider / model selector
    provider = st.selectbox("AI Provider", ["OpenAI", "Groq", "Google"])

    if provider == "OpenAI":
        model_name = st.selectbox("Model", ["gpt-4o-mini", "gpt-5-mini"])
    elif provider == "Groq":
        model_name = st.selectbox("Model", ["llama-3.3-70b-versatile"])
    else:
        model_name = st.selectbox("Model", ["gemini-2.5-flash"])

    st.session_state.provider = provider
    st.session_state.model = model_name

    st.divider()

    # Health check / policy info
    if st.button("Check System Status"):
        ok, data = api_call("get", f"{config.API_URL}/health")
        if ok:
            st.success(f"API Online — {data['policies_loaded']} policies loaded")
            with st.expander("Loaded Policies"):
                for title in data.get("policy_titles", []):
                    st.write(f"- {title}")
        else:
            st.error("API is not available. Please check that the API server is running.")

    # File upload for Data Analysis mode
    if current_mode == "analyze":
        st.divider()
        st.subheader("Upload a File")
        uploaded_file = st.file_uploader(
            "Choose a file to analyze",
            type=["csv", "json", "xlsx", "xls", "docx", "db"],
            help="Supported formats: CSV, JSON, Excel (.xlsx), Word (.docx), SQLite (.db)",
        )
    else:
        uploaded_file = None

    if st.button("Clear Chat"):
        st.session_state.messages = []
        if "uploaded_file_name" in st.session_state:
            del st.session_state.uploaded_file_name
        st.rerun()


# --- Mode-specific headers and placeholders ---

mode_config = {
    "chat": {
        "title": "Policy Q&A",
        "subtitle": "Ask questions about Northstar Foods policies. I'll find the relevant documents and give you accurate answers with sources.",
        "placeholder": "e.g., What is the remote work policy? How many PTO days do I get after 3 years?",
        "welcome": "Hello! I'm the Northstar Foods Policy Copilot. Ask me anything about company policies — remote work, leave, benefits, IT security, onboarding, and more. I'll provide answers based on official policy documents.",
    },
    "summarize": {
        "title": "Policy Summarizer",
        "subtitle": "Get a concise summary of any company policy.",
        "placeholder": "e.g., Summarize the expense reimbursement policy",
        "welcome": "I can summarize any Northstar Foods policy for you. Just tell me which policy you'd like summarized — for example: 'remote work policy', 'benefits overview', or 'IT security policy'.",
    },
    "checklist": {
        "title": "Onboarding Checklist Generator",
        "subtitle": "Generate a personalized onboarding checklist for new employees.",
        "placeholder": "e.g., Generate an onboarding checklist for a new software engineer",
        "welcome": "I can generate a personalized onboarding checklist based on Northstar Foods policies. Tell me the role or department, and I'll create a tailored checklist covering everything from pre-boarding to the first 90 days.",
    },
    "analyze": {
        "title": "Data Analysis",
        "subtitle": "Upload a file (CSV, JSON, Excel, Word) and ask questions about it.",
        "placeholder": "e.g., What are the key patterns in this data? Summarize the main findings.",
        "welcome": "Upload a file using the sidebar and I'll analyze it for you. I can read **CSV**, **JSON**, **Excel (.xlsx)**, **Word (.docx)**, and **SQLite (.db)** files. You can ask specific questions or I'll provide a comprehensive summary.",
    },
}

cfg = mode_config[current_mode]

st.title(cfg["title"])
st.caption(cfg["subtitle"])

# --- Chat History ---

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_mode" not in st.session_state:
    st.session_state.current_mode = current_mode

# Reset chat when mode changes
if st.session_state.current_mode != current_mode:
    st.session_state.messages = []
    st.session_state.current_mode = current_mode

# Show welcome message if chat is empty
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(cfg["welcome"])

# Display existing messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.write(f"- {source}")

# --- Chat Input ---

# Handle file upload in analyze mode
if current_mode == "analyze" and uploaded_file is not None:
    file_name = uploaded_file.name
    if st.session_state.get("uploaded_file_name") != file_name:
        st.session_state.uploaded_file_name = file_name
        st.session_state.uploaded_file_bytes = uploaded_file.getvalue()
        st.info(f"File loaded: **{file_name}** ({len(st.session_state.uploaded_file_bytes):,} bytes)")

if prompt := st.chat_input(cfg["placeholder"]):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Use /upload endpoint for analyze mode when a file is uploaded
        if current_mode == "analyze" and st.session_state.get("uploaded_file_bytes"):
            with st.spinner(f"Analyzing {st.session_state.uploaded_file_name}..."):
                import io
                ok, response_data = api_call(
                    "post",
                    f"{config.API_URL}/upload",
                    files={"file": (st.session_state.uploaded_file_name, io.BytesIO(st.session_state.uploaded_file_bytes))},
                    data={
                        "question": prompt,
                        "provider": st.session_state.provider,
                        "model_name": st.session_state.model,
                    },
                )
        else:
            with st.spinner("Searching policies and generating response..."):
                ok, response_data = api_call(
                    "post",
                    f"{config.API_URL}/chat",
                    json={
                        "provider": st.session_state.provider,
                        "model_name": st.session_state.model,
                        "messages": [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages
                        ],
                        "mode": current_mode,
                    },
                )

        if ok:
            answer = response_data["message"]
            sources = response_data.get("sources", [])
        else:
            answer = response_data.get("message", "An error occurred. Please try again.")
            sources = []

        st.markdown(answer)
        if sources:
            with st.expander("Sources"):
                for source in sources:
                    st.write(f"- {source}")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
    })
