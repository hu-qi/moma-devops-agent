"""Direct Q&A response handler for read-only inquiry issues without creating branches or PRs."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from devopspilot.contracts.branding import BrandConfig
from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.providers import (
    CommentSubjectKind,
    CommentSubjectRef,
    SCMProvider,
)
from devopspilot.utils.model_text import strip_think_tags


class InquiryHandler:
    """Handles read-only inquiry issues by inspecting repository context and commenting directly."""

    def __init__(self, scm: SCMProvider) -> None:
        self._scm = scm

    async def answer_and_comment(
        self,
        task: DeliveryTask,
        workspace_path: Path | None = None,
        *,
        model: str | None = None,
    ) -> str:
        # 1. Collect repository context
        existing_files: list[str] = []
        readme_snippet: str = ""

        if workspace_path and workspace_path.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "ls-files",
                    cwd=str(workspace_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                existing_files = [f.strip() for f in stdout.decode("utf-8").splitlines() if f.strip()]
            except Exception:
                try:
                    existing_files = [
                        str(p.relative_to(workspace_path))
                        for p in workspace_path.glob("**/*")
                        if p.is_file() and not any(part.startswith(".") for part in p.parts)
                    ][:50]
                except Exception:
                    pass

            readme_file = workspace_path / "README.md"
            if readme_file.exists():
                try:
                    readme_snippet = readme_file.read_text(encoding="utf-8")[:2000]
                except Exception:
                    pass

        # 2. Call MoMA Model to compose a professional Markdown answer
        answer = await self._generate_answer(
            task=task,
            files=existing_files,
            readme_snippet=readme_snippet,
            model=model,
        )

        # 3. Post comment to SCM issue with idempotency (C09):
        # a delivery may be resumed after a crash between comment-post and
        # state-save; without a marker we would duplicate the answer.
        comment_body = answer
        delivery_id = task.metadata.get("delivery_id", "")
        if delivery_id:
            marker = f"<!-- devopspilot:inquiry-answer:{delivery_id} -->"
            if await self._already_commented(task, marker):
                print("[Inquiry] Answer for this delivery already posted; skipping duplicate comment.")
                return answer
            comment_body = f"{answer}\n\n{marker}"

        await self._scm.add_comment(
            CommentSubjectRef(
                repository=task.repository,
                subject_id=task.work_item.item_id,
                kind=CommentSubjectKind.WORK_ITEM,
            ),
            body=comment_body,
        )
        return answer

    async def _already_commented(self, task: DeliveryTask, marker: str) -> bool:
        """Check prior comments for this delivery's idempotency marker."""
        try:
            comments = await self._scm.list_comments(
                CommentSubjectRef(
                    repository=task.repository,
                    subject_id=task.work_item.item_id,
                    kind=CommentSubjectKind.WORK_ITEM,
                ),
            )
        except Exception:
            return False  # cannot verify; posting is the safer failure for Q&A
        for c in comments or ():
            body = getattr(c, "body", None) or (c.get("body") if isinstance(c, dict) else "")
            if body and marker in body:
                return True
        return False

    async def _generate_answer(
        self,
        task: DeliveryTask,
        files: list[str],
        readme_snippet: str,
        model: str | None = None,
    ) -> str:
        from devopspilot.adapters.moma.client import MoMAClient

        api_key = os.environ.get("MOMA_API_KEY", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        api_base = os.environ.get("MOMA_API_BASE", "https://zhenze-huhehaote.cmecloud.cn/v1").strip()
        selected_model = (
            model
            or os.environ.get("MOMA_MODEL")
            or os.environ.get("MOMA_CODING_MODEL")
            or "deepseek-v4.1-flash"
        )

        client = MoMAClient(api_key=api_key, api_base=api_base, default_model=selected_model)

        sys_prompt = (
            "You are DevOpsPilot, an autonomous AI DevOps and Software Engineering Agent operating on China Mobile Cloud (MoMA) platform.\n"
            "The user opened an inquiry/question issue. Your task is to provide an accurate, clear, and well-structured answer.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output your answer directly in standard Markdown format.\n"
            "2. Do NOT output any <think> tags or reasoning thoughts.\n"
            "3. Do NOT wrap your answer in JSON or markdown JSON fences.\n"
            "4. Respond in the same language as the user's issue (Chinese if Chinese, English if English)."
        )

        user_prompt = (
            f"Repository: {task.repository.full_name}\n"
            f"Issue #{task.work_item.item_id}: {task.work_item.title}\n\n"
            f"Issue Content:\n{task.work_item.body}\n\n"
            f"Current repository files ({len(files)} file(s)):\n"
            + ("\n".join(f"- {f}" for f in files) if files else "(empty repository)")
            + (f"\n\nExisting README snippet:\n```markdown\n{readme_snippet}\n```" if readme_snippet else "")
            + "\n\nPlease provide a clear, professional answer to resolve the inquiry."
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        resp = await asyncio.to_thread(client.chat_completion, messages, model=selected_model)
        content = resp["choices"][0]["message"]["content"].strip()
        cleaned_answer = strip_think_tags(content)

        # Append official signature footer from BrandConfig (configurable, no hardcoding)
        brand = BrandConfig.from_env()
        return cleaned_answer + brand.format_issue_footer()
