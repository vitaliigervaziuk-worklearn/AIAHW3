import time
import streamlit as st
from evaluation.evaluator import run_evaluation

if "metrics" not in st.session_state:
    st.session_state.metrics = []


from llm.llm_client import LLMClient
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

st.title("🌦️ Agentic Weather & News Assistant")

llm = LLMClient()
orchestrator = Orchestrator(llm=llm)

user_query = st.text_input(
    "Ask about weather or news (e.g. 'tech news in Germany')"
)

if user_query:
    t0 = time.perf_counter()
    response = orchestrator.handle(user_query)
    t1 = time.perf_counter()

    success_weather = "Unable to fetch weather" not in response
    success_news = "Unable to fetch news" not in response
    headline_count = response.count("https://news.google.com")

    st.session_state.metrics.append({
        "query": user_query,
        "latency_ms": (t1 - t0) * 1000,
        "weather_success": success_weather,
        "news_success": success_news,
        "headline_count": headline_count,
    })

    st.markdown(response)

    with st.expander("Metrics & Evaluation", expanded=True):
        data = st.session_state.metrics

        if not data:
            st.info("No metrics yet. Ask a question to generate data.")
        else:
            avg_latency = sum(d["latency_ms"] for d in data) / len(data)
            weather_success_rate = sum(d["weather_success"] for d in data) / len(data)
            news_success_rate = sum(d["news_success"] for d in data) / len(data)

            c1, c2, c3 = st.columns(3)
            c1.metric("Avg latency (ms)", f"{avg_latency:.1f}")
            c2.metric("Weather success rate", f"{weather_success_rate*100:.0f}%")
            c3.metric("News success rate", f"{news_success_rate*100:.0f}%")

            st.dataframe(data, use_container_width=True)

    with st.expander("Evaluation Suite (run_evaluation)", expanded=False):
        st.write("Runs a small evaluation dataset and computes success rates + latency.")

        if st.button("Run evaluation"):
            result = run_evaluation(orchestrator)
            metrics = result["metrics"]
            rows = result["rows"]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Weather success rate", f"{metrics['weather_success_rate']*100:.0f}%")
            c2.metric("News success rate", f"{metrics['news_success_rate']*100:.0f}%")
            c3.metric("Avg latency (ms)", f"{metrics['avg_latency_ms']:.1f}")
            c4.metric("Total cases", str(metrics["total_cases"]))

            st.dataframe(rows, use_container_width=True)