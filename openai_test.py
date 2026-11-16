from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path


load_dotenv(Path(__file__).resolve().parent / ".env")
client = OpenAI()
prompt = "너는 금융기관 위치를 조사하는 도우미야. 공식 홈페이지를 **반드시** 우선 확인하고, 한국어로 답변해. 공식 홈페이지가 아닐 경우, 출처를 **반드시** 출력해. 답변은 오직 주소만 나오게 출력해야해. 확인하지 못한 정보는 **절대로** 추측해선 안 돼."

# web search 기능 필요
response = client.responses.create(
    model = "gpt-6-luna",
    instructions = prompt,
    tools = [{"type": "web_search",
              "filters":{
                "blocked_domains":[
                    "kbank.org"
                ]
              }}],
    input = "골드만삭스 한국지점"
)

print(response.output_text)

# 사용토큰 출력
usage = response.usage
if usage is not None:
    print(f"입력토큰: {usage.input_tokens:,}")
    print(f"출력 토큰: {usage.output_tokens:,}")