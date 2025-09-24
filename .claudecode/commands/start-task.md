---
name: start-task
description: Move task from backlog to in-progress with full dependency and impact analysis
parameters:
  - name: task
    description: Task ID from kanban/backlog folder (e.g., TASK-004)
    required: true
  - name: assignee
    description: Person assigned to the task
    required: false
    default: "Unassigned"
---

# Start Task with Impact Analysis

Move task from backlog to in-progress with comprehensive analysis.

## Process Overview

1. **Locate and validate task** in kanban/backlog/${task}*.md
2. **Perform dependency analysis** to understand what exists
3. **Assess impact** on existing components
4. **Add technical information** to the ticket
5. **Move to in-progress** with updated status

## Analysis Steps

### Step 1: Task Validation
- Read kanban/backlog/${task}*.md
- Extract requirements and acceptance criteria
- Identify technical approach sections

### Step 2: Dependency Discovery (MUST DO - per CLAUDE.md)
**ALWAYS check existing code before starting:**

#### A. Search for Related Components
```bash
# Search for existing similar functionality
grep -r "component_name" frontend/src/
grep -r "endpoint_name" backend/
grep -r "table_name" backend/shared/migrations/
```

#### B. Identify What Already Exists
- Components that can be reused
- Services already implemented
- Database tables and columns available
- API endpoints that exist
- Utility functions to leverage

#### C. Check Dependencies
- Package.json dependencies (frontend)
- Requirements.txt dependencies (backend)
- Database migrations already applied
- Docker services required

### Step 3: Impact Analysis (MUST DO - per CLAUDE.md)

#### A. Components Affected
- List all files that will be modified
- Identify components that import these files
- Check for breaking changes

#### B. API Impact
- Endpoints that need modification
- Request/response contract changes
- WebSocket message format changes

#### C. Database Impact
- Schema changes required
- Migration dependencies
- Index performance implications
- ACID transaction requirements

#### D. Frontend Impact
- Components to update
- State management changes
- Type definitions to modify
- CSS classes needed

### Step 4: Technical Information Update

Add the following sections to the task:

```markdown
## Technical Analysis (Auto-generated ${date})

### Existing Resources Found
- Components: [list reusable components found]
- Services: [list existing services to use]
- APIs: [list existing endpoints]
- Database: [list relevant tables/columns]
- Utilities: [list helper functions available]

### Dependencies Required
- Frontend packages: [from package.json]
- Backend packages: [from requirements.txt]
- Database migrations: [required migrations]
- Docker services: [required services]

### Impact Assessment
#### Files to Modify
- [file path]: [reason for change]

#### Components Affected
- [component]: [impact level: HIGH/MEDIUM/LOW]

#### API Changes
- [endpoint]: [change description]

#### Database Changes
- [table]: [change description]

### Implementation Checklist
Based on CLAUDE.md principles:
- [ ] Reuse existing [component] instead of creating new
- [ ] Extend [service] rather than duplicate
- [ ] Follow SOLID principles
- [ ] Maintain backwards compatibility
- [ ] Add proper error handling
- [ ] Include loading states
- [ ] Write self-documenting code

### Risk Analysis
- **Risk Level**: [HIGH/MEDIUM/LOW]
- **Main Risks**: 
  - [risk 1]: [mitigation strategy]
  - [risk 2]: [mitigation strategy]

### Estimated Effort
- Original: [from task]
- Adjusted: [based on analysis]
- Reason: [why different if changed]
```

### Step 5: Update Task Status

```markdown
**Status**: IN-PROGRESS
**Assigned**: ${assignee}
**Started**: ${current_date}
**Analysis Completed**: ${current_date}
```

### Step 6: Move File

```bash
# Check if in-progress directory exists (it should already exist)
if [ ! -d "kanban/in-progress" ]; then
    echo "ERROR: kanban/in-progress directory doesn't exist"
    echo "Project structure might be corrupted"
    exit 1
fi

# Move task file
mv kanban/backlog/${task}*.md kanban/in-progress/

# Verify move
ls kanban/in-progress/${task}*.md
```

## Validation Checklist

Before moving to in-progress, ensure:
- ✅ All existing code has been searched (CLAUDE.md Rule 1)
- ✅ Impact analysis is complete (CLAUDE.md Rule 2)
- ✅ Reusable components identified
- ✅ Dependencies documented
- ✅ Risks assessed and mitigations planned
- ✅ Technical details added to ticket
- ✅ Implementation checklist created

## Common Patterns to Check

### Frontend
- Check components in `/frontend/src/components/`
- Review services in `/frontend/src/services/`
- Look for similar patterns in existing code
- Verify Tailwind classes exist

### Backend
- Check existing endpoints in `/backend/agents/`
- Review database models and migrations
- Look for similar extraction patterns
- Verify Redis/WebSocket usage

### Database
- Check existing JSONB columns for similar data
- Review indexes for performance
- Look for similar table structures
- Verify FK constraints

## Output Format

After analysis, provide:
1. Summary of what was found
2. List of reusable components
3. Impact assessment
4. Updated task file in in-progress/
5. Clear implementation path

## Important Rules (from CLAUDE.md)
- NEVER create duplicate components
- ALWAYS check what exists first
- VALIDATE all impacts before starting
- FOLLOW existing patterns
- REUSE over recreate