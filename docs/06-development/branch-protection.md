# Git Branch Protection Rules

## Overview

Branch protection rules help maintain code quality and prevent accidental changes to important branches.

## Setting Up Branch Protection (GitHub)

### 1. Navigate to Settings

1. Go to your repository on GitHub
2. Click on "Settings" tab
3. Select "Branches" from the left sidebar

### 2. Add Branch Protection Rule

Click "Add rule" and configure:

#### Branch name pattern
- `main` - Protects the main branch
- `release/*` - Protects all release branches
- `production` - Protects production branch

### 3. Protection Settings

#### Required Reviews
- ✅ Require pull request reviews before merging
- Number of required reviews: 2
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from CODEOWNERS
- ✅ Restrict who can dismiss pull request reviews

#### Status Checks
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- Required status checks:
  - `continuous-integration/travis-ci`
  - `test-suite`
  - `lint`
  - `type-check`
  - `security-scan`

#### Conversation Resolution
- ✅ Require conversation resolution before merging

#### Signed Commits
- ✅ Require signed commits (optional but recommended)

#### Linear History
- ✅ Require linear history (prevents merge commits)

#### Include Administrators
- ✅ Include administrators (recommended for consistency)

#### Restrict Push Access
- ✅ Restrict who can push to matching branches
- Allowed users/teams:
  - `maintainers` team
  - `release-managers` team

#### Force Push
- ❌ Allow force pushes (should be disabled)
- ❌ Allow deletions (should be disabled)

### 4. Additional Rules

#### Development Branch
```
Branch pattern: develop
- Require 1 review
- Require status checks
- Allow force pushes from maintainers only
```

#### Feature Branches
```
Branch pattern: feature/*
- No restrictions (developers can work freely)
- Encourage PR workflow
```

## Setting Up Branch Protection (GitLab)

### 1. Navigate to Settings

1. Go to Project Settings
2. Select "Repository"
3. Expand "Protected branches"

### 2. Protect a Branch

- Branch: `main`
- Allowed to merge: Developers + Maintainers
- Allowed to push: No one
- Require approval from: 2 users

## Local Git Configuration

### Pre-push Hook

Create `.git/hooks/pre-push`:

```bash
#!/bin/bash

protected_branch='main'
current_branch=$(git symbolic-ref HEAD | sed -e 's,.*/\(.*\),\1,')

if [ $protected_branch = $current_branch ]; then
    echo "Direct push to $protected_branch branch is not allowed."
    echo "Please create a pull request."
    exit 1
fi

exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-push
```

### Commit Message Hook

Create `.git/hooks/commit-msg`:

```bash
#!/bin/bash

# Check commit message format
commit_regex='^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .{1,50}'

if ! grep -qE "$commit_regex" "$1"; then
    echo "Commit message does not follow conventional format!"
    echo "Format: <type>(<scope>): <subject>"
    echo "Example: feat(auth): add biometric login support"
    exit 1
fi
```

## Branch Naming Conventions

### Main Branches
- `main` - Production-ready code
- `develop` - Integration branch for features
- `staging` - Pre-production testing

### Supporting Branches
- `feature/` - New features (e.g., `feature/biometric-auth`)
- `bugfix/` - Bug fixes (e.g., `bugfix/login-error`)
- `hotfix/` - Urgent production fixes
- `release/` - Release preparation (e.g., `release/1.2.0`)
- `chore/` - Maintenance tasks

## Pull Request Process

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes and Commit
```bash
git add .
git commit -m "feat(module): add new feature"
```

### 3. Push to Remote
```bash
git push -u origin feature/your-feature-name
```

### 4. Create Pull Request

#### PR Title Format
```
<type>(<scope>): <short description>
```

#### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings
```

## Enforcement Automation

### GitHub Actions Workflow

Create `.github/workflows/pr-checks.yml`:

```yaml
name: PR Checks

on:
  pull_request:
    types: [opened, edited, synchronize]

jobs:
  check-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Check PR Title
        uses: deepakputhraya/action-pr-title@master
        with:
          regex: '^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .{1,50}'
          
      - name: Check Branch Name
        run: |
          branch=${GITHUB_HEAD_REF}
          if [[ ! "$branch" =~ ^(feature|bugfix|hotfix|release|chore)/.+ ]]; then
            echo "Branch name does not follow naming convention"
            exit 1
          fi
```

## Bypass for Emergencies

For critical hotfixes:

1. Create hotfix branch from main
2. Requires only 1 review
3. Can bypass some status checks
4. Must be merged back to develop

```bash
# Create hotfix
git checkout -b hotfix/critical-security-fix main

# After fix and approval
git checkout main
git merge --no-ff hotfix/critical-security-fix
git checkout develop
git merge --no-ff hotfix/critical-security-fix
```

## Monitoring and Compliance

- Regular audits of bypass events
- Monthly review of protection rules
- Automated reports on rule violations
- Training for new team members