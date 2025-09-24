---
name: complete-task
description: Move task from review to done and create git commit
parameters:
  - name: task
    description: Task ID from kanban/review folder (e.g., TASK-004)
    required: true
  - name: summary
    description: Brief summary of what was accomplished
    required: false
    default: ""
---

# Complete Task & Commit

Move task from review to done and create a git commit following project standards.

## Process Overview

1. **Validate task** in kanban/review/${task}*.md
2. **Verify review status** is approved
3. **Generate completion summary** from task changes
4. **Update task** with completion metadata
5. **Move to done** folder (required before commit)
6. **Create git commit** using @commit command
7. **Generate completion report**

## Completion Steps

### Step 1: Task Validation

```bash
# Verify task exists in review
if [ ! -f "kanban/review/${task}*.md" ]; then
    echo "ERROR: Task ${task} not found in review folder"
    echo "Task must be in review before completing"
    exit 1
fi

# Check if review report exists
if [ ! -f "kanban/review/${task}-code-review-report.md" ]; then
    echo "WARNING: No review report found for ${task}"
    echo "Consider running review-task first"
fi

# Read task to verify review status
review_status=$(grep -i "status.*approved" kanban/review/${task}-code-review-report.md 2>/dev/null)

if [ -z "$review_status" ]; then
    echo "ERROR: Task ${task} is not approved"
    echo "Review must be approved before completing task"
    exit 1
fi
```

Check for:
- ✅ Review decision is APPROVED
- ✅ Review report exists
- ✅ No critical issues pending
- ✅ All acceptance criteria met

### Step 2: Extract Task Information

From the task file, extract:
- Task title
- Key changes implemented
- Technical improvements made
- Files modified
- Components affected

### Step 3: Update Task with Completion Data

Add completion section to task:

```markdown
## Completion Summary (${date})

### Implemented Features
- ✅ [Feature 1 from acceptance criteria]
- ✅ [Feature 2 from acceptance criteria]
- ✅ [Feature 3 from acceptance criteria]

### Technical Changes
- [Component/File]: [What was changed]
- [Component/File]: [What was changed]

### Code Quality Improvements
- SOLID principles applied: [specifics]
- ACID compliance ensured: [where applicable]
- Reused components: [list of reused items]
- No code duplication

### Files Modified
${list_of_modified_files}

### Testing Status
- [ ] Unit tests added/updated
- [ ] Integration tests passed
- [ ] Manual testing completed
- [ ] Edge cases handled

### Documentation
- [ ] Code comments added where necessary
- [ ] README updated if needed
- [ ] API documentation updated
- [ ] Type definitions complete

### Performance Impact
- Bundle size: [no change/+X KB/-X KB]
- Load time: [no impact/improved/slight increase]
- Database queries: [optimized/no change]

### Completion Metrics
- **Estimated Effort**: [original estimate]
- **Actual Effort**: [actual time taken]
- **Complexity**: [as expected/higher/lower]
- **Technical Debt**: [none added/minor/addressed existing]

### Lessons Learned
${summary_or_default_to_empty}
```

### Step 4: Prepare Commit Message

Generate structured commit message:

```bash
# Format for commit message
[${task}] ${task_title}

✅ Implemented:
- ${key_feature_1}
- ${key_feature_2}
- ${key_feature_3}

📁 Files Modified:
- ${component_1}: ${change_1}
- ${component_2}: ${change_2}

🔧 Technical:
- Applied SOLID principles
- Ensured ACID compliance
- No code duplication
- Reused existing components

📊 Status: Review approved, task completed
Task: ${task}
${summary}
```

### Step 5: Git Operations

```bash
# Ensure on dev branch
git branch --show-current

# If not on dev, switch
if [ "$(git branch --show-current)" = "main" ]; then
    echo "ERROR: Cannot commit to main branch!"
    git checkout dev
fi

# Stage all changes related to task
git add -A

# Review what will be committed
git status
git diff --cached --stat

# Check if author is already configured (following @commit rules)
current_name=$(git config user.name)
current_email=$(git config user.email)

# Verify author is Glody (email can be any valid email)
if [[ "$current_name" == *"Glody"* ]] && [[ -n "$current_email" ]]; then
    echo "Git author verified: $current_name <$current_email>"
else
    # Only try to set if not configured
    if [[ "$current_name" != *"Glody"* ]]; then
        echo "ERROR: Git author must be configured as Glody Figueiredo"
        echo "Current name: $current_name"
        echo "Please run: git config user.name 'Glody Figueiredo'"
    fi
    if [[ -z "$current_email" ]]; then
        echo "ERROR: Git email not configured"
        echo "Please run: git config user.email 'your-email@example.com'"
    fi
    exit 1
fi
```

