from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def openai_chatbot(messages):
    
    prompt = """
    너는 금융거래조회서 주소 검증 프로그램의 한국어 도우미다.
    질문에 대해 **정확하게** 답변해야 하며, 새로운 정보를 만들어 내서는 안 된다.
    반드시 질문에 대한 출처를 남겨야 한다.
    질문이 명확하지 않을 경우, 재질문을 통하여 정확한 정보를 얻는다.
    """
        
    load_dotenv(Path(__file__).resolve().parent / ".env")

    with OpenAI(timeout=60.0) as client:
        response = client.responses.create(
            model="gpt-6-luna",
            tools=[{"type": "web_search"}],
            instructions=prompt,
            input=messages,
        )

    if not response.output_text.strip():
        raise ValueError("챗봇 응답이 비어 있습니다.")
    
    return response.output_text
