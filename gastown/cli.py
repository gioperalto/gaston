"""Gastown CLI - Multi-agent collaborative development."""

import sys
from pathlib import Path

import click

from .agent import AgentConfig
from .gitops import (
    GitError,
    branch_exists,
    create_branch,
    create_pr,
    fetch,
    get_current_branch,
    get_default_branch,
    get_repo_root,
    has_changes,
    has_remote,
    is_rebased,
    list_prs,
    approve_pr,
    merge_pr,
    pull,
    push,
    rebase,
    stage_file,
    switch_branch,
    commit,
)
from .registry import Registry, TaskStatus


def get_context() -> tuple[Path, Registry]:
    """Get repo root and load registry."""
    try:
        repo_root = get_repo_root()
    except GitError:
        click.echo("Error: Not in a git repository.", err=True)
        sys.exit(1)

    try:
        registry = Registry.load(repo_root)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    return repo_root, registry


@click.group()
@click.version_option()
def cli():
    """Gastown: Multi-agent collaborative development system.

    Coordinate multiple agents working on a shared codebase using git.
    """
    pass


@cli.command()
@click.argument("name")
def init(name: str):
    """Initialize this agent with a name.

    The agent name is used to identify your work in the task registry
    and for branch naming.

    Example: gastown init alpha
    """
    config = AgentConfig(name=name)
    config.save()
    click.echo(f"Initialized agent '{name}'")
    click.echo(f"Config saved to: {config.config_path()}")


@cli.command()
def tasks():
    """List all tasks and their status."""
    repo_root, registry = get_context()

    click.echo(f"Goal: {registry.goal}\n")
    click.echo("Tasks:")
    click.echo("-" * 60)

    for task in registry.tasks:
        status_color = {
            TaskStatus.PENDING: "white",
            TaskStatus.CLAIMED: "yellow",
            TaskStatus.IN_PROGRESS: "cyan",
            TaskStatus.REVIEW: "magenta",
            TaskStatus.MERGED: "green",
        }.get(task.status, "white")

        status_str = click.style(f"[{task.status.value}]", fg=status_color)

        click.echo(f"  {task.id}: {task.description}")
        click.echo(f"    Status: {status_str}")

        if task.claimed_by:
            click.echo(f"    Claimed by: {task.claimed_by}")
        if task.branch:
            click.echo(f"    Branch: {task.branch}")
        if task.depends_on:
            click.echo(f"    Depends on: {', '.join(task.depends_on)}")
        if task.files:
            click.echo(f"    Files: {', '.join(task.files)}")
        click.echo()


@cli.command()
@click.argument("task_id")
@click.option("--force", is_flag=True, help="Claim even with conflicts or unmet deps")
def claim(task_id: str, force: bool):
    """Claim a task and create a branch for it.

    This marks the task as claimed by you and creates a new branch
    for your work.

    Example: gastown claim implement-auth
    """
    agent = AgentConfig.require()
    repo_root, registry = get_context()

    task = registry.get_task(task_id)
    if task is None:
        click.echo(f"Error: Task '{task_id}' not found.", err=True)
        sys.exit(1)

    if task.status != TaskStatus.PENDING:
        click.echo(
            f"Error: Task '{task_id}' is not pending (status: {task.status.value}).",
            err=True,
        )
        sys.exit(1)

    # Check dependencies
    unmet = registry.check_dependencies(task)
    if unmet and not force:
        click.echo("Error: Unmet dependencies:", err=True)
        for dep in unmet:
            click.echo(f"  - {dep}", err=True)
        click.echo("\nUse --force to claim anyway.", err=True)
        sys.exit(1)

    # Check for file conflicts
    conflicts = registry.check_file_conflicts(task)
    if conflicts and not force:
        click.echo("Warning: Potential file conflicts:", err=True)
        for file, other in conflicts:
            click.echo(f"  - {file} (also in {other.id} by {other.claimed_by})", err=True)
        click.echo("\nUse --force to claim anyway.", err=True)
        sys.exit(1)

    # Create branch
    branch_name = f"agent/{agent.name}/{task_id}"
    if branch_exists(branch_name, repo_root):
        click.echo(f"Error: Branch '{branch_name}' already exists.", err=True)
        sys.exit(1)

    # Switch to default branch first
    default_branch = get_default_branch(repo_root)
    switch_branch(default_branch, repo_root)

    # Pull latest
    if has_remote(repo_root):
        try:
            pull(repo_root)
        except GitError:
            pass  # Might not have remote tracking

    # Create and switch to new branch
    create_branch(branch_name, repo_root)

    # Update registry
    task.status = TaskStatus.CLAIMED
    task.claimed_by = agent.name
    task.branch = branch_name

    # Save registry, then stage and commit
    registry.save(repo_root)
    stage_file("gastown.yaml", repo_root)
    commit(f"[gastown] Claim task: {task_id}", repo_root)

    click.echo(f"Claimed task '{task_id}'")
    click.echo(f"Created branch: {branch_name}")
    click.echo("\nNext steps:")
    click.echo("  1. Make your changes")
    click.echo("  2. Commit your work")
    click.echo("  3. Run 'gastown submit' to create a PR")


