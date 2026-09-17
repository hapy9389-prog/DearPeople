import os

import anthropic
from dotenv import load_dotenv

load_dotenv()


def call_claude(system_prompt: str, messages: list[dict], model: str, max_tokens: int = 1024) -> str:
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
