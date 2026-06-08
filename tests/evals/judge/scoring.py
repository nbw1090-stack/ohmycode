"""Judge 评分处理 — 解析 LLM judge 的结构化输出。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class JudgeResult:
    """LLM Judge 的评估结果。"""

    scores: dict[str, float] = field(default_factory=dict)
    reasoning: dict[str, str] = field(default_factory=dict)
    overall_score: float = 0.0
    verdict: str = "FAIL"
    parse_error: str = ""

    @property
    def passed(self) -> bool:
        """判定是否通过。"""
        if self.parse_error:
            return False
        return self.verdict.upper() == "PASS" and self.overall_score >= 3.5

    @staticmethod
    def failed(reason: str) -> JudgeResult:
        """创建一个解析失败的 JudgeResult。"""
        return JudgeResult(parse_error=reason, verdict="FAIL")


def parse_judge_response(text: str) -> JudgeResult:
    """解析 judge LLM 的结构化输出。

    期望格式：
        ## 评分
        - 工具选择准确性: 4/5 - 选择了正确的工具...
        - 参数合理性: 3/5 - ...
        Overall: 3.5
        Verdict: PASS

    使用正则提取，解析失败不抛异常，而是返回 parse_error。
    """
    if not text or not text.strip():
        return JudgeResult.failed("Empty judge response")

    result = JudgeResult()

    # 提取单项评分: "criterion: N/5 - reasoning" 或 "criterion: N - reasoning"
    score_pattern = re.compile(
        r"[-*]\s*(.+?):\s*(\d+(?:\.\d+)?)\s*(?:/\s*5)?\s*[-—:]\s*(.*?)(?:\n|$)",
        re.MULTILINE,
    )

    for match in score_pattern.finditer(text):
        criterion = match.group(1).strip()
        score = float(match.group(2))
        reasoning = match.group(3).strip()

        # 标准化 criterion 名称
        criterion_clean = criterion.rstrip(":")
        result.scores[criterion_clean] = min(5.0, max(1.0, score))
        if reasoning:
            result.reasoning[criterion_clean] = reasoning

    # 提取 Overall score
    overall_pattern = re.compile(r"overall\s*[:：]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
    overall_match = overall_pattern.search(text)
    if overall_match:
        result.overall_score = float(overall_match.group(1))

    # 提取 Verdict
    verdict_pattern = re.compile(r"verdict\s*[:：]?\s*(PASS|FAIL)", re.IGNORECASE)
    verdict_match = verdict_pattern.search(text)
    if verdict_match:
        result.verdict = verdict_match.group(1).upper()

    # 计算平均分（如果没有明确的 overall score）
    if not result.overall_score and result.scores:
        result.overall_score = sum(result.scores.values()) / len(result.scores)

    # 如果没有提取到任何评分，标记解析错误
    if not result.scores and result.overall_score == 0:
        return JudgeResult.failed(f"Could not parse scores from response: {text[:200]}")

    return result