### Step 6: Move to Done

```bash
# Check if done directory exists (it should already exist)
if [ ! -d "kanban/done" ]; then
    echo "ERROR: kanban/done directory doesn't exist"
    echo "Project structure might be corrupted"
    exit 1
fi

# Check if task already exists in done
if [ -f "kanban/done/${task}*.md" ]; then
    echo "WARNING: Task ${task} already exists in done folder"
    echo "This task might have been completed already"
    exit 1
fi

# Move task file with completion data
mv kanban/review/${task}*.md kanban/done/

# Verify move
if [ -f "kanban/done/${task}*.md" ]; then
    echo "✅ Task successfully moved to done folder"
    ls kanban/done/${task}*.md
else
    echo "ERROR: Failed to move task to done folder"
    exit 1
fi
```

### Step 7: Execute Commit

Call the @commit command with task reference (task must be in done/ folder):

```bash
# This will be executed via @commit command
@commit ${task} "${summary}"
```

The commit command will:
- Find task file in kanban/done/ folder
- Verify branch (not main)
- Create proper commit message
- Include task reference
- Set correct author
- No AI attribution

### Step 8: Post-Completion Checklist

After task is complete:

```markdown
## Post-Completion Checklist
- ✅ Task moved to kanban/done/
- ✅ Git commit created with task reference
- ✅ Author is Glody Figueiredo (no AI attribution)
- ✅ Committed to dev branch (not main)
- ✅ All changes staged and committed
- ✅ Completion summary documented
- ✅ Review feedback addressed

## Ready for:
- [ ] Merge to UAT for testing
- [ ] Update project documentation
- [ ] Team notification if needed
```

### Step 9: Generate Completion Report

```markdown
# Task Completion Report

**Task**: ${task}
**Title**: ${task_title}
**Completed**: ${date}
**Duration**: ${start_date} to ${date}

## Summary
${summary_or_extracted}

## Deliverables
- ✅ All acceptance criteria met
- ✅ Code review passed
- ✅ Git commit created
- ✅ Documentation updated

## Git Commit
- **Commit Hash**: ${git_commit_hash}
- **Branch**: dev
- **Author**: Glody Figueiredo
- **Message**: [${task}] ${task_title}

## Next Steps
1. Merge dev → uat for testing
2. UAT validation
3. Prepare for production release

## Metrics
- **Code Quality**: PASSED
- **SOLID Compliance**: YES
- **ACID Compliance**: YES (where applicable)
- **Duplication**: NONE
- **Technical Debt**: NONE ADDED
```

## Important Rules

1. **NEVER complete if review not approved**
2. **ALWAYS move task to done BEFORE calling @commit**
3. **ALWAYS create git commit**
4. **NEVER commit to main branch**
5. **ALWAYS use Glody Figueiredo as author**
6. **NEVER include AI/Claude attribution**
7. **ALWAYS document what was implemented**
8. **ALWAYS verify acceptance criteria met**

## Error Handling

If any step fails:

### Review Not Approved
```bash
echo "ERROR: Task ${task} review status is not APPROVED"
echo "Please address review feedback first"
exit 1
```

### On Wrong Branch
```bash
if [ "$(git branch --show-current)" = "main" ]; then
    echo "ERROR: On main branch. Switching to dev..."
    git stash
    git checkout dev
    git stash pop
fi
```

### Uncommitted Changes
```bash
if [ -n "$(git status --porcelain)" ]; then
    echo "Found uncommitted changes. Committing..."
    # Proceed with commit
else
    echo "WARNING: No changes to commit"
fi
```

## Output

After successful completion:

1. **Task moved to**: kanban/done/${task}.md
2. **Git commit created**: With proper message and author (after task moved to done)
3. **Completion report**: Generated and displayed
4. **Ready for**: UAT testing via dev → uat merge

## Integration with Other Commands

This command integrates with:
- **@commit**: Automatically called for git commit
- **@review-task**: Reads review status
- **@start-task**: References original analysis

## Workflow Summary

```
backlog → (@start-task) → in-progress → (@review-task) → review → (@complete-task) → done
                ↓                          ↓                           ↓
          [analysis added]          [review report]            [move + git commit]
```