@cli.command()
def status():
    """Show your current claimed tasks."""
    agent = AgentConfig.require()
    repo_root, registry = get_context()

    my_tasks = registry.get_tasks_by_agent(agent.name)
    current_branch = get_current_branch(repo_root)

    click.echo(f"Agent: {agent.name}")
    click.echo(f"Current branch: {current_branch}")
    click.echo()

    if not my_tasks:
        click.echo("No tasks claimed.")
        return

    click.echo("Your tasks:")
    for task in my_tasks:
        marker = "*" if task.branch == current_branch else " "
        click.echo(f"  {marker} {task.id}: {task.description}")
        click.echo(f"      Status: {task.status.value}")
        click.echo(f"      Branch: {task.branch}")


@cli.command()
def sync():
    """Pull latest changes and rebase your branch."""
    agent = AgentConfig.require()
    repo_root, registry = get_context()

    current_branch = get_current_branch(repo_root)
    default_branch = get_default_branch(repo_root)

    if current_branch == default_branch:
        click.echo(f"On {default_branch}, pulling latest...")
        if has_remote(repo_root):
            fetch(repo_root)
            pull(repo_root)
        click.echo("Done.")
        return

    if has_changes(repo_root):
        click.echo("Error: You have uncommitted changes. Commit or stash first.", err=True)
        sys.exit(1)

    click.echo(f"Fetching latest from remote...")
    if has_remote(repo_root):
        fetch(repo_root)

    click.echo(f"Rebasing {current_branch} onto {default_branch}...")
    try:
        rebase(f"origin/{default_branch}", repo_root)
        click.echo("Rebase successful.")
    except GitError as e:
        click.echo(f"Rebase failed: {e}", err=True)
        click.echo("Resolve conflicts and run 'git rebase --continue'", err=True)
        sys.exit(1)


