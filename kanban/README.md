# Kanban Task Management

## Structure

This kanban board is organized into four stages:

### 📝 BACKLOG
Tasks that are planned but not yet started.
- New features
- Bug reports
- Improvements
- Technical debt

### 🚀 ONGOING
Tasks currently being worked on.
- Active development
- In progress fixes
- Current sprint items

### 👀 REVIEW
Tasks completed but awaiting review.
- Code review pending
- Testing in progress
- Awaiting approval

### ✅ DONE
Completed and deployed tasks.
- Merged to main
- Deployed to production
- Closed issues

## Task File Format

Each task is a markdown file with the following structure:

```markdown
# TASK-[ID]: [Title]

**Status**: [BACKLOG/ONGOING/REVIEW/DONE]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]
**Type**: [FEATURE/BUG/REFACTOR/DOCS]
**Assigned**: [Name/Unassigned]
**Created**: [Date]
**Updated**: [Date]

## Description
[Detailed description of the task]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Technical Details
[Implementation notes, dependencies, etc.]

## Related Files
- [List of affected files]

## Notes
[Any additional notes or comments]
```

## Commands for Claude

### Create Task
"CREATE TASK [title] in [BACKLOG/ONGOING/REVIEW/DONE]"

### Move Task
"MOVE TASK-[ID] to [BACKLOG/ONGOING/REVIEW/DONE]"

### List Tasks
"LIST TASKS in [BACKLOG/ONGOING/REVIEW/DONE/ALL]"

### Update Task
"UPDATE TASK-[ID] [updates]"

## Example Tasks

### Feature Task
```
TASK-001: Implement Real-time Dashboard Updates
Priority: HIGH
Type: FEATURE
```

### Bug Task
```
TASK-002: Fix WebSocket Connection Drops
Priority: CRITICAL
Type: BUG
```

### Refactor Task
```
TASK-003: Refactor API Service Layer
Priority: MEDIUM
Type: REFACTOR
```

## Workflow

1. **New Task** → BACKLOG
2. **Start Work** → ONGOING
3. **Complete Work** → REVIEW
4. **Pass Review** → DONE

## Review Criteria

Before moving to DONE:
- [ ] Code reviewed (use REVIEW command)
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] No critical violations
- [ ] Impact analyzed (use ANALYZE command)