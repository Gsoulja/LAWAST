---
name: create-task
description: Create a new task with dependency analysis and automatic task splitting
parameters:
  - name: title
    description: Brief title for the task
    required: true
  - name: description
    description: Detailed description of what needs to be done
    required: true
  - name: type
    description: Type of task (feature/bug/refactor/docs/test)
    required: false
    default: "feature"
---

# Create Task with Analysis

Create a new task in the backlog with comprehensive analysis and automatic splitting if needed.

## Process Overview

1. **Analyze the request** to understand scope
2. **Check existing code** for similar functionality
3. **Identify dependencies** and requirements
4. **Estimate complexity** and effort
5. **Split if needed** into smaller tasks
6. **Create task file(s)** in kanban/backlog/

## Step 1: Request Analysis

### Parse the Description
Analyze "${description}" to identify:
- Main objective
- Technical requirements
- User-facing changes
- Backend vs Frontend work
- Database changes needed
- API endpoints required

### Determine Scope
Based on the description, classify as:
- **Small** (< 1 day): Single component or endpoint
- **Medium** (1-3 days): Multiple components, some integration
- **Large** (3-5 days): Feature spanning multiple systems
- **Epic** (> 5 days): Needs to be split into multiple tasks

## Step 2: Dependency Discovery (MUST DO - per CLAUDE.md)

### Search for Existing Code
```bash
# Search for related components
grep -r "${keywords}" frontend/src/ --include="*.tsx" --include="*.ts"
grep -r "${keywords}" backend/ --include="*.py"

# Check for similar features
find . -name "*${related_term}*" -type f

# Look for existing patterns
grep -r "class.*${ComponentName}" frontend/src/
grep -r "def.*${function_name}" backend/
```

### What Already Exists
Check for:
- Existing components that can be extended
- Similar features to use as templates
- Utility functions available
- Database tables already created
- API endpoints that exist
- Services that can be reused

### Required Dependencies
Identify:
- NPM packages needed (check package.json)
- Python packages needed (check requirements.txt)
- Database migrations required
- Docker services needed
- External APIs or services

## Step 3: Complexity Analysis

### Technical Complexity Score
Rate each aspect 1-5:
- Frontend complexity: [1-5]
- Backend complexity: [1-5]
- Database complexity: [1-5]
- Integration complexity: [1-5]
- Testing complexity: [1-5]

**Total Score**: Sum of all scores
- 5-10: Simple task (1 day)
- 11-15: Medium task (2-3 days)
- 16-20: Complex task (3-5 days)
- 21-25: Epic - must split (> 5 days)

### Risk Assessment
- Data migration required? [HIGH risk]
- Breaking changes? [HIGH risk]
- New technology? [MEDIUM risk]
- Complex business logic? [MEDIUM risk]
- UI/UX changes? [LOW risk]

## Step 4: Task Splitting Logic

### When to Split
Split into multiple tasks if:
- Complexity score > 20
- Touches > 5 files in different modules
- Frontend + Backend + Database all needed
- Multiple user stories involved
- Can be delivered incrementally

### How to Split
Common splitting patterns:

#### Pattern 1: Layer-based (Vertical)
```
Parent Task: ${title}
├── TASK-XXX-backend: Backend API implementation
├── TASK-XXX-frontend: Frontend UI components
├── TASK-XXX-integration: Connect frontend to backend
└── TASK-XXX-testing: End-to-end testing
```

#### Pattern 2: Feature-based (Horizontal)
```
Parent Task: ${title}
├── TASK-XXX-core: Core functionality
├── TASK-XXX-ui: User interface
├── TASK-XXX-validation: Input validation & error handling
└── TASK-XXX-polish: Performance & UX improvements
```

#### Pattern 3: CRUD-based
```
Parent Task: ${title}
├── TASK-XXX-create: Create functionality
├── TASK-XXX-read: Display/list functionality
├── TASK-XXX-update: Edit functionality
└── TASK-XXX-delete: Delete functionality
```

## Step 5: Generate Task File(s)

