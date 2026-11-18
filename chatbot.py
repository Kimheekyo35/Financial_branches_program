from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def openai_chatbot(messages):
    """사용자가 입력한 대화 내역을 바탕으로 답변한다."""
    load_dotenv(Path(__file__).resolve().parent / ".env")

    prompy = 
    with OpenAI(timeout=60.0) as client:
        response = client.responses.create(
            model="gpt-6-luna",
            tool = [{"type": "web_search"}],
            instructions=(
                "너는 금융거래조회서 주소 검증 프로그램의 한국어 도우미다. "
                "질문에 대해 **정확하게** 답변해야 하며, 새로운 정보를 만들어 내서는 안 된다."
                "반드시 질문에 대한 출처를 남겨야 한다."
            ),
            input=messages,
        )
    if not response.output_text.strip():
        raise ValueError("챗봇 응답이 비어 있습니다.")
    return response.output_text
