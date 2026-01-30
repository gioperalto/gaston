# Gaston

A multi-agent collaborative development system using git. Gaston coordinates multiple AI agents (or developers) working simultaneously on a shared codebase by managing task assignment, workflow, and code review through git operations and a central task registry.

## Features

- **Agent Management**: Each agent has a local identity for tracking ownership
- **Task Registry**: YAML-based registry tracking tasks, status, dependencies, and file assignments
- **Dependency Checking**: Prevents claiming tasks with unmet dependencies or file conflicts
- **Git Integration**: Automatic branch creation, rebasing, and PR management
- **Workflow Automation**: Streamlined claim → work → submit → review → merge cycle

## Prerequisites

- Python >= 3.10
- Git configured with user.name and user.email
- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/gaston.git
cd gaston

# Install in development mode
pip install -e .
```

## Usage

### Initial Setup

```bash
# Initialize your agent identity (run once per machine)
gaston init <agent-name>
```

### Project Setup

```bash
# Create a new task registry in your project
gaston create-registry "Your project goal"

# Add tasks to the registry
gaston new-task <task-id> "Task description" -f <files> -d <dependencies>
```

### Commands

| Command | Description |
|---------|-------------|
| `gaston init <name>` | Initialize agent identity |
| `gaston create-registry "goal"` | Create a new task registry |
| `gaston new-task <id> "desc"` | Add a task (`-f` files, `-d` dependencies) |
| `gaston tasks` | List all tasks and their status |
| `gaston claim <task-id>` | Claim a task and create a branch |
| `gaston status` | Show your claimed tasks |
| `gaston sync` | Pull latest main and rebase your branch |
| `gaston submit` | Create a PR for your work |
| `gaston review` | List tasks awaiting review |
| `gaston approve <task-id>` | Approve a task's PR |
| `gaston merge <task-id>` | Merge an approved task to main |

### Workflow Example

```bash
# 1. Claim a task (creates branch agent/<name>/<task-id>)
gaston claim user-model

# 2. Make changes and commit normally
git add .
git commit -m "Implement User model"

# 3. Sync with latest main
gaston sync

# 4. Submit a PR
gaston submit -t "User Model" -b "Added User model with validation"

# 5. Another agent reviews and approves
gaston approve user-model

# 6. Merge the PR
gaston merge user-model
```

### Task Registry Format

Tasks are stored in `gaston.yaml`:

```yaml
goal: "Build a file encryption CLI tool"
tasks:
  - id: encrypt-core
    description: "Implement AES encryption/decryption"
    status: pending
    files:
      - pkg/crypto/
    depends_on: []

  - id: cli-interface
    description: "Build CLI with encrypt/decrypt commands"
    status: pending
    files:
      - cmd/
    depends_on:
      - encrypt-core
```

### Task Status Lifecycle

`pending` → `claimed` → `in_progress` → `review` → `merged`

## License

MIT License - Copyright 2026 Giovanni Peralto
