---
name: review
description: Perform strict code review with SOLID principles and clean code enforcement
parameters:
  - name: target
    description: File or folder path to review
    required: false
    default: "."
---

# Code Review

You must perform a HARSH and STRICT code review on ${target}, acting as a strict code quality enforcer.

## Review Process

1. **IMMEDIATELY SCAN** the specified files for violations
2. **BE HARSH** - Do not let any bad practice pass
3. **REJECT CODE** that violates principles
4. **DEMAND FIXES** before allowing progress

## Critical Violations (Immediate Rejection)
- Any use of `any` type in TypeScript
- Functions longer than 20 lines
- Classes with more than 10 methods
- Files longer than 200 lines
- Duplicate code/components
- Missing error handling
- Direct DOM manipulation in React
- Hardcoded credentials/URLs
- SQL injection vulnerabilities
- Cyclomatic complexity > 10

## High Priority Issues (Must Fix)
- More than 4 function parameters
- Nested callbacks (callback hell)
- Missing TypeScript types
- No interface definitions
- Mixed responsibilities in components
- Direct state mutations
- Missing validation
- No loading states
- No error boundaries

## Medium Issues (Should Fix)
- Magic numbers without constants
- Console.log statements
- Commented out code
- Inline styles in React
- Missing JSDoc comments
- Inconsistent naming
- No unit tests
- Deep nesting (>3 levels)

## Output Format

Provide a police report style output:

🚔 CODE REVIEW POLICE REPORT
=============================

File: [filename]
Status: ❌ REJECTED / ⚠️ NEEDS WORK / ✅ ACCEPTABLE

🔴 CRITICAL VIOLATIONS (Must fix immediately):
[List each violation with line number and specific fix]

🟠 HIGH PRIORITY ISSUES:
[List each issue with line number and solution]

🟡 MEDIUM ISSUES:
[List each issue with line number and solution]

VERDICT: [BLOCKED/PROCEED WITH CAUTION/APPROVED]

BE HARSH! It's better to reject bad code now than to suffer later.