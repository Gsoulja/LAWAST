---
name: analyze
description: Perform deep code analysis including dependencies, impact, and security
parameters:
  - name: target
    description: File, folder, or component to analyze
    required: false
    default: "."
  - name: mode
    description: Analysis mode (quick/deep/impact/libs/solid/clean/perf/sec/deps)
    required: false
    default: "deep"
---

# Code Analysis

Perform comprehensive analysis of ${target} in ${mode} mode.

## Analysis Scope

Based on the mode "${mode}", focus on:
- **quick**: Basic dependency check and immediate impacts (2-minute analysis)
- **deep**: Full recursive analysis with all dependencies traced, performance profiling, and security scanning
- **impact**: What-if analysis for changes and ripple effects
- **libs**: Library review, redundancy check, and license compliance
- **solid**: SOLID principle compliance check
- **clean**: Clean code practices analysis
- **perf**: Performance analysis only
- **sec**: Security analysis only
- **deps**: Dependencies analysis only

## Analysis Report Structure

📊 COMPREHENSIVE CODE ANALYSIS REPORT
=====================================

Target: ${target}
Mode: ${mode}
Date: [current date]

### 1️⃣ DEPENDENCY ANALYSIS
- Direct Dependencies with versions and usage
- Peer Dependencies requirements
- Dev Dependencies used in code
- Dependency Health (outdated, security issues, size impact)

### 2️⃣ IMPACT ASSESSMENT
- Files Affected and how
- Components Impacted with severity level
- API Endpoints Affected
- Database Impact (schema changes, migration needs, data loss risk)

### 3️⃣ LIBRARY USAGE ANALYSIS
- Libraries Used (purpose, usage, alternatives, bundle size, license)
- Redundant Libraries that can be replaced
- Missing Libraries suggestions

### 4️⃣ PERFORMANCE IMPACT
- Bundle Size Changes
- Load Time Impact
- Memory Usage changes
- Render Performance metrics

### 5️⃣ SECURITY ANALYSIS
- Security Issues by severity
- Vulnerable Dependencies with CVE IDs
- Security Best Practices checklist

### 6️⃣ BREAKING CHANGES
- API Contract Changes
- Type/Interface Changes
- Component Props Changes
- Database Schema Changes

### 7️⃣ RISK ASSESSMENT
- Risk Level: CRITICAL/HIGH/MEDIUM/LOW
- Risks Identified with mitigation strategies

### 8️⃣ RECOMMENDATIONS
- Must Do actions
- Should Do improvements
- Consider optimizations

### 9️⃣ TESTING REQUIREMENTS
- Unit Tests Needed
- Integration Tests required
- E2E Test scenarios

### 🔟 DEPLOYMENT CONSIDERATIONS
- Environment Variables changes
- Docker service changes
- CI/CD Pipeline updates
- Rollback Plan

## Summary

Provide clear metrics:
- Total Files Affected
- Risk Level
- Estimated Work (hours/days)
- Deployment Complexity

VERDICT: [SAFE TO PROCEED / PROCEED WITH CAUTION / HIGH RISK / BLOCK]

Always provide actionable insights, specific impacts, and clear recommendations.