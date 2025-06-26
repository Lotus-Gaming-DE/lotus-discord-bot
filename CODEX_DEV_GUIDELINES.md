# Codex Development Guidelines

These rules apply across all repositories where Codex is the sole developer.
All configuration, implementation, testing, and documentation must be automated and handled entirely through GitHub.
No local installations or manual steps are allowed. All deployments are handled via Railway.

---

## 🧩 Project Structure & File Conventions

Use this layout unless another language or framework makes it impractical:

```
src/<project_name>/      # main application code
tests/                   # test suite
.github/                 # workflows, dependabot
data/                    # ignored by git
logs/                    # ignored by git
scripts/                 # CLI tools (Python, argparse, documented)
LICENSE                  # must be present
README.md                # must document: overview, setup, usage, tests, deployment
CHANGELOG.md             # required, "Keep a Changelog" format
requirements.txt         # required if Python is used
requirements-dev.txt     # required if Python is used
.pre-commit-config.yaml  # required if Python is used
.env.example             # required if environment variables are used
.gitignore               # required (must exclude logs/, data/, .env, __pycache__, *.pyc)
```

### 🔧 CLI Scripts in `scripts/`

All CLI tools must:
- be written in Python using `argparse`
- contain a `main()` function
- support `--help`
- include a docstring explaining purpose and arguments
- be executable via `python scripts/<name>.py`
- be referenced in `README.md` under "Utility Scripts"

---

## 🚦 CI/CD & Automation

All automation must run fully via GitHub Actions:

- Trigger on: `push` and `pull_request`
- Must execute unattended without local setup
- Cache dependencies and pre-commit hooks
- Stream Railway logs:
  ```
  railway logs --follow > logs/latest_railway.log
  ```
- Artifacts (e.g. logs, SBOMs) must be saved under `logs/`

### Railway Logs

Include `.github/workflows/railway_logs.yml`:
- Install CLI: `npm install -g railway`
- Authenticate using `RAILWAY_TOKEN`
- Upload latest logs using `actions/upload-artifact@v4`
- Must support `workflow_dispatch`

### SBOM (Software Bill of Materials)

For **Python** projects:
```yaml
- name: Install CycloneDX Python SBOM Tool
  run: |
    python -m pip install cyclonedx-bom
    echo "$HOME/.local/bin" >> $GITHUB_PATH
- name: Generate SBOM
  run: cyclonedx-py requirements -i requirements.txt -o sbom.xml
```

> Alternative fallback (module-based):
> `python -m cyclonedx_py requirements -i requirements.txt -o sbom.xml`

For **Node.js** projects:
```yaml
- name: Install CycloneDX SBOM Tool
  run: npm install -g @cyclonedx/cyclonedx-npm
- name: Generate SBOM
  run: cyclonedx-npm --output-file sbom.json
```

In both cases:
```yaml
- uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.*
```

> Use `pip-audit` for quick vulnerability scans; use `cyclonedx-py` for full SBOM generation.
> Do **not** use `cyclonedx-bom` CLI alias directly, as it may be deprecated or unavailable in GitHub environments.

### Snyk (Vulnerability Scanning)

```yaml
- name: Install Snyk CLI
  run: npm install -g snyk
```

Then:
```yaml
- name: Run Snyk Test
  env:
    SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
  if: ${{ env.SNYK_TOKEN != '' && (github.event_name != 'pull_request' || github.event.pull_request.head.repo.fork == false) }}
  run: snyk test
```

⚠️ Never use `secrets.SNYK_TOKEN` directly inside an `if:` block.

---

## 🧪 Testing & Coverage

- All code must be covered with **unit and integration tests**
- Use `pytest --cov=.` for Python
- Tests must clean up their data (e.g., mocks, temp files, DB resets)

For async code:
- Use `@pytest.mark.asyncio(mode="auto")`
- Clean up with `cog_unload()` and `shutdown_asyncgens()`
- Use `pytest-timeout` to detect timeouts

CI must enforce:
- 100% execution of test suite
- 90% minimum coverage threshold

---

## 🧼 Linting & Code Style

All code must follow PEP 8 and use automated formatting.

Required `pre-commit` hooks:

```yaml
repos:
  - repo: https://github.com/psf/black
    hooks: [{ id: black }]
  - repo: https://github.com/pycqa/flake8
    hooks: [{ id: flake8 }]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{ id: ruff }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
  - repo: https://github.com/pypa/pip-audit
    hooks:
      - id: pip-audit
        additional_dependencies: ["pip-audit[cyclonedx]", "cyclonedx-bom"]
        args: ["-r", "requirements.txt", "--format", "columns"]
```

CI must run:
```bash
pre-commit run --all-files
```

