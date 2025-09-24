---
name: review-task
description: Move task from in-progress to review with comprehensive code quality analysis
parameters:
  - name: task
    description: Task ID from kanban/in-progress folder (e.g., TASK-004)
    required: true
  - name: reviewer
    description: Person performing the review
    required: false
    default: "System Review"
---

# Code Review & Quality Check

Move task from in-progress to review with comprehensive quality analysis.

## Review Process Overview

1. **Locate task** in kanban/in-progress/${task}*.md
2. **Identify changes** using git diff
3. **Check SOLID principles** compliance
4. **Verify ACID compliance** for database operations
5. **Detect code duplication**
6. **Validate folder structure**
7. **Generate review report**
8. **Move to review** with findings

## Comprehensive Review Steps

### Step 1: Identify Changes Made

```bash
# Get list of changed files for this task
git diff --name-only dev origin/dev

# Get detailed changes
git diff dev origin/dev

# Check commits related to task
git log --grep="${task}" --oneline

# Get full diff for task-related commits
git show --stat $(git log --grep="${task}" --format="%H")
```

### Step 2: SOLID Principles Validation

#### Single Responsibility Check
- Each class/function should have ONE reason to change
- Look for classes doing multiple unrelated things
- Check for functions > 20 lines (violates focus principle)

```python
# BAD: Multiple responsibilities
class ClientHandler:
    def extract_data(self): ...
    def save_to_db(self): ...
    def send_email(self): ...
    def generate_pdf(self): ...

# GOOD: Single responsibility
class ClientExtractor:
    def extract_data(self): ...

class ClientRepository:
    def save(self): ...
```

#### Open/Closed Principle
- Check if existing code was modified vs extended
- Look for hardcoded conditions that should be polymorphic

#### Liskov Substitution
- Verify derived classes can replace base classes
- Check for broken inheritance contracts

#### Interface Segregation
- No fat interfaces
- Clients shouldn't depend on methods they don't use

#### Dependency Inversion
- High-level modules shouldn't depend on low-level modules
- Both should depend on abstractions

### Step 3: ACID Compliance Check (Database Operations)

#### Atomicity
- All database operations in transactions
- Proper rollback on failure

```python
# Check for transaction usage
async with db.transaction() as tx:
    # All operations here are atomic
```

#### Consistency
- Data integrity maintained
- Constraints validated

#### Isolation
- Concurrent operations handled correctly
- Proper locking mechanisms

#### Durability
- Changes persisted correctly
- Proper commit handling

### Step 4: Code Duplication Detection

```bash
# Search for duplicate patterns
# Check for similar function names
grep -r "function_name" --include="*.py" --include="*.tsx" .

# Look for duplicate logic patterns
# Common duplication areas:
- Data extraction patterns
- API endpoint handlers
- React component structures
- Database queries
- Utility functions
```

#### Duplication Report Format:
```markdown
## Duplication Found
- **File A**: path/to/fileA.py:45-60
- **File B**: path/to/fileB.py:120-135
- **Similarity**: 85%
- **Recommendation**: Extract to shared utility
```

### Step 5: Folder Structure Validation

#### Frontend Structure Check
```
frontend/src/
├── components/       # UI components only
│   ├── meeting/     # Feature-specific
│   ├── portfolio/   # Feature-specific
│   └── shared/      # Reusable components
├── services/        # API calls and business logic
├── utils/           # Helper functions
├── hooks/           # Custom React hooks
├── types/           # TypeScript definitions
└── constants/       # App constants
```

#### Backend Structure Check
```
backend/
├── agents/          # Service agents
│   ├── data-ingestion/
│   └── ai-services/
├── shared/          # Shared resources
│   ├── models/     # Database models
│   ├── utils/      # Utilities
│   └── migrations/ # DB migrations
└── gateway/        # API gateway
```

#### Violations to Check:
- Business logic in components (should be in services)
- UI logic in services (should be in components)
- Duplicate utilities (should be in shared)
- Hardcoded values (should be in constants)
- Mixed concerns in files

### Step 6: Additional Quality Checks

#### Import Analysis
```bash
# Check for unused imports
grep -r "^import\|^from" --include="*.py" --include="*.tsx"

# Check for circular dependencies
# Look for A imports B, B imports A patterns
```

#### Error Handling
- All API calls have try/catch
- Proper error messages
- Loading states implemented
- User feedback on errors

#### Type Safety (TypeScript)
- No `any` types without justification
- Interfaces properly defined
- Props typed correctly

#### Performance
- No unnecessary re-renders (React)
- Proper memoization used
- Database queries optimized
- Indexes used appropriately

### Step 7: Generate Review Report