@cli.command()
@click.option("--title", "-t", help="PR title (defaults to task description)")
@click.option("--body", "-b", help="PR body")
def submit(title: str, body: str):
    """Submit your work as a pull request.

    Creates a PR from your current branch to the default branch.
    The task status will be updated to 'review'.
    """
    agent = AgentConfig.require()
    repo_root, registry = get_context()

    current_branch = get_current_branch(repo_root)
    default_branch = get_default_branch(repo_root)

    if current_branch == default_branch:
        click.echo(f"Error: You're on {default_branch}. Switch to a task branch first.", err=True)
        sys.exit(1)

    # Find the task for this branch
    task = None
    for t in registry.tasks:
        if t.branch == current_branch:
            task = t
            break

    if task is None:
        click.echo(f"Error: No task found for branch '{current_branch}'.", err=True)
        sys.exit(1)

    if task.claimed_by != agent.name:
        click.echo(f"Error: This task is claimed by '{task.claimed_by}', not you.", err=True)
        sys.exit(1)

    # Check if rebased
    if has_remote(repo_root):
        fetch(repo_root)
        if not is_rebased(f"origin/{default_branch}", repo_root):
            click.echo("Error: Branch is not rebased onto latest main.", err=True)
            click.echo("Run 'gastown sync' first.", err=True)
            sys.exit(1)

    # Push branch
    click.echo(f"Pushing {current_branch}...")
    try:
        push(current_branch, set_upstream=True, cwd=repo_root)
    except GitError as e:
        click.echo(f"Push failed: {e}", err=True)
        sys.exit(1)

    # Create PR
    pr_title = title or f"{task.id}: {task.description}"
    pr_body = body or f"""## Task
{task.description}

## Files affected
{chr(10).join(f'- {f}' for f in task.files) if task.files else 'Not specified'}

---
Submitted by agent: {agent.name}
"""

    click.echo("Creating pull request...")
    try:
        pr = create_pr(pr_title, pr_body, default_branch, repo_root)
        click.echo(f"Created PR #{pr.number}: {pr.url}")
    except GitError as e:
        click.echo(f"Failed to create PR: {e}", err=True)
        click.echo("You may need to create the PR manually.", err=True)
        # Still update registry
        pass

    # Update task status
    task.status = TaskStatus.REVIEW
    registry.save(repo_root)

    # Commit registry update
    stage_file("gastown.yaml", repo_root)
    commit(f"[gastown] Submit task for review: {task.id}", repo_root)
    push(current_branch, cwd=repo_root)

    click.echo(f"\nTask '{task.id}' is now awaiting review.")


@cli.command()
def review():
    """List pull requests awaiting review."""
    repo_root, registry = get_context()

    # Get tasks in review
    review_tasks = registry.get_tasks_in_review()

    if not review_tasks:
        click.echo("No tasks awaiting review.")
        return

    click.echo("Tasks awaiting review:")
    click.echo("-" * 60)

    for task in review_tasks:
        click.echo(f"  {task.id}: {task.description}")
        click.echo(f"    Author: {task.claimed_by}")
        click.echo(f"    Branch: {task.branch}")
        if task.files:
            click.echo(f"    Files: {', '.join(task.files)}")
        click.echo()

    # Also try to list PRs from GitHub
    try:
        prs = list_prs("open", repo_root)
        if prs:
            click.echo("\nOpen PRs on GitHub:")
            for pr in prs:
                click.echo(f"  #{pr.number}: {pr.title}")
                click.echo(f"    Branch: {pr.branch}")
                click.echo(f"    URL: {pr.url}")
                click.echo()
    except GitError:
        pass  # gh CLI not available or not authenticated


@cli.command()
@click.argument("task_id")
def approve(task_id: str):
    """Approve a task after reviewing it.

    This approves the PR on GitHub if possible.
    """
    agent = AgentConfig.require()
    repo_root, registry = get_context()

    task = registry.get_task(task_id)
    if task is None:
        click.echo(f"Error: Task '{task_id}' not found.", err=True)
        sys.exit(1)

    if task.status != TaskStatus.REVIEW:
        click.echo(f"Error: Task is not in review (status: {task.status.value}).", err=True)
        sys.exit(1)

    if task.claimed_by == agent.name:
        click.echo("Error: You cannot approve your own task.", err=True)
        sys.exit(1)

    # Try to find and approve the PR
    try:
        prs = list_prs("open", repo_root)
        for pr in prs:
            if pr.branch == task.branch:
                click.echo(f"Approving PR #{pr.number}...")
                approve_pr(pr.number, repo_root)
                click.echo(f"Approved PR #{pr.number}")
                break
        else:
            click.echo("No matching PR found. Approval recorded in registry only.")
    except GitError as e:
        click.echo(f"Could not approve via GitHub: {e}")
        click.echo("Approval will be recorded in registry.")

    click.echo(f"\nTask '{task_id}' approved by {agent.name}.")
    click.echo(f"The author ({task.claimed_by}) can now merge with 'gastown merge {task_id}'.")