### Single Task Template
```markdown
# TASK-${next_id}: ${title}

**Status**: BACKLOG
**Priority**: ${priority}
**Type**: ${type}
**Assigned**: Unassigned
**Created**: ${current_date}
**Updated**: ${current_date}
**Estimated Effort**: ${effort_estimate}

## Description
${description}

## Business Value
- ${business_value_1}
- ${business_value_2}
- ${business_value_3}

## Acceptance Criteria
- [ ] ${criterion_1}
- [ ] ${criterion_2}
- [ ] ${criterion_3}
- [ ] All tests pass
- [ ] No console errors
- [ ] Documentation updated

## Technical Approach

### Existing Resources to Reuse
${existing_resources_found}

### New Components Needed
${new_components_list}

### Dependencies
- Frontend: ${frontend_deps}
- Backend: ${backend_deps}
- Database: ${database_changes}

### Implementation Steps
1. ${step_1}
2. ${step_2}
3. ${step_3}

## Testing Requirements
- Unit tests for ${components}
- Integration tests for ${integrations}
- Manual testing of ${user_flows}

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| ${risk_1} | ${impact_1} | ${mitigation_1} |

## Related Tasks
- Dependencies: ${dependent_tasks}
- Related: ${related_tasks}
- Blocks: ${blocked_tasks}

## Notes
${additional_notes}
```

### Parent Task Template (for split tasks)
```markdown
# TASK-${parent_id}: ${title} [EPIC]

**Status**: BACKLOG
**Priority**: ${priority}
**Type**: EPIC
**Created**: ${current_date}
**Total Effort**: ${total_effort}

## Description
${description}

## Sub-tasks
- [ ] TASK-${child_1_id}: ${child_1_title} (${child_1_effort})
- [ ] TASK-${child_2_id}: ${child_2_title} (${child_2_effort})
- [ ] TASK-${child_3_id}: ${child_3_title} (${child_3_effort})

## Completion Criteria
All sub-tasks must be completed for this epic to be done.

## Business Value
${business_value}

## Dependencies Identified
${all_dependencies}
```

## Step 6: Task ID Generation

```bash
# Get next task ID
last_task=$(ls kanban/*/TASK-*.md 2>/dev/null | sed 's/.*TASK-//' | sed 's/-.*//' | sort -n | tail -1)
next_id=$((last_task + 1))
next_id=$(printf "%03d" $next_id)  # Format as 001, 002, etc.
```

## Step 7: Validation & Output

### Pre-creation Checks
- [ ] No duplicate task exists
- [ ] Dependencies are documented
- [ ] Effort estimate is realistic
- [ ] Acceptance criteria are clear
- [ ] Technical approach is sound

### Create Task File(s)
```bash
# For single task
echo "${task_content}" > "kanban/backlog/TASK-${next_id}-${slug_title}.md"

# For multiple tasks (epic)
echo "${parent_content}" > "kanban/backlog/TASK-${parent_id}-${slug_title}-epic.md"
echo "${child_1_content}" > "kanban/backlog/TASK-${child_1_id}-${slug_title}-backend.md"
echo "${child_2_content}" > "kanban/backlog/TASK-${child_2_id}-${slug_title}-frontend.md"
```

## Example Usage

### Simple Task
```
@create-task "Add dark mode toggle" "Add a toggle switch in settings to enable dark mode theme"
```
Result: Creates single TASK-004-add-dark-mode-toggle.md

### Complex Task (Auto-split)
```
@create-task "Implement real-time notifications" "Add WebSocket-based notifications with database persistence, UI indicators, and email fallback"
```
Result: Creates:
- TASK-004-notifications-epic.md (parent)
- TASK-005-notifications-backend.md
- TASK-006-notifications-frontend.md
- TASK-007-notifications-integration.md

## Decision Matrix for Splitting

| Criteria | Don't Split | Consider Split | Must Split |
|----------|------------|----------------|------------|
| Effort | < 2 days | 2-5 days | > 5 days |
| Files | < 5 files | 5-10 files | > 10 files |
| Systems | 1 system | 2 systems | 3+ systems |
| Dependencies | < 3 deps | 3-5 deps | > 5 deps |
| Risk | Low | Medium | High |
| Delivery | All at once | Some incremental | Must be incremental |

## Output Format

After task creation:
```
✅ Task Created Successfully
============================
Task ID: TASK-${id}
Title: ${title}
Type: ${type}
Location: kanban/backlog/TASK-${id}-${slug}.md
Estimated Effort: ${effort}

Dependencies Found:
- Reusable: ${reusable_components}
- Required: ${new_dependencies}

${if_split}
Sub-tasks Created:
- TASK-${id1}: ${title1}
- TASK-${id2}: ${title2}
${endif}

Next Steps:
1. Review task in backlog
2. Assign to developer
3. Run @start-task TASK-${id} when ready
```

## Important Rules
- ALWAYS check existing code first (CLAUDE.md rule)
- ALWAYS identify dependencies
- ALWAYS estimate realistically
- SPLIT when complexity > threshold
- REUSE over recreate
- DOCUMENT all findings