import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()


def call_claude(system_prompt: str, messages: list, model: str, max_tokens: int = 1024) -> str:
    """Claude 호출을 모으는 단일 함수. model은 호출자가 CHAT_MODEL/FAST_MODEL 중 선택해서 넘긴다."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _extract_json_str(text: str) -> str:
    text = text.strip()
    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    ends = [i for i in (text.rfind("]"), text.rfind("}")) if i != -1]
    if not starts or not ends:
        return text
    return text[min(starts):max(ends) + 1]


def call_claude_json(system_prompt: str, messages: list, model: str, max_tokens: int = 1024):
    """call_claude 호출 후 JSON 파싱. 실패 시 1회 재시도, 그래도 실패하면 예외."""
    raw = call_claude(system_prompt, messages, model, max_tokens)
    try:
        return json.loads(_extract_json_str(raw))
    except json.JSONDecodeError:
        raw2 = call_claude(system_prompt, messages, model, max_tokens)
        try:
            return json.loads(_extract_json_str(raw2))
        except json.JSONDecodeError as e:
            raise RuntimeError("AI 응답을 JSON으로 파싱하지 못했습니다.") from e
