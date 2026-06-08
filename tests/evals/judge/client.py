"""LLM-as-Judge 客户端 — 使用 DeepSeek 模型进行主观质量评估。"""

from __future__ import annotations

import os

from tests.evals.judge.prompts import build_judge_prompt
from tests.evals.judge.scoring import JudgeResult, parse_judge_response


class LLMJudgeClient:
    """封装 LLM 作为 judge 的客户端。

    使用与 agent 相同的模型（从 .env 读取 OPENAI_API_KEY / BASE_URL / MODEL）。
    """

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", None)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        if not api_key:
            raise ValueError("OPENAI_API_KEY 未设置，无法使用 llm-as-judge")

        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def judge(
        self,
        rubric: str,
        context: str,
        response: str,
        criteria: list[str],
        max_retries: int = 2,
    ) -> JudgeResult:
        """使用 LLM judge 评估回复质量。

        Args:
            rubric: 评估标准描述
            context: 用户输入/上下文
            response: AI 助手的回复
            criteria: 评估维度列表
            max_retries: 解析失败时的重试次数

        Returns:
            JudgeResult 包含评分、推理和结论
        """
        prompt = build_judge_prompt(rubric, context, response, criteria)

        for attempt in range(max_retries + 1):
            try:
                result = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=1024,
                )
                raw_response = result.choices[0].message.content or ""
                judge_result = parse_judge_response(raw_response)

                if not judge_result.parse_error:
                    return judge_result

                if attempt < max_retries:
                    continue
                return judge_result

            except Exception as e:
                if attempt < max_retries:
                    continue
                return JudgeResult.failed(f"Judge API call failed: {e}")

        return JudgeResult.failed("Max retries exceeded")
