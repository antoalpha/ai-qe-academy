# Agno Release Manager Test Data Pack

This pack is designed for an Agno Framework case study where a memory-enabled Release Manager Agent analyzes release readiness using historical context, current release data, lessons learned, Jira defects, test execution, and security findings.

Files:
- historical_releases.csv: Past release outcomes and quality metrics.
- current_release.csv: Current release metadata and scope.
- lessons_learned.csv: Historical release lessons that an Agno agent can store as memory/knowledge.
- jira_data.csv: Current release defects.
- test_data.csv: Test execution results.
- security_data.csv: Security scan findings.

Suggested agent tasks:
1. Analyze current release readiness.
2. Compare current release risks with historical releases.
3. Apply lessons learned from previous NO-GO decisions.
4. Recommend GO / NO-GO.
5. Explain the decision with supporting evidence.