@cli.command("merge")
@click.argument("task_id")
def merge_task(task_id: str):
    """Merge an approved task to main.

    This merges the PR and updates the task status to 'merged'.
    """
    agent = AgentConfig.require()
    repo_root, registry = get_context()

    task = registry.get_task(task_id)
    if task is None:
        click.echo(f"Error: Task '{task_id}' not found.", err=True)
        sys.exit(1)

    if task.status != TaskStatus.REVIEW:
        click.echo(f"Error: Task is not in review (status: {task.status.value}).", err=True)
        sys.exit(1)

    # Try to find and merge the PR
    try:
        prs = list_prs("open", repo_root)
        for pr in prs:
            if pr.branch == task.branch:
                click.echo(f"Merging PR #{pr.number}...")
                merge_pr(pr.number, repo_root)
                click.echo(f"Merged PR #{pr.number}")
                break
        else:
            click.echo("No matching PR found on GitHub.", err=True)
            click.echo("You may need to merge manually.", err=True)
            sys.exit(1)
    except GitError as e:
        click.echo(f"Merge failed: {e}", err=True)
        sys.exit(1)

    # Update task status
    task.status = TaskStatus.MERGED
    registry.save(repo_root)

    # Need to update registry on main branch
    default_branch = get_default_branch(repo_root)
    switch_branch(default_branch, repo_root)
    pull(repo_root)

    # Registry should be updated - save and commit
    stage_file("gastown.yaml", repo_root)
    commit(f"[gastown] Mark task as merged: {task_id}", repo_root)
    push(default_branch, cwd=repo_root)

    click.echo(f"\nTask '{task_id}' has been merged!")


@cli.command("new-task")
@click.argument("task_id")
@click.argument("description")
@click.option("--files", "-f", multiple=True, help="Files/directories this task affects")
@click.option("--depends", "-d", multiple=True, help="Task IDs this depends on")
def new_task(task_id: str, description: str, files: tuple, depends: tuple):
    """Add a new task to the registry.

    Example: gastown new-task auth "Implement user authentication" -f src/auth/ -f src/models/user.py
    """
    repo_root, registry = get_context()

    if registry.get_task(task_id):
        click.echo(f"Error: Task '{task_id}' already exists.", err=True)
        sys.exit(1)

    from .registry import Task

    task = Task(
        id=task_id,
        description=description,
        files=list(files),
        depends_on=list(depends),
    )

    registry.tasks.append(task)
    registry.save(repo_root)

    click.echo(f"Added task: {task_id}")
    click.echo(f"  Description: {description}")
    if files:
        click.echo(f"  Files: {', '.join(files)}")
    if depends:
        click.echo(f"  Depends on: {', '.join(depends)}")


@cli.command("create-registry")
@click.argument("goal")
def create_registry(goal: str):
    """Create a new gastown.yaml registry.

    Example: gastown create-registry "Build a REST API for user management"
    """
    try:
        repo_root = get_repo_root()
    except GitError:
        click.echo("Error: Not in a git repository.", err=True)
        sys.exit(1)

    registry_path = Registry.registry_path(repo_root)
    if registry_path.exists():
        click.echo(f"Error: {registry_path} already exists.", err=True)
        sys.exit(1)

    registry = Registry(goal=goal, tasks=[])
    registry.save(repo_root)

    click.echo(f"Created {registry_path}")
    click.echo(f"Goal: {goal}")
    click.echo("\nAdd tasks with: gastown new-task <id> <description>")


if __name__ == "__main__":
    cli()
