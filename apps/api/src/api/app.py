from fastapi import FastAPI, File, UploadFile, Form
from pydantic import BaseModel

from openai import OpenAI
from groq import Groq
from google import genai

from api.core.config import config
from api.prompts.system_prompts import (
    POLICY_COPILOT_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
    CHECKLIST_SYSTEM_PROMPT,
    DATA_ANALYSIS_SYSTEM_PROMPT,
)
from api.retrieval.policy_store import PolicyStore
from api.retrieval.file_parser import parse_file, SUPPORTED_EXTENSIONS

import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- LLM Clients (initialized once) ---

openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
groq_client = Groq(api_key=config.GROQ_API_KEY)
google_client = genai.Client(api_key=config.GOOGLE_API_KEY)

# --- Policy Store (loaded once at startup) ---

policy_store = PolicyStore(policies_dir=config.POLICIES_DIR)


def run_llm(provider: str, model_name: str, messages: list[dict], max_tokens: int = 1024) -> str:
    try:
        if provider == "Google":
            system_msg = None
            user_contents = []
            for message in messages:
                if message["role"] == "system":
                    system_msg = message["content"]
                else:
                    user_contents.append(message["content"])
            kwargs = {"model": model_name, "contents": user_contents}
            if system_msg:
                kwargs["config"] = {"system_instruction": system_msg}
            return google_client.models.generate_content(**kwargs).text
        elif provider == "Groq":
            return groq_client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_completion_tokens=max_tokens,
            ).choices[0].message.content
        else:
            return openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_completion_tokens=max_tokens,
            ).choices[0].message.content
    except Exception as e:
        logger.error(f"LLM call failed ({provider}/{model_name}): {e}")
        raise


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    provider: str
    model_name: str
    messages: list[dict]
    mode: str = "chat"  # "chat", "summarize", "checklist"

class ChatResponse(BaseModel):
    message: str
    sources: list[str] = []
    mode: str = "chat"

class HealthResponse(BaseModel):
    status: str
    policies_loaded: int
    policy_titles: list[str]


# --- App ---

app = FastAPI(
    title="Northstar Foods Policy Copilot API",
    description="Internal AI assistant for company policies, onboarding, and HR questions.",
    version="0.1.0",
)


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        policies_loaded=len(policy_store.documents),
        policy_titles=policy_store.get_all_titles(),
    )


@app.post("/chat")
def chat(payload: ChatRequest) -> ChatResponse:
    user_messages = payload.messages

    if not user_messages:
        return ChatResponse(message="Please provide a message.", sources=[], mode=payload.mode)

    last_user_message = ""
    for msg in reversed(user_messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break

    if payload.mode == "summarize":
        return _handle_summarize(payload, last_user_message)
    elif payload.mode == "checklist":
        return _handle_checklist(payload, last_user_message)
    else:
        return _handle_policy_chat(payload, user_messages, last_user_message)


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    question: str = Form(""),
    provider: str = Form("OpenAI"),
    model_name: str = Form("gpt-4o-mini"),
) -> ChatResponse:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        return ChatResponse(
            message=f"Unsupported file type: {ext}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}",
            sources=[],
            mode="analyze",
        )

    content = await file.read()
    try:
        file_text = parse_file(file.filename, content)
    except Exception as e:
        return ChatResponse(
            message=f"Error reading file: {e}",
            sources=[],
            mode="analyze",
        )

    payload = ChatRequest(
        provider=provider,
        model_name=model_name,
        messages=[{"role": "user", "content": question}],
        mode="analyze",
    )
    return _handle_analyze(payload, question, file_text)


def _handle_policy_chat(payload: ChatRequest, user_messages: list[dict], query: str) -> ChatResponse:
    retrieved = policy_store.search(query, top_k=3, min_score=0.08)

    if not retrieved:
        return ChatResponse(
            message="I don't have enough information in the current policy documents to answer that question. Please contact HR at hr@companyx.com for further assistance.",
            sources=[],
            mode="chat",
        )

    sources = [f"{doc['title']} ({doc['filename']})" for doc in retrieved]
    context = "\n\n---\n\n".join(
        f"### {doc['title']}\n{doc['content']}" for doc in retrieved
    )

    system_prompt = POLICY_COPILOT_SYSTEM_PROMPT.format(context=context)

    messages_for_llm = [{"role": "system", "content": system_prompt}]
    for msg in user_messages:
        if msg.get("role") in ("user", "assistant"):
            messages_for_llm.append(msg)

    try:
        result = run_llm(payload.provider, payload.model_name, messages_for_llm)
        return ChatResponse(message=result, sources=sources, mode="chat")
    except Exception as e:
        return ChatResponse(
            message=f"Sorry, I encountered an error processing your request. Please try again or contact IT support. (Error: {type(e).__name__})",
            sources=[],
            mode="chat",
        )


def _handle_summarize(payload: ChatRequest, query: str) -> ChatResponse:
    retrieved = policy_store.search(query, top_k=1, min_score=0.08)

    if not retrieved:
        return ChatResponse(
            message="I couldn't find a policy matching your request. Available policies: " + ", ".join(policy_store.get_all_titles()),
            sources=[],
            mode="summarize",
        )

    doc = retrieved[0]
    system_prompt = SUMMARIZE_SYSTEM_PROMPT.format(context=doc["content"])
    messages_for_llm = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please summarize the {doc['title']} policy."},
    ]

    try:
        result = run_llm(payload.provider, payload.model_name, messages_for_llm)
        return ChatResponse(
            message=result,
            sources=[f"{doc['title']} ({doc['filename']})"],
            mode="summarize",
        )
    except Exception as e:
        return ChatResponse(
            message=f"Error generating summary. Please try again. (Error: {type(e).__name__})",
            sources=[],
            mode="summarize",
        )


def _handle_analyze(payload: ChatRequest, query: str, file_content: str) -> ChatResponse:
    system_prompt = DATA_ANALYSIS_SYSTEM_PROMPT.format(context=file_content)
    messages_for_llm = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query if query else "Please analyze this file and summarize the key patterns and insights."},
    ]

    try:
        result = run_llm(payload.provider, payload.model_name, messages_for_llm, max_tokens=2048)
        return ChatResponse(message=result, sources=["Uploaded file"], mode="analyze")
    except Exception as e:
        return ChatResponse(
            message=f"Error analyzing file. Please try again. (Error: {type(e).__name__})",
            sources=[],
            mode="analyze",
        )


def _handle_checklist(payload: ChatRequest, query: str) -> ChatResponse:
    context = policy_store.get_all_documents_context()
    system_prompt = CHECKLIST_SYSTEM_PROMPT.format(context=context)
    messages_for_llm = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query if query else "Generate a complete onboarding checklist for a new employee."},
    ]

    try:
        result = run_llm(payload.provider, payload.model_name, messages_for_llm, max_tokens=2048)
        return ChatResponse(
            message=result,
            sources=[f"{doc['title']} ({doc['filename']})" for doc in policy_store.documents],
            mode="checklist",
        )
    except Exception as e:
        return ChatResponse(
            message=f"Error generating checklist. Please try again. (Error: {type(e).__name__})",
            sources=[],
            mode="checklist",
        )
