---
name: merge-to-uat
description: Merge dev branch into UAT for testing with validation checks
parameters:
  - name: tasks
    description: Comma-separated list of task IDs being merged (e.g., TASK-001,TASK-002)
    required: true
  - name: testing_notes
    description: Specific testing instructions or focus areas
    required: false
    default: ""
---

# Merge to UAT for Testing

Safely merge dev branch into UAT with comprehensive validation.

## Pre-Merge Checklist

1. **Verify all tasks are in done/**
2. **Ensure all commits are made**
3. **Check no work in progress**
4. **Validate code quality**
5. **Document testing requirements**

## Merge Process

### Step 1: Pre-Flight Checks

```bash
# Current branch check
git branch --show-current

# Ensure we're on dev
if [ "$(git branch --show-current)" != "dev" ]; then
    echo "ERROR: Not on dev branch!"
    git checkout dev
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Uncommitted changes found!"
    echo "Please commit or stash changes first"
    git status
    exit 1
fi
```

### Step 2: Validate Tasks

For each task in ${tasks}:
```bash
# Verify task is completed
ls kanban/done/${task}*.md

# If not found, check if still in progress
ls kanban/in-progress/${task}*.md 2>/dev/null && echo "WARNING: Task ${task} still in progress!"
ls kanban/review/${task}*.md 2>/dev/null && echo "WARNING: Task ${task} still in review!"
```

### Step 3: Code Quality Verification

```bash
# Python linting (if applicable)
echo "Running Python code quality checks..."
flake8 backend/ --count --select=E9,F63,F7,F82 --show-source --statistics || true

# TypeScript checks (if applicable)
echo "Running TypeScript checks..."
cd frontend && npm run typecheck || true
cd ..

# Check for console.logs in production code
echo "Checking for console.logs..."
grep -r "console.log" frontend/src --exclude-dir=node_modules --exclude="*.test.*" | head -5

# Check for TODO comments
echo "Checking for TODO comments..."
grep -r "TODO\|FIXME\|XXX" --exclude-dir=node_modules --exclude-dir=.git . | head -5
```

### Step 4: Update Dev Branch

```bash
# Pull latest changes
git pull origin dev

# Show recent commits
echo "Recent commits on dev:"
git log --oneline -10
```

### Step 5: Switch to UAT Branch

```bash
# Switch to UAT
git checkout uat

# Pull latest UAT changes
git pull origin uat 2>/dev/null || echo "No remote UAT branch yet"

# Show current UAT status
echo "Current UAT branch status:"
git log --oneline -5
```

### Step 6: Merge Dev into UAT

```bash
# Perform the merge
echo "Merging dev into uat..."
git merge dev --no-ff -m "Merge dev into UAT: ${tasks}

Testing Required:
- Tasks: ${tasks}
${testing_notes}

This merge includes all completed features from dev branch.
Ready for User Acceptance Testing."

# Check merge status
if [ $? -eq 0 ]; then
    echo "✅ Merge successful!"
else
    echo "❌ Merge conflicts detected!"
    echo "Please resolve conflicts manually"
    git status
    exit 1
fi
```

### Step 7: Generate Testing Checklist

Create testing documentation:

```markdown
# UAT Testing Checklist
**Date**: ${current_date}
**Merged Tasks**: ${tasks}
**Branch**: uat
**Merge Commit**: ${merge_commit_hash}

## Features to Test

### Based on Tasks:
```

For each task in ${tasks}:
- Read kanban/done/${task}*.md
- Extract acceptance criteria
- Generate test cases

```markdown
### ${task}: [Task Title]
**Feature**: [Description]
**Test Cases**:
- [ ] [Acceptance criterion 1]
- [ ] [Acceptance criterion 2]
- [ ] [Edge case 1]
- [ ] [Error handling]
```

### Step 8: Testing Requirements Document

```markdown
## Testing Scope

### Functional Testing
- [ ] All new features work as expected
- [ ] No regression in existing features
- [ ] Error messages display correctly
- [ ] Loading states work properly

### Integration Testing  
- [ ] Frontend-Backend communication
- [ ] Database operations (ACID compliance)
- [ ] WebSocket connections (if applicable)
- [ ] File upload/download

### User Experience Testing
- [ ] UI displays correctly
- [ ] Responsive design works
- [ ] Navigation flows are intuitive
- [ ] Performance is acceptable

### Security Testing
- [ ] Authentication works
- [ ] Authorization enforced
- [ ] No sensitive data exposed
- [ ] Input validation works

### Specific Areas (${testing_notes})
${testing_notes_expanded}

## Test Data Requirements
- Client test data
- Sample documents
- Test user accounts

## Environment
- URL: [UAT environment URL]
- Test Users: [List of test accounts]
- Test Data: [Location of test data]

## Regression Testing
Features that must still work:
- [ ] Existing feature 1
- [ ] Existing feature 2
- [ ] Core functionality

## Sign-off Criteria
- [ ] All test cases pass
- [ ] No critical bugs
- [ ] Performance acceptable
- [ ] Security validated
- [ ] User experience smooth
```

### Step 9: Push UAT Branch

```bash
# Push to remote
echo "Pushing UAT branch to remote..."
git push origin uat

if [ $? -eq 0 ]; then
    echo "✅ UAT branch pushed successfully!"
else
    echo "Setting upstream and pushing..."
    git push -u origin uat
fi

# Show final status
echo "UAT branch status:"
git log --oneline -3
```

### Step 10: Post-Merge Tasks

```bash
# Switch back to dev for continued development
git checkout dev

# Create a UAT testing tracking file
mkdir -p kanban/testing
cat > kanban/testing/UAT-$(date +%Y%m%d)-${tasks}.md << EOF
# UAT Testing Session

**Date**: $(date +%Y-%m-%d)
**Tasks**: ${tasks}
**Status**: PENDING
**Tester**: [Assigned]

## Test Results
- [ ] Functional tests
- [ ] Integration tests  
- [ ] User experience tests
- [ ] Security tests

## Issues Found
1. [Issue description] - Severity: [HIGH/MEDIUM/LOW]

## Approval
- [ ] Approved for production
- [ ] Needs fixes (return to dev)
EOF

echo "✅ UAT testing file created: kanban/testing/UAT-$(date +%Y%m%d)-${tasks}.md"
```

## Important Validations

### Before Merge
- ✅ All tasks in done/
- ✅ No uncommitted changes
- ✅ Code quality checks pass
- ✅ No console.logs
- ✅ No TODO comments

### During Merge
- ✅ No merge conflicts
- ✅ Merge commit created
- ✅ Proper merge message

### After Merge
- ✅ UAT branch updated
- ✅ Testing checklist created
- ✅ Pushed to remote
- ✅ Back on dev branch

## Rollback Plan

If issues found during UAT:

```bash
# On UAT branch
git checkout uat

# Revert the merge
git revert -m 1 HEAD

# Push the revert
git push origin uat

# Return to dev to fix issues
git checkout dev
```

## Success Criteria

The merge is successful when:
1. All code merged without conflicts
2. UAT branch builds successfully
3. Testing checklist generated
4. Remote UAT branch updated
5. Team notified for testing

## Output Summary

```
==========================================
UAT MERGE COMPLETED SUCCESSFULLY
==========================================
Tasks Merged: ${tasks}
Merge Commit: ${commit_hash}
Testing Doc: kanban/testing/UAT-${date}-${tasks}.md

Next Steps:
1. Deploy UAT branch to test environment
2. Execute testing checklist
3. Report issues in testing doc
4. If approved, merge UAT → main
==========================================
```

## Common Issues & Solutions

### Merge Conflicts
- Resolve in favor of most recent tested code
- Document conflict resolution
- Re-test affected areas

### Failed Quality Checks
- Fix issues in dev branch first
- Create new commit
- Retry merge

### Missing Tasks
- Ensure all related tasks are in done/
- Complete any dependent tasks
- Update task references