Reject any commit that fails linting.

---

## 🔐 Security

- Use Snyk for all dependency scans
- Use `pip-audit` for Python in pre-commit
- Never commit tokens, secrets, or credentials
- Always use `.env.example` to document all environment variables

### `.env.example` Format

- Must list **every** env var used in the codebase
- If there are fixed options, name and describe them
  - e.g., `DEBUG`, `INFO`, `ERROR` for logging
- Include a placeholder value or comment
- Group by area (e.g. "Discord", "Database")

---

## 🔄 Dependency Management

Include `.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

- Enable GitHub security alerts
- Automatically accept `patch` and `minor` updates that pass CI
- Hold all `major` updates for manual review
- Commit lockfiles and verify their content
- Validate `requirements.txt` consistency by regenerating from `requirements.in` and diffing via CI

⚠️ **Codex must never use `automerge` or `automerge-type` inside `dependabot.yml`**, as these fields are invalid and will break the workflow.
Auto-merge behavior must be configured via branch protection or GitHub Actions.

### Optional: Enable Auto-Merge via GitHub UI

1. Go to `Settings > General > Pull Requests`
   → Enable **Allow auto-merge**
2. Go to `Settings > Branches > Protection Rules` for `main`
   - Require status checks
   - Enable **Allow auto-merge**

### Optional: Enable Auto-Merge via GitHub Action

Add a file `.github/workflows/dependabot-automerge.yml`:
```yaml
name: Enable Auto-Merge for Dependabot

on:
  pull_request:
    types: [opened, labeled]
    branches: [main]

jobs:
  automerge:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - name: Enable auto-merge
        uses: peter-evans/enable-pull-request-automerge@v3
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          merge-method: squash
```

---

## 📊 Logging & Error Handling

- Use `structlog` with JSON output
- Logging levels:
  - `DEBUG`: internal details
  - `INFO`: key flows and events
  - `ERROR`: unexpected failures

- Internal logs must be in English
- User-facing messages (e.g. Discord) must be in German
- Never log secrets or tokens
- All logs go to `logs/` and must support rotation

---

## 🔁 Clean Code & Maintainability

Automatically remove:
- Dead code (unreachable, unused, or never imported)
- Unused files or data
- Unused dependencies (verified via static analysis and coverage)

Other rules:
- TODOs are allowed only in dev branches and must start with `# TODO(githubuser):`
- Analyze and fix:
  - DB latency
  - inefficient APIs
  - memory or state leaks

---

## 🧠 Architecture & Quality

All code must be:
- Modular
- Testable
- Extensible

Follow principles like:
- Dependency Injection (DI)
- Factory Pattern
- Single Responsibility Principle (SRP)

A feature is only complete when:
- All business logic is implemented
- Unit and integration tests cover ≥90%
- CHANGELOG.md is updated
- README.md is updated
- CI passes 100%
- Commit message is descriptive and conventional

---

## ⚙️ Deployment & Release

Use **Semantic Release** via GitHub Actions **only if publishing to npm is intended**:

```yaml
on:
  push:
    branches: [main]
permissions:
  contents: write
  issues: write
  pull-requests: write
  id-token: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: "lts/*"
      - run: npm ci
      - name: Release
        uses: cycjimmy/semantic-release-action@v4
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

> ❗ **Do not include `NPM_TOKEN` unless the project is an npm package** intended to be published to [npmjs.com](https://www.npmjs.com/).
> If unsure, leave it unset. Data extractors, bots, and Python projects do **not** require `NPM_TOKEN`.

---

## 🔒 Optional Security Scans

Enable the following GitHub Actions:

### CodeQL
```yaml
- uses: github/codeql-action/init@v2
- uses: github/codeql-action/analyze@v2
```

### TruffleHog
```yaml
- uses: trufflesecurity/trufflehog@v3
  with:
    path: ./
  continue-on-error: false
```

---

## 🔐 Optional Auth Integration

For projects exposing APIs:
- Prefer token-based authentication (e.g. OAuth2, OIDC)
- Protect endpoints with authorization scopes
- Document auth flows in `README.md`

---

## 📌 Final Notes

These rules are final and apply across all Codex-managed repositories.
No manual fixes or local steps are allowed.
All builds, tests, scans, and releases must run completely within GitHub and Railway pipelines.
Codex must ensure deterministic, DRY, and compliant implementations at all times.

The `README.md` is generated by Codex and may be outdated.
Do **not** treat it as a rule source.
Instead, it must:
- Describe the repo and functionality clearly
- Reflect all scripts, env vars, APIs, and logic
- Be kept up to date based on real files, configs, and code
- Be written like a user-facing guide: specific and detailed
