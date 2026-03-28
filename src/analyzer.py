"""LangChain + Gemini AI analysis for JTVO."""

from __future__ import annotations

import os
import time

import pandas as pd
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()


# ── Pydantic schemas ────────────────────────────────────────────

class IssueAnalysis(BaseModel):
    complexity_reasoning: str = Field(
        description="Why this score — what evidence from description/comments"
    )
    instruction_clarity_score: float = Field(
        ge=0, le=1,
        description="How clear were the instructions/requirements (0=vague, 1=crystal clear)"
    )
    instruction_clarity_notes: str = Field(
        description="Notes on what made instructions clear or unclear"
    )


class WeeklyFeedback(BaseModel):
    feedback: str = Field(
        description="Brutally honest weekly feedback in Japanese, sarcastic tone"
    )
    mvp: str = Field(
        description="Most valuable performer this sprint"
    )


# ── Prompts ─────────────────────────────────────────────────────

ISSUE_ANALYSIS_PROMPT = """\
あなたはアジャイルコーチ兼テクニカルリードです。以下のJiraチケットを分析してください。

## チケット情報
- Key: {key}
- Summary: {summary}
- Reported SP: {reported_sp}
- Status: {status}
- Assignee: {assignee}
- Description:
{description}

## コメント
{comments}

## 分析基準
1. **complexity_reasoning**: チケットの技術的複雑度・作業範囲の分析根拠。
2. **instruction_clarity_score**: チケットの指示の明確度(0〜1)。
   - コメント欄で「これどういう意味？」等の質問が多い→低スコア
   - 明確なACと具体的手順がある→高スコア
3. **instruction_clarity_notes**: 指示の問題点や良い点。

正直に、忖度なしで判定してください。
"""

WEEKLY_FEEDBACK_PROMPT = """\
あなたは毒舌だが的確なアジャイルコーチです。
以下のスプリントデータを見て、マネージャー（中津川）への週次フィードバックを生成してください。

## スプリントデータ
{sprint_data}

## 個人別スコア
{leaderboard}

## ルール
- feedback: 日本語で、皮肉を効かせつつも建設的な改善提案を含める。
  中津川が指示を出している立場なので、指示の不明確さにも言及すること。
- mvp: 最も実質的に貢献した人物名（SP合計が最大の人）。

容赦なく、しかし愛を持って。
"""


# ── Analyzer class ──────────────────────────────────────────────

class Analyzer:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.3,
        )

    def analyze_issue(
        self, key: str, summary: str, reported_sp: float,
        status: str, assignee: str, description: str, comments: str,
    ) -> IssueAnalysis:
        """Analyze a single issue with structured output."""
        structured_llm = self.llm.with_structured_output(IssueAnalysis)
        prompt = ISSUE_ANALYSIS_PROMPT.format(
            key=key, summary=summary, reported_sp=reported_sp,
            status=status, assignee=assignee or "Unassigned",
            description=description or "(no description)",
            comments=comments or "(no comments)",
        )
        return structured_llm.invoke(prompt)

    def analyze_sprint_issues(
        self, issues_df: pd.DataFrame, comments_df: pd.DataFrame,
        progress_callback=None,
    ) -> pd.DataFrame:
        """Batch-analyze all issues in a sprint.

        Returns DataFrame matching ai_scores table schema.
        """
        results = []
        total = len(issues_df)

        for idx, row in issues_df.iterrows():
            issue_key = row["key"]

            # Gather comments for this issue
            issue_comments = comments_df[
                comments_df["issue_key"] == issue_key
            ] if not comments_df.empty else pd.DataFrame()

            comments_text = "\n".join(
                f"- {c['author']}: {c['body']}"
                for _, c in issue_comments.iterrows()
            ) if not issue_comments.empty else ""

            try:
                analysis = self.analyze_issue(
                    key=issue_key,
                    summary=row.get("summary", ""),
                    reported_sp=row.get("reported_sp", 0),
                    status=row.get("status", ""),
                    assignee=row.get("assignee", ""),
                    description=row.get("description", ""),
                    comments=comments_text,
                )
                results.append({
                    "issue_key": issue_key,
                    "complexity_reasoning": analysis.complexity_reasoning,
                    "clarity_score": analysis.instruction_clarity_score,
                    "clarity_notes": analysis.instruction_clarity_notes,
                    "analyzed_at": pd.Timestamp.now(),
                })
            except Exception as e:
                results.append({
                    "issue_key": issue_key,
                    "complexity_reasoning": f"Analysis failed: {e}",
                    "clarity_score": None,
                    "clarity_notes": None,
                    "analyzed_at": pd.Timestamp.now(),
                })

            if progress_callback:
                progress_callback(idx + 1, total)

            # Rate limit: 4s between API calls
            if idx < total - 1:
                time.sleep(4)

        return pd.DataFrame(results)

    def generate_weekly_feedback(
        self, sprint_summary: str, leaderboard_text: str,
    ) -> WeeklyFeedback:
        """Generate sarcastic weekly feedback for the manager."""
        structured_llm = self.llm.with_structured_output(WeeklyFeedback)
        prompt = WEEKLY_FEEDBACK_PROMPT.format(
            sprint_data=sprint_summary,
            leaderboard=leaderboard_text,
        )
        return structured_llm.invoke(prompt)
