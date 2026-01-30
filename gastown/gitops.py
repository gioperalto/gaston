"""Git operations wrapper."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Error from a git command."""
    pass


def run_git(*args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if check and result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")

    return result.stdout.strip()


def get_repo_root(cwd: Optional[Path] = None) -> Path:
    """Get the root directory of the git repository."""
    root = run_git("rev-parse", "--show-toplevel", cwd=cwd)
    return Path(root)


def get_current_branch(cwd: Optional[Path] = None) -> str:
    """Get the name of the current branch."""
    return run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)


def get_default_branch(cwd: Optional[Path] = None) -> str:
    """Get the default branch (main or master)."""
    try:
        run_git("rev-parse", "--verify", "main", cwd=cwd)
        return "main"
    except GitError:
        return "master"


def branch_exists(branch: str, cwd: Optional[Path] = None) -> bool:
    """Check if a branch exists."""
    try:
        run_git("rev-parse", "--verify", branch, cwd=cwd)
        return True
    except GitError:
        return False


def create_branch(branch: str, cwd: Optional[Path] = None) -> None:
    """Create a new branch and switch to it."""
    run_git("checkout", "-b", branch, cwd=cwd)


def switch_branch(branch: str, cwd: Optional[Path] = None) -> None:
    """Switch to an existing branch."""
    run_git("checkout", branch, cwd=cwd)


def commit(message: str, cwd: Optional[Path] = None) -> None:
    """Create a commit with all staged changes."""
    run_git("commit", "-m", message, cwd=cwd)


def stage_file(path: str, cwd: Optional[Path] = None) -> None:
    """Stage a file for commit."""
    run_git("add", path, cwd=cwd)


def has_changes(cwd: Optional[Path] = None) -> bool:
    """Check if there are uncommitted changes."""
    status = run_git("status", "--porcelain", cwd=cwd)
    return bool(status)


def has_staged_changes(cwd: Optional[Path] = None) -> bool:
    """Check if there are staged changes."""
    diff = run_git("diff", "--cached", "--name-only", cwd=cwd)
    return bool(diff)


def pull(cwd: Optional[Path] = None) -> None:
    """Pull from remote."""
    run_git("pull", cwd=cwd)


def push(branch: str, set_upstream: bool = False, cwd: Optional[Path] = None) -> None:
    """Push to remote."""
    if set_upstream:
        run_git("push", "-u", "origin", branch, cwd=cwd)
    else:
        run_git("push", cwd=cwd)


def rebase(base: str, cwd: Optional[Path] = None) -> None:
    """Rebase current branch onto base."""
    run_git("rebase", base, cwd=cwd)


def fetch(cwd: Optional[Path] = None) -> None:
    """Fetch from all remotes."""
    run_git("fetch", "--all", cwd=cwd)


def is_rebased(base: str, cwd: Optional[Path] = None) -> bool:
    """Check if current branch is rebased onto base."""
    merge_base = run_git("merge-base", "HEAD", base, cwd=cwd)
    base_commit = run_git("rev-parse", base, cwd=cwd)
    return merge_base == base_commit


def get_remote_url(cwd: Optional[Path] = None) -> Optional[str]:
    """Get the remote origin URL."""
    try:
        return run_git("remote", "get-url", "origin", cwd=cwd)
    except GitError:
        return None


def has_remote(cwd: Optional[Path] = None) -> bool:
    """Check if a remote is configured."""
    return get_remote_url(cwd) is not None


@dataclass
class PRInfo:
    """Information about a pull request."""
    number: int
    title: str
    branch: str
    author: str
    url: str


def create_pr(title: str, body: str, base: str, cwd: Optional[Path] = None) -> PRInfo:
    """Create a pull request using gh CLI."""
    result = run_git(
        "gh", "pr", "create",
        "--title", title,
        "--body", body,
        "--base", base,
    )
    # This is actually gh, not git - we'll handle this differently
    # For now, let's use subprocess directly
    proc = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body", body, "--base", base],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(f"Failed to create PR: {proc.stderr.strip()}")

    # gh pr create outputs the PR URL
    url = proc.stdout.strip()
    # Extract PR number from URL
    number = int(url.split("/")[-1])

    return PRInfo(
        number=number,
        title=title,
        branch=get_current_branch(cwd),
        author="",  # Would need another call to get this
        url=url,
    )


def list_prs(state: str = "open", cwd: Optional[Path] = None) -> list[PRInfo]:
    """List pull requests using gh CLI."""
    proc = subprocess.run(
        ["gh", "pr", "list", "--state", state, "--json", "number,title,headRefName,author,url"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(f"Failed to list PRs: {proc.stderr.strip()}")

    import json
    prs = json.loads(proc.stdout) if proc.stdout.strip() else []

    return [
        PRInfo(
            number=pr["number"],
            title=pr["title"],
            branch=pr["headRefName"],
            author=pr["author"]["login"] if pr.get("author") else "",
            url=pr["url"],
        )
        for pr in prs
    ]


def approve_pr(number: int, cwd: Optional[Path] = None) -> None:
    """Approve a pull request using gh CLI."""
    proc = subprocess.run(
        ["gh", "pr", "review", str(number), "--approve"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(f"Failed to approve PR: {proc.stderr.strip()}")


def merge_pr(number: int, cwd: Optional[Path] = None) -> None:
    """Merge a pull request using gh CLI."""
    proc = subprocess.run(
        ["gh", "pr", "merge", str(number), "--merge", "--delete-branch"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(f"Failed to merge PR: {proc.stderr.strip()}")