Check where to save the report:
```bash
# Determine report location based on review decision
if [ "$review_decision" = "APPROVED" ]; then
    report_location="kanban/review/${task}-code-review-report.md"
else
    report_location="kanban/in-progress/${task}-review-notes.md"
fi

# Check if report already exists
if [ -f "$report_location" ]; then
    echo "Report already exists at: $report_location"
    echo "Updating existing report..."
fi
```

Generate the report:
```markdown
# Code Review Report for ${task}

**Date**: ${current_date}
**Reviewer**: ${reviewer}
**Task**: ${task}
**Status**: PENDING REVIEW

## Changes Summary
- Files Modified: [count]
- Lines Added: [count]
- Lines Removed: [count]
- Components Affected: [list]

## SOLID Principles Compliance
### ✅ Passed
- [Principle]: [Evidence]

### ❌ Violations Found
- [Principle]: [File:Line] - [Description]
- **Recommendation**: [How to fix]

## ACID Compliance (Database Operations)
### ✅ Passed
- All operations use transactions
- Proper rollback handling

### ⚠️ Warnings
- [Issue]: [Description]

## Code Duplication Analysis
### ❌ Duplications Found
- [Description of duplicate code]
- **Files**: [List of files]
- **Recommendation**: Extract to [suggested location]

### ✅ No Duplications
- Code properly reuses existing components

## Folder Structure Compliance
### ✅ Correct Placement
- Components in proper directories
- Services separated from UI

### ❌ Violations
- [File]: Should be in [correct location]
- **Reason**: [Why it's wrong]

## Quality Metrics
- **Complexity**: [HIGH/MEDIUM/LOW]
- **Maintainability**: [Score/10]
- **Test Coverage**: [percentage]
- **Documentation**: [COMPLETE/PARTIAL/MISSING]

## Critical Issues (Must Fix)
1. [Issue description]
   - Location: [file:line]
   - Impact: [description]
   - Fix: [recommendation]

## Recommendations (Should Fix)
1. [Improvement suggestion]
   - Current: [current state]
   - Suggested: [better approach]

## Good Practices Observed
- [What was done well]

## Review Decision
[ ] APPROVED - Ready for testing
[ ] NEEDS CHANGES - Address critical issues
[ ] REJECTED - Major refactoring required

## Next Steps
1. [Action item 1]
2. [Action item 2]
```

### Step 8: Update Task and Move

Update task file with review findings:

```markdown
## Review Summary (${date})
**Reviewer**: ${reviewer}
**Decision**: [APPROVED/NEEDS CHANGES/REJECTED]
**Key Findings**:
- [Finding 1]
- [Finding 2]

[Full review report attached above]
```

Move to appropriate folder:
```bash
# Check if review folder exists (it should already exist)
if [ ! -d "kanban/review" ]; then
    echo "ERROR: kanban/review directory doesn't exist"
    echo "Project structure might be corrupted"
    exit 1
fi

# Check if review report already exists
if [ -f "kanban/review/${task}-code-review-report.md" ]; then
    echo "WARNING: Review report already exists for ${task}"
    echo "Consider updating existing report instead of creating new one"
    # Optionally append to existing report or create versioned report
fi

# If approved
if [ "$review_decision" = "APPROVED" ]; then
    mv kanban/in-progress/${task}*.md kanban/review/
    echo "Task moved to review folder"
else
    echo "Task remains in in-progress - needs changes"
    # Keep in in-progress with review notes attached
fi
```

## Automated Checks Commands

```bash
# Python code quality
flake8 backend/ --count --statistics
black backend/ --check
mypy backend/

# TypeScript quality  
cd frontend && npm run lint
cd frontend && npm run typecheck

# Complexity analysis
radon cc backend/ -s
```

## Review Checklist

Before approving:
- ✅ No code duplication
- ✅ SOLID principles followed
- ✅ ACID compliance for DB operations
- ✅ Proper error handling
- ✅ Loading states implemented
- ✅ TypeScript types defined
- ✅ No hardcoded values
- ✅ Proper folder structure
- ✅ Clean imports
- ✅ No console.logs in production code
- ✅ Comments explain "why" not "what"
- ✅ Functions < 20 lines
- ✅ Classes have single responsibility
- ✅ Git commits follow standards

## Common Anti-patterns to Flag

1. **God Objects**: Classes doing everything
2. **Copy-Paste Programming**: Duplicate code blocks
3. **Magic Numbers**: Hardcoded values without context
4. **Callback Hell**: Deeply nested callbacks
5. **Premature Optimization**: Complex code without need
6. **Dead Code**: Unused functions/imports
7. **Long Methods**: Functions doing too much
8. **Feature Envy**: Class using another class's data excessively
9. **Inappropriate Intimacy**: Classes knowing too much about each other
10. **Shotgun Surgery**: Change requires edits in many places

## Output

Provide:
1. Review report with all findings
2. Clear pass/fail decision
3. Specific action items if changes needed
4. Updated task file in review/ or ongoing/
5. Recommendations for improvement