
import json
import re

def safe_json_parse(text: str | None) -> dict:
    """
    Defensive JSON parser for LLM outputs.
    Returns {} if parsing fails.
    """
    if not text:
        return {}

    cleaned = text.strip()
    if not cleaned:
        return {}

    # Remove Markdown fences
    cleaned = re.sub(r"^```(json)?|```$", "", cleaned, flags=re.IGNORECASE).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting first JSON object from text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    return {}
