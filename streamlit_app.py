import time
import streamlit as st
from evaluation.evaluator import run_evaluation
from orchestrator import Orchestrator


def require_password():
    if st.session_state.get("authenticated", False):
        return True

    st.title("🔒 Protected App")
    password = st.text_input("Enter password", type="password")

    if password:
        if password == st.secrets["auth"]["password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password ❌")

    st.stop()


require_password()

st.title("Agentic Weather & News Assistant")
st.caption("Open-Meteo + Google News via MCP servers · Gemini function-calling agent")

# init session state on first run
if "messages" not in st.session_state:
    st.session_state.messages = []
if "metrics" not in st.session_state:
    st.session_state.metrics = []
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

orchestrator = st.session_state.orchestrator

# ── sidebar with live metrics ─────────────────────────────────────────────────

with st.sidebar:
    st.header("Session Metrics")
    data = st.session_state.metrics
    if data:
        avg_latency = sum(d["latency_ms"] for d in data) / len(data)
        weather_ok  = sum(d["weather_success"] for d in data) / len(data)
        news_ok     = sum(d["news_success"] for d in data) / len(data)
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg latency (ms)", f"{avg_latency:.0f}")
        c2.metric("Weather success", f"{weather_ok * 100:.0f}%")
        c3.metric("News success",    f"{news_ok * 100:.0f}%")
        st.dataframe(data, use_container_width=True)
    else:
        st.info("Ask something to see live metrics.")

    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.metrics  = []
        st.rerun()

    st.divider()
    with st.expander("Evaluation Suite (run_evaluation)", expanded=False):
        st.write("Runs a small evaluation dataset and computes success rates + latency.")
        if st.button("Run evaluation"):
            result  = run_evaluation(orchestrator)
            metrics = result["metrics"]
            rows    = result["rows"]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Weather success rate", f"{metrics['weather_success_rate'] * 100:.0f}%")
            c2.metric("News success rate",    f"{metrics['news_success_rate'] * 100:.0f}%")
            c3.metric("Avg latency (ms)",     f"{metrics['avg_latency_ms']:.1f}")
            c4.metric("Total cases",          str(metrics["total_cases"]))
            st.dataframe(rows, use_container_width=True)

# ── chat history ──────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── chat input ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask about weather or news (e.g. 'tech news in Philadelphia')"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Thinking...."):
            t0     = time.perf_counter()
            result = orchestrator.handle(
                prompt,
                history=st.session_state.messages[:-1],
            )
            latency_ms = (time.perf_counter() - t0) * 1000
        reply        = result["reply"]
        tools_called = result["tools_called"]
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

    st.session_state.metrics.append({
        "query":           prompt,
        "latency_ms":      round(latency_ms),
        # use actual tool calls, not text heuristics
        "weather_success": any(t in tools_called for t in ("get_weather", "get_forecast")),
        "news_success":    "get_news" in tools_called,
    })
    # rerun so sidebar metrics refresh immediately
    st.rerun()
