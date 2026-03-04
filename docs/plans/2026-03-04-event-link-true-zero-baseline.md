# Event Link True-Zero Baseline (2026-03-04)

## Branch / Workspace
- Worktree: `C:\Users\prekzursil\Desktop\workspace\worktrees\event-link-true-zero`
- Branch: `fix/true-zero-and-coverage-100`
- Base: `origin/main` at `5e2d2e9`

## Required Branch-Protection Contexts (`main`)
- `backend`
- `frontend`
- `Coverage 100 Gate`
- `Codecov Analytics`
- `Quality Zero Gate`
- `SonarCloud Code Analysis`
- `Codacy Static Code Analysis`
- `DeepScan`
- `Snyk Zero`
- `Sentry Zero`
- `Sonar Zero`
- `Codacy Zero`
- `DeepScan Zero`

Evidence command:
- `gh api repos/Prekzursil/event-link/branches/main/protection/required_status_checks`

## Code Scanning Open Alerts (`refs/heads/main`)
- Total open alerts: `105`
- CodeQL: `12`
- SonarCloud: `93`

Evidence command:
- `gh api "repos/Prekzursil/event-link/code-scanning/alerts?state=open&ref=refs/heads/main&per_page=100" --paginate`

## Sonar Open Issues (`main`)
- Sonar issues total: `522`

Evidence command:
- `GET https://sonarcloud.io/api/issues/search?componentKeys=Prekzursil_event-link&branch=main&resolved=false&ps=1`

## Latest Coverage Gate Failure Snapshot (`main` push run `22678078516`)
- Backend: `81.00%` (`3462/4274`) from `backend/coverage.xml`
- UI: `8.25%` (`158/1916`) from `ui/coverage/lcov.info`
- Combined: `58.48%` (`3620/6190`)

Evidence lines from run log:
- `backend coverage below 100%: 81.00% (3462/4274)`
- `ui coverage below 100%: 8.25% (158/1916)`
- `combined coverage below 100%: 58.48% (3620/6190)`

## Provider Zero-Gate Failure Snapshots (same main push wave)
- Codacy Zero (`run 22678078537`): open issues `409`
- Sonar Zero (`run 22678078449`): scan failed due missing `sonar.projectKey` / `sonar.organization`
- Snyk Zero (`run 22678078464`): open code issues `47` and result `fail`

Evidence lines from run logs:
- Codacy: `Open issues: 409`
- Sonar: `You must define ... sonar.projectKey, sonar.organization`
- Snyk: `Open issues: 47 [ 0 HIGH  38 MEDIUM  9 LOW ]`

## Notes
- This baseline is captured from remote `main` status before remediation on `fix/true-zero-and-coverage-100`.
- No local dirty state from older `event-link` branch is carried into this clean worktree.
