---
name: commit
description: Create a git commit following project standards and linking to kanban tasks
parameters:
  - name: task
    description: Task ID from kanban/done folder (e.g., TASK-003)
    required: true
  - name: message
    description: Additional commit message details
    required: false
    default: ""
---

# Smart Git Commit

Create a git commit following Kielis project standards.

## Pre-commit Checklist

1. **Verify current branch**
   - NEVER commit directly to main
   - Should be on `dev` branch (or feature branch)
   - If on main, switch to dev first

2. **Link to completed task**
   - Find task file in kanban/done/ matching "${task}"
   - Extract task title and key changes
   - Include task reference in commit message

3. **Review changes**
   - Run git status to see all changes
   - Run git diff to review modifications
   - Identify all affected components

4. **Commit Standards**
   - Start with verb (Add, Fix, Update, Remove, Refactor)
   - Reference task ID
   - Keep first line under 50 characters
   - Add bullet points for multiple changes
   - Author: Glody Figueiredo (with configured email)
   - NO Claude AI co-author attribution

## Commit Process

### Step 1: Branch Verification
```bash
# Check current branch
git branch --show-current

# If on main, switch to dev
git checkout dev
git pull origin dev
```

### Step 2: Task Validation
- Read kanban/done/${task}*.md to get task details
- Extract task title and key implementation points
- Prepare structured commit message

### Step 3: Stage Changes
```bash
# Review changes
git status
git diff

# Stage relevant files
git add [files related to task]
```

### Step 4: Create Commit
```bash
# Check if author is already configured
current_name=$(git config user.name)
current_email=$(git config user.email)

# Verify author is Glody
if [[ "$current_name" == *"Glody"* ]] && [[ -n "$current_email" ]]; then
    echo "Git author verified: $current_name <$current_email>"
else
    echo "ERROR: Git author must be configured as Glody Figueiredo"
    echo "Current: $current_name <$current_email>"
    echo "Please run: git config user.name 'Glody Figueiredo'"
    echo "And: git config user.email 'your-email@example.com'"
    exit 1
fi

# Commit with task reference
git commit -m "[${task}] Task title here

- Key change 1
- Key change 2
- Key change 3

Task: ${task}
${message}"
```

### Step 5: Verify Commit
```bash
# Check the commit was created correctly
git log -1 --pretty=fuller

# Ensure:
# - Author is Glody Figueiredo
# - No Claude/AI attribution
# - Task reference included
# - On dev branch
```

## Branch Strategy Reminder
- `main`: Production branch (protected)
- `dev`: Development branch (active development)
- `uat`: User Acceptance Testing (merged from dev)
- Flow: feature → dev → uat → main

## Important Rules
- NEVER use --force on shared branches
- ALWAYS pull before pushing
- NEVER commit directly to main
- ALWAYS reference a task from kanban/done
- NEVER include AI/Claude attribution
- ALWAYS use Glody Figueiredo as author

## Error Handling
- If on wrong branch: stash changes, switch branch, apply stash
- If task not found in done: verify task completion first
- If author wrong: use --amend to fix before pushing