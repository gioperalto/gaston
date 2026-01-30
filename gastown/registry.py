"""Task registry management (gastown.yaml)."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    MERGED = "merged"


@dataclass
class Task:
    """A task in the registry."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    claimed_by: Optional[str] = None
    branch: Optional[str] = None
    files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create a Task from a dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            status=TaskStatus(data.get("status", "pending")),
            claimed_by=data.get("claimed_by"),
            branch=data.get("branch"),
            files=data.get("files", []),
            depends_on=data.get("depends_on", []),
        )

    def to_dict(self) -> dict:
        """Convert to a dictionary for YAML serialization."""
        d = {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
        }
        if self.claimed_by:
            d["claimed_by"] = self.claimed_by
        if self.branch:
            d["branch"] = self.branch
        if self.files:
            d["files"] = self.files
        if self.depends_on:
            d["depends_on"] = self.depends_on
        return d


@dataclass
class Registry:
    """The task registry."""
    goal: str
    tasks: list[Task]

    @classmethod
    def registry_path(cls, repo_root: Path) -> Path:
        """Get the path to gastown.yaml."""
        return repo_root / "gastown.yaml"

    @classmethod
    def load(cls, repo_root: Path) -> "Registry":
        """Load the registry from gastown.yaml."""
        path = cls.registry_path(repo_root)
        if not path.exists():
            raise FileNotFoundError(
                f"No gastown.yaml found at {path}. "
                "Create one to define tasks for this project."
            )

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            goal=data.get("goal", ""),
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
        )

    def save(self, repo_root: Path) -> None:
        """Save the registry to gastown.yaml."""
        path = self.registry_path(repo_root)

        data = {
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def get_tasks_by_agent(self, agent_name: str) -> list[Task]:
        """Get all tasks claimed by an agent."""
        return [t for t in self.tasks if t.claimed_by == agent_name]

    def get_tasks_in_review(self) -> list[Task]:
        """Get all tasks awaiting review."""
        return [t for t in self.tasks if t.status == TaskStatus.REVIEW]

    def check_dependencies(self, task: Task) -> list[str]:
        """Check if task dependencies are satisfied. Returns list of unmet deps."""
        unmet = []
        for dep_id in task.depends_on:
            dep = self.get_task(dep_id)
            if dep is None:
                unmet.append(f"{dep_id} (not found)")
            elif dep.status != TaskStatus.MERGED:
                unmet.append(f"{dep_id} (status: {dep.status.value})")
        return unmet

    def check_file_conflicts(self, task: Task) -> list[tuple[str, Task]]:
        """Check for file conflicts with other in-progress tasks.

        Returns list of (conflicting_file, other_task) tuples.
        """
        conflicts = []
        active_statuses = {TaskStatus.CLAIMED, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW}

        for other in self.tasks:
            if other.id == task.id:
                continue
            if other.status not in active_statuses:
                continue

            # Check for file overlaps
            for task_file in task.files:
                for other_file in other.files:
                    if self._paths_overlap(task_file, other_file):
                        conflicts.append((task_file, other))

        return conflicts

    @staticmethod
    def _paths_overlap(path1: str, path2: str) -> bool:
        """Check if two file paths might conflict."""
        # Normalize trailing slashes
        p1 = path1.rstrip("/")
        p2 = path2.rstrip("/")

        # Check if one is a prefix of the other (directory contains file)
        return p1.startswith(p2) or p2.startswith(p1) or p1 == p2
