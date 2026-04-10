#!/usr/bin/env python3
"""
Deterministic wrapper around CodeRabbit CLI for the code-review skill.

The `review` subcommand writes artifacts and emits a small JSON summary to
stdout. Diagnostics and progress go to stderr.

The `render` subcommand reads the normalized JSON artifact and prints the final
Markdown report to stdout.
"""

from __future__ import annotations

import argparse
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class ReviewError(RuntimeError):
    pass


class ReviewProcessError(ReviewError):
    def __init__(self, message: str, *, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


def run(
    args: list[str],
    *,
    cwd: str | None = None,
    timeout: int | None = None,
    check: bool = True,
) -> CommandResult:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    result = CommandResult(proc.returncode, proc.stdout, proc.stderr)
    if check and proc.returncode != 0:
        raise ReviewError(
            f"command failed ({proc.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def emit_error(code: str, message: str, **extra: Any) -> None:
    payload = {"status": "error", "code": code, "message": message}
    payload.update(extra)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def derive_title(comment: str | None, path: str | None, classification: str | None, proposed_fix: str | None = None) -> str:
    if comment:
        first_line = comment.splitlines()[0].strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", first_line)[0].strip()
        if first_sentence:
            return first_sentence[:120]
    if proposed_fix:
        first_line = proposed_fix.splitlines()[0].strip()
        if first_line:
            return first_line[:120]
    parts = [part for part in (classification, path) if part]
    return " / ".join(parts) if parts else "Finding"


def derive_impact(comment: str | None, proposed_fix: str | None) -> str | None:
    source = comment or proposed_fix
    if not source:
        return None
    first_line = source.splitlines()[0].strip()
    if not first_line:
        return None
    return f"CodeRabbit flagged: {first_line[:160].rstrip('.')}."


def summarize(findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not findings:
        return {
            "overall_verdict": "No Findings Reported",
            "findings_count": 0,
        }

    return {
        "overall_verdict": "Findings Reported",
        "findings_count": len(findings),
    }


def summarize_plain_review(text: str) -> dict[str, Any]:
    if text.strip():
        return {
            "overall_verdict": "Review Completed",
            "findings_count": None,
        }
    return {
        "overall_verdict": "No Review Output",
        "findings_count": 0,
    }


def parse_line_range(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    stripped = text.strip()
    match = re.fullmatch(r"(\d+)\s+to\s+(\d+)", stripped)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.fullmatch(r"(\d+)", stripped)
    if match:
        value = int(match.group(1))
        return value, value
    return None, None


def is_fix_heading(line: str) -> bool:
    normalized = line.strip().lower()
    if not normalized:
        return False
    return (
        "suggested fix" in normalized
        or "proposed fix" in normalized
        or "suggested formatting improvement" in normalized
        or "suggested refactor direction" in normalized
    )


def fence_language_for_path(path: str | None) -> str:
    if not path:
        return "text"
    suffix = Path(path).suffix.lower()
    return {
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".py": "python",
        ".rb": "ruby",
        ".go": "go",
        ".rs": "rust",
        ".php": "php",
        ".c": "c",
        ".h": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".cs": "csharp",
        ".m": "objective-c",
        ".mm": "objective-cpp",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".json": "json",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".sql": "sql",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".md": "markdown",
        ".diff": "diff",
        ".patch": "diff",
        ".xib": "xml",
        ".storyboard": "xml",
    }.get(suffix, "text")


def parse_plain_text_review(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not text.strip():
        return findings

    blocks = re.split(r"\n={20,}\n", text)
    for block in blocks:
        block = block.strip()
        if not block.startswith("File: "):
            continue

        file_match = re.search(r"^File:\s*(.+)$", block, re.MULTILINE)
        type_match = re.search(r"^Type:\s*(.+)$", block, re.MULTILINE)
        line_match = re.search(r"^Line:\s*(.+)$", block, re.MULTILINE)
        path = file_match.group(1).strip() if file_match else None
        classification = type_match.group(
            1).strip() if type_match else "unknown"
        start_line, end_line = parse_line_range(
            line_match.group(1) if line_match else None)

        comment = None
        proposed_fix = None
        lines = block.splitlines()
        if "Comment:" in lines:
            comment_start = lines.index("Comment:") + 1
            comment_lines: list[str] = []
            fix_lines: list[str] = []
            in_fix = False
            for line in lines[comment_start:]:
                if not in_fix and is_fix_heading(line):
                    in_fix = True
                    continue
                if in_fix:
                    fix_lines.append(line)
                else:
                    comment_lines.append(line)
            comment = "\n".join(comment_lines).strip() or None
            proposed_fix = "\n".join(fix_lines).strip() or None

        if not path and not comment:
            continue

        findings.append(
            {
                "title": derive_title(comment, path, classification, proposed_fix),
                "classification": classification or "unknown",
                "event_type": "finding",
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
                "comment": comment,
                "codegen_instructions": None,
                "impact": None,
                "suggested_refactor": None,
                "proposed_fix": proposed_fix,
                "raw": {"plain_text_block": block},
            }
        )

    return findings


def build_report(
    *,
    plain_text: str,
    repo: str,
    scope: str,
    base: str | None,
    command: list[str],
    warnings: list[str],
    auth_status: str,
) -> dict[str, Any]:
    findings = parse_plain_text_review(plain_text)
    if findings:
        summary = summarize(findings)
        return {
            "summary": summary,
            "findings": findings,
            "metadata": {
                "repo": repo,
                "scope": scope,
                "base": base,
                "command": command,
                "warnings": warnings,
                "auth_status": auth_status,
                "status_events": [],
                "output_mode": "plain",
            },
        }

    summary = summarize_plain_review(plain_text)
    return {
        "summary": summary,
        "findings": [],
        "plain_review": plain_text,
        "metadata": {
            "repo": repo,
            "scope": scope,
            "base": base,
            "command": command,
            "warnings": warnings,
            "auth_status": auth_status,
            "status_events": [],
            "output_mode": "plain",
        },
    }


def markdown_for_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    output_mode = report.get("metadata", {}).get("output_mode", "plain")
    repo_root = report.get("metadata", {}).get("repo")
    content_lines = [
        "# Code Review Summary",
        "",
        f"- **Overall Verdict**: `{summary['overall_verdict']}`",
        "- **Review Source**: `CodeRabbit`",
        f"- **Output Mode**: `{output_mode}`",
        "",
    ]
    if summary.get("findings_count") is not None:
        content_lines.insert(
            4, f"- **Findings Count**: `{summary['findings_count']}`")
    findings = report["findings"]
    if not findings:
        plain_review = report.get("plain_review", "").strip()
        if plain_review:
            content_lines.append("## CodeRabbit Output")
            content_lines.append("")
            content_lines.extend(["```text", plain_review, "```"])
        else:
            content_lines.append("No CodeRabbit review output was captured.")
        return "\n".join(content_lines).rstrip() + "\n"

    grouped_findings: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        severity = finding.get("classification") or "unknown"
        grouped_findings.setdefault(severity, []).append(finding)

    for severity, severity_findings in grouped_findings.items():
        content_lines.append(f"## {severity}")
        content_lines.append("")
        for index, finding in enumerate(severity_findings, start=1):
            content_lines.append(f"### {severity} Issue #{index}")
            if finding.get("path"):
                file_path = finding["path"]
                if repo_root and not Path(file_path).is_absolute():
                    absolute_file_path = str(Path(repo_root) / file_path)
                else:
                    absolute_file_path = file_path
                content_lines.append(
                    f"- **File**: [{file_path}]({absolute_file_path})")
            if finding.get("start_line") is not None and finding.get("end_line") is not None:
                content_lines.append(
                    f"- **Lines**: `{finding['start_line']}-{finding['end_line']}`")
            elif finding.get("start_line") is not None:
                content_lines.append(f"- **Line**: `{finding['start_line']}`")
            if finding.get("comment"):
                content_lines.append("- **Comment**:")
                content_lines.append("")
                for line in finding["comment"].splitlines():
                    content_lines.append(f"> {line}" if line else ">")
                content_lines.append("")
            if finding.get("codegen_instructions"):
                content_lines.append(
                    f"- **Codegen Instructions**: {finding['codegen_instructions']}")
            if finding["suggested_refactor"]:
                content_lines.append("- **Suggested Refactor**:")
                content_lines.extend(
                    ["```", finding["suggested_refactor"], "```"])
            if finding["proposed_fix"]:
                code_lang = fence_language_for_path(finding.get("path"))
                content_lines.append("- **Proposed Fix**:")
                content_lines.extend(
                    [f"```{code_lang}", finding["proposed_fix"], "```"])
            content_lines.append("")
    return "\n".join(content_lines).rstrip() + "\n"


def write_report_artifacts(output_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    normalized_path = output_dir / "normalized.json"
    normalized_path.write_text(json.dumps(
        report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path = output_dir / "report.md"
    markdown_path.write_text(markdown_for_report(report), encoding="utf-8")
    return {
        "normalized_json": str(normalized_path),
        "report_markdown": str(markdown_path),
    }


def write_progress(progress_path: Path, **payload: Any) -> None:
    progress_path.write_text(
        json.dumps({"updated_at": int(time.time()), **payload},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )


def git_repo_root(repo: str) -> str:
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    return result.stdout.strip()


def check_preconditions(repo: str) -> dict[str, Any]:
    if shutil.which("coderabbit") is None:
        raise ReviewError("`coderabbit` is not available on PATH.")

    run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    run(["git", "rev-parse", "--verify", "HEAD"], cwd=repo)
    auth_command = ["coderabbit", "auth", "status", "--agent"]
    auth = run(auth_command, cwd=repo)
    if auth.returncode != 0:
        raise ReviewError(f"`{' '.join(auth_command)}` failed.")
    flattened = f"{auth.stdout}\n{auth.stderr}".lower()
    if "not authenticated" in flattened:
        raise ReviewError("CodeRabbit authentication is not active.")
    return {"auth_stdout": auth.stdout, "auth_stderr": auth.stderr}


def tracked_change_summary(repo: str) -> dict[str, Any]:
    result = run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=repo,
    )
    tracked = []
    untracked = []
    for line in result.stdout.splitlines():
        if line.startswith("?? "):
            untracked.append(line[3:])
        elif line:
            tracked.append(line[3:])
    return {"tracked": tracked, "untracked": untracked}


def resolve_base(repo: str, requested: str | None) -> str | None:
    base = requested
    if base is None:
        result = subprocess.run(
            ["git", "symbolic-ref", "--quiet",
                "--short", "refs/remotes/origin/HEAD"],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            resolved = result.stdout.strip()
            if resolved.startswith("origin/"):
                base = resolved[len("origin/"):]
            else:
                base = resolved
    if base is None:
        return None

    verify = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if verify.returncode == 0:
        return base

    remote_verify = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet",
            f"origin/{base}^{{commit}}"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if remote_verify.returncode == 0:
        return f"origin/{base}"

    raise ReviewError(f"Requested base branch does not resolve: {base}")


def determine_scope(repo: str, requested_scope: str, base: str | None) -> tuple[str, list[str]]:
    warnings: list[str] = []
    status = tracked_change_summary(repo)
    if not status["tracked"] and status["untracked"]:
        warnings.append(
            "Repository has only untracked files; CodeRabbit may return no findings because it analyzes tracked changes."
        )

    if requested_scope != "auto":
        return requested_scope, warnings

    if status["tracked"]:
        return "uncommitted", warnings

    if base:
        diff = subprocess.run(
            ["git", "diff", "--quiet", f"{base}...HEAD", "--"],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if diff.returncode == 1:
            return "committed", warnings

    return "all", warnings


def validate_config_paths(repo: str, configs: list[str]) -> list[str]:
    resolved: list[str] = []
    for config in configs:
        path = Path(config)
        if not path.is_absolute():
            path = Path(repo) / path
        if not path.exists():
            raise ReviewError(f"Config path does not exist: {config}")
        resolved.append(str(path))
    return resolved


def stream_process(
    args: list[str],
    *,
    cwd: str,
    timeout_seconds: int,
    stdout_path: Path,
    stderr_path: Path,
    progress_path: Path,
) -> CommandResult:
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def reader(stream: Any, name: str) -> None:
        try:
            for line in iter(stream.readline, ""):
                q.put((name, line))
        finally:
            q.put((name, None))

    threads = [
        threading.Thread(target=reader, args=(
            proc.stdout, "stdout"), daemon=True),
        threading.Thread(target=reader, args=(
            proc.stderr, "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()

    closed = {"stdout": False, "stderr": False}
    start = time.time()
    write_progress(
        progress_path,
        state="running",
        pid=proc.pid,
        command=args,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        elapsed_seconds=0,
        stdout_log=str(stdout_path),
        stderr_log=str(stderr_path),
        stdout_bytes=0,
        stderr_bytes=0,
    )
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        while True:
            elapsed_seconds = int(time.time() - start)
            if time.time() - start > timeout_seconds:
                proc.kill()
                write_progress(
                    progress_path,
                    state="timed_out",
                    pid=proc.pid,
                    command=args,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    elapsed_seconds=elapsed_seconds,
                    stdout_log=str(stdout_path),
                    stderr_log=str(stderr_path),
                    stdout_bytes=sum(len(chunk) for chunk in stdout_chunks),
                    stderr_bytes=sum(len(chunk) for chunk in stderr_chunks),
                )
                raise ReviewProcessError(
                    f"CodeRabbit review timed out after {timeout_seconds} seconds.",
                    stdout="".join(stdout_chunks),
                    stderr="".join(stderr_chunks),
                )
            try:
                stream_name, chunk = q.get(timeout=1.0)
            except queue.Empty:
                write_progress(
                    progress_path,
                    state="running",
                    pid=proc.pid,
                    command=args,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    elapsed_seconds=elapsed_seconds,
                    stdout_log=str(stdout_path),
                    stderr_log=str(stderr_path),
                    stdout_bytes=sum(len(chunk) for chunk in stdout_chunks),
                    stderr_bytes=sum(len(chunk) for chunk in stderr_chunks),
                )
                if proc.poll() is not None and all(closed.values()):
                    break
                continue
            if chunk is None:
                closed[stream_name] = True
                write_progress(
                    progress_path,
                    state="running" if proc.poll() is None else "finalizing",
                    pid=proc.pid,
                    command=args,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    elapsed_seconds=elapsed_seconds,
                    stdout_log=str(stdout_path),
                    stderr_log=str(stderr_path),
                    stdout_bytes=sum(len(chunk) for chunk in stdout_chunks),
                    stderr_bytes=sum(len(chunk) for chunk in stderr_chunks),
                )
                if proc.poll() is not None and all(closed.values()):
                    break
                continue
            if stream_name == "stdout":
                stdout_chunks.append(chunk)
                stdout_file.write(chunk)
                stdout_file.flush()
            else:
                stderr_chunks.append(chunk)
                stderr_file.write(chunk)
                stderr_file.flush()
                sys.stderr.write(chunk)
                sys.stderr.flush()

    result = CommandResult(proc.wait(), "".join(
        stdout_chunks), "".join(stderr_chunks))
    write_progress(
        progress_path,
        state="completed" if result.returncode == 0 else "failed",
        pid=proc.pid,
        command=args,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        elapsed_seconds=int(time.time() - start),
        stdout_log=str(stdout_path),
        stderr_log=str(stderr_path),
        stdout_bytes=len(result.stdout),
        stderr_bytes=len(result.stderr),
        returncode=result.returncode,
    )
    return result


def review_command(args: argparse.Namespace) -> int:
    output_dir: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    progress_path: Path | None = None
    repo = ""
    scope = args.scope
    base = args.base
    warnings: list[str] = []
    preflight: dict[str, Any] = {"auth_stdout": ""}
    command: list[str] = []
    partial_stdout = ""
    try:
        repo = git_repo_root(args.repo)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        progress_path = output_dir / "progress.json"
        write_progress(
            progress_path,
            state="starting",
            repo=repo,
            requested_scope=args.scope,
            requested_base=args.base,
            output_dir=str(output_dir),
        )

        preflight = check_preconditions(repo)
        base = resolve_base(
            repo, args.base) if args.resolve_base else args.base
        scope, warnings = determine_scope(repo, args.scope, base)
        configs = validate_config_paths(repo, args.config or [])
        write_progress(
            progress_path,
            state="preflight_complete",
            repo=repo,
            scope=scope,
            base=base,
            warnings=warnings,
            output_dir=str(output_dir),
        )

        command = ["coderabbit", "review", "--plain",
                   "--type", scope, "--dir", repo]
        if base:
            command.extend(["--base", base])
        if configs:
            command.extend(["--config", *configs])

        stdout_path = output_dir / "coderabbit.stdout.log"
        stderr_path = output_dir / "coderabbit.stderr.log"
        result = stream_process(
            command,
            cwd=repo,
            timeout_seconds=args.timeout_seconds,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            progress_path=progress_path,
        )

        if result.returncode != 0:
            raise ReviewProcessError(
                "CodeRabbit review failed.\n"
                f"stdout:\n{result.stdout[-4000:]}\n"
                f"stderr:\n{result.stderr[-4000:]}",
                stdout=result.stdout,
                stderr=result.stderr,
            )

        report = build_report(
            plain_text=result.stdout,
            repo=repo,
            scope=scope,
            base=base,
            command=command,
            warnings=warnings,
            auth_status=preflight["auth_stdout"],
        )
        summary = report["summary"]
        artifacts = write_report_artifacts(output_dir, report)

        payload = {
            "status": "ok",
            "scope": scope,
            "base": base,
            "findings_count": summary["findings_count"],
            "warnings": warnings,
            "artifacts": {
                **artifacts,
                "stdout_log": str(stdout_path),
                "stderr_log": str(stderr_path),
            },
        }
        write_progress(
            progress_path,
            state="artifacts_ready",
            repo=repo,
            scope=scope,
            base=base,
            findings_count=summary["findings_count"],
            warnings=warnings,
            artifacts=payload["artifacts"],
        )
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    except ReviewProcessError as exc:
        artifacts: dict[str, str] = {}
        if output_dir is not None:
            partial_stdout = exc.stdout
            if not partial_stdout and stdout_path is not None and stdout_path.exists():
                partial_stdout = stdout_path.read_text(encoding="utf-8")
            if partial_stdout.strip():
                report = build_report(
                    plain_text=partial_stdout,
                    repo=repo,
                    scope=scope,
                    base=base,
                    command=command,
                    warnings=warnings,
                    auth_status=preflight["auth_stdout"],
                )
                artifacts = write_report_artifacts(output_dir, report)
            if stdout_path is not None:
                artifacts["stdout_log"] = str(stdout_path)
            if stderr_path is not None:
                artifacts["stderr_log"] = str(stderr_path)
            if progress_path is not None:
                write_progress(
                    progress_path,
                    state="error",
                    repo=repo,
                    scope=scope,
                    base=base,
                    message=str(exc),
                    partial_events_found=bool(partial_stdout.strip()),
                    artifacts=artifacts or None,
                )
        emit_error(
            "review_failed",
            str(exc),
            artifacts=artifacts or None,
            partial_events_found=bool(partial_stdout.strip(
            )) if 'partial_stdout' in locals() else False,
        )
        return 1
    except ReviewError as exc:
        if progress_path is not None:
            write_progress(
                progress_path,
                state="error",
                repo=repo,
                scope=scope,
                base=base,
                message=str(exc),
            )
        emit_error("review_failed", str(exc))
        return 1


def render_command(args: argparse.Namespace) -> int:
    try:
        report = json.loads(Path(args.input).read_text(encoding="utf-8"))
        sys.stdout.write(markdown_for_report(report))
        return 0
    except FileNotFoundError:
        emit_error("missing_input",
                   f"Normalized report not found: {args.input}")
        return 1
    except json.JSONDecodeError as exc:
        emit_error("invalid_json", f"Failed to parse normalized report: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic CodeRabbit wrapper for the code-review skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser(
        "review",
        help="Run CodeRabbit review, capture plain output, and write artifacts.",
    )
    review.add_argument("--repo", required=True,
                        help="Repository path to review.")
    review.add_argument("--output-dir", required=True,
                        help="Directory for logs and normalized artifacts.")
    review.add_argument(
        "--scope",
        choices=["auto", "all", "committed", "uncommitted"],
        default="auto",
        help="Review scope. Default: auto.",
    )
    review.add_argument("--base", help="Optional base branch for comparison.")
    review.add_argument(
        "--resolve-base",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-resolve origin/HEAD when --base is omitted. Default: enabled.",
    )
    review.add_argument(
        "--config",
        action="append",
        default=[],
        help="Additional existing instruction file to pass via --config. Repeatable.",
    )
    review.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help="Maximum time to wait for CodeRabbit completion. Default: 1800.",
    )
    review.set_defaults(func=review_command)

    render = subparsers.add_parser(
        "render",
        help="Render the normalized JSON artifact into the final Markdown report.",
    )
    render.add_argument("--input", required=True,
                        help="Path to normalized.json from the review command.")
    render.set_defaults(func=render_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
