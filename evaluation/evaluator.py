from __future__ import annotations
import time
from typing import Dict, Any, List


# Small evaluation dataset
EVAL_DATASET: List[Dict[str, Any]] = [
    {"prompt": "Tell me a joke", "expected_weather": False, "expected_news": False},
    {"prompt": "Give me the weather in Paris", "expected_weather": True, "expected_news": False},
    {"prompt": "Give me headlines about medical", "expected_weather": False, "expected_news": True},
    {"prompt": "Give me weather and headlines for Paris, France", "expected_weather": True, "expected_news": True},
    {"prompt": "medical headlines for Philadelphia", "expected_weather": False, "expected_news": True},
]

def _headline_count_from_response(response: str) -> int:
    """
    Heuristic headline counter from rendered output text.
    Counts bullet/numbered list items.
    """
    if not response:
        return 0

    count = 0
    for line in response.splitlines():
        s = line.strip()
        if s.startswith(("-", "•", "*")):
            count += 1
        elif s[:2].isdigit() and s[2:3] == ".":
            count += 1
        elif s[:3].isdigit() and s[3:4] == ".":
            count += 1
    return count


def run_evaluation(orchestrator) -> Dict[str, Any]:
    """
    Runs the evaluation dataset through orchestrator.handle() and computes:
      - weather_success_rate
      - news_success_rate
      - avg_latency_ms
      - (optional) intent-like classification from output (simple)
    """
    rows = []
    total = len(EVAL_DATASET)

    weather_expected = 0
    weather_ok = 0

    news_expected = 0
    news_ok = 0

    total_latency_ms = 0.0

    for item in EVAL_DATASET:
        prompt = item["prompt"]
        expect_weather = item["expected_weather"]
        expect_news = item["expected_news"]

        t0     = time.perf_counter()
        result = orchestrator.handle(prompt)
        t1     = time.perf_counter()

        latency_ms = (t1 - t0) * 1000.0
        total_latency_ms += latency_ms

        response     = result["reply"]
        tools_called = result["tools_called"]

        # check success by actual tool calls, not text heuristics
        weather_success = (
            any(t in tools_called for t in ("get_weather", "get_forecast"))
        ) if expect_weather else None
        news_success = ("get_news" in tools_called) if expect_news else None

        # Count headlines from the response
        headlines = _headline_count_from_response(response) if expect_news else 0

        # Aggregate metrics
        if expect_weather:
            weather_expected += 1
            if weather_success:
                weather_ok += 1

        if expect_news:
            news_expected += 1
            # consider success true only if no error AND some items present
            if news_success and headlines > 0:
                news_ok += 1

        rows.append({
            "prompt": prompt,
            "expect_weather": expect_weather,
            "expect_news": expect_news,
            "latency_ms": round(latency_ms, 1),
            "weather_success": weather_success,
            "news_success": news_success,
            "headline_count": headlines,
        })

    weather_success_rate = (weather_ok / weather_expected) if weather_expected else 0.0
    news_success_rate = (news_ok / news_expected) if news_expected else 0.0
    avg_latency_ms = (total_latency_ms / total) if total else 0.0

    return {
        "rows": rows,
        "metrics": {
            "weather_success_rate": weather_success_rate,
            "news_success_rate": news_success_rate,
            "avg_latency_ms": avg_latency_ms,
            "total_cases": total,
        }
    }
