# Privacy Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove exposed personal and operational identifiers from the public repository, prevent their accidental recommit, and rewrite the public Git history.

**Architecture:** Repository code keeps only generic privacy checks. User-specific regular expressions are stored in the local Git configuration under `cinelog.privacyPattern`, which is outside the tracked tree. Current files are sanitized first; a disposable mirror is then rewritten and scanned before its `master` ref replaces the GitHub branch.

**Tech Stack:** Bash, Git hooks, pytest, git-filter-repo, GitHub remote.

## Global Constraints

- Never put the user's real name, historical email addresses, hostname, absolute path, or VM name in a tracked file, test, or commit message.
- Keep user-specific hook patterns in local Git configuration only.
- Do not use `--no-verify` for new commits.
- Rewrite and force-push only after current-tree tests and a mirror-history scan succeed.
- Run `python3 -m pytest -q`, `node --check static/js/app.js`, and `git diff --check` before the final push.

---

### Task 1: Add local privacy-pattern hook coverage

**Files:**
- Modify: `tests/test_pre_commit_hook.py`
- Modify: `scripts/pre-commit`

**Interfaces:**
- Consumes: local Git configuration values from `git config --local --get-all cinelog.privacyPattern`
- Produces: a nonzero pre-commit exit status when any configured regular expression matches an added diff line

- [ ] **Step 1: Write the failing test**

```python
def test_pre_commit_blocks_locally_configured_privacy_pattern(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path, "probe.txt", "owner=local-sensitive-identity\\n")
    subprocess.run(
        ["git", "config", "--local", "--add", "cinelog.privacyPattern", "local-sensitive-identity"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run([str(HOOK)], cwd=repo, capture_output=True, text=True)

    assert result.returncode == 1
    assert "local privacy pattern" in result.stdout
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python3 -m pytest -q tests/test_pre_commit_hook.py::test_pre_commit_blocks_locally_configured_privacy_pattern`

Expected: the hook exits `0` because it does not yet read `cinelog.privacyPattern`.

- [ ] **Step 3: Implement the minimal hook loop**

Add this after the generic `check_pattern` calls in `scripts/pre-commit`:

```bash
while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    check_pattern "local privacy pattern" "$pattern"
done < <(git config --local --get-all cinelog.privacyPattern || true)
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `python3 -m pytest -q tests/test_pre_commit_hook.py::test_pre_commit_blocks_locally_configured_privacy_pattern`

Expected: `1 passed`.

- [ ] **Step 5: Commit the tested hook behavior**

```bash
git add scripts/pre-commit tests/test_pre_commit_hook.py
git commit -m "feat: support local privacy patterns in hook"
```

### Task 2: Sanitize current scripts and deployment documentation

**Files:**
- Modify: `scripts/pre-commit`
- Modify: `tests/test_pre_commit_hook.py`
- Modify: `tools/cleanup_db_backups.sh`
- Modify: `deploy/README.md`
- Create: `tests/test_privacy_sanitization.py`

**Interfaces:**
- Consumes: `$0` in `tools/cleanup_db_backups.sh`
- Produces: a repository root calculated as the parent directory of the script and generic deployment placeholders

- [ ] **Step 1: Write failing static safety tests**

```python
def test_backup_cleanup_derives_the_repository_root() -> None:
    source = (ROOT / "tools" / "cleanup_db_backups.sh").read_text(encoding="utf-8")
    assert 'REPO="$(cd "$(dirname "$0")/.." && pwd)"' in source
    assert "/Users/" not in source


def test_deployment_readme_uses_generic_vm_placeholders() -> None:
    source = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    assert "<VM_NAME>" in source
    assert "<ZONE>" in source
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest -q tests/test_privacy_sanitization.py`

Expected: both assertions fail against the hard-coded path and VM details.

- [ ] **Step 3: Make the minimum source changes**

Replace the backup script assignment with:

```bash
REPO="$(cd "$(dirname "$0")/.." && pwd)"
```

Remove the user-specific `REAL_NAME` assignment and username rule from `scripts/pre-commit`. Replace every concrete VM name and zone in `deploy/README.md` with `<VM_NAME>` and `<ZONE>`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `python3 -m pytest -q tests/test_pre_commit_hook.py tests/test_privacy_sanitization.py`

Expected: all selected tests pass.

- [ ] **Step 5: Configure local-only patterns and prove the live hook blocks them**

Add the approved user-specific regular expressions directly to local Git configuration with `git config --local --add cinelog.privacyPattern`. The values must not appear in a tracked file, test fixture, shell-history output, or commit message.

Use a temporary index containing a probe blob to verify the active pre-commit hook rejects each local pattern. Do not put the literal patterns into tracked files or command output.

- [ ] **Step 6: Commit the sanitized current tree**

```bash
git add scripts/pre-commit tests/test_pre_commit_hook.py tools/cleanup_db_backups.sh deploy/README.md tests/test_privacy_sanitization.py
git commit -m "fix: remove public personal deployment details"
```

### Task 3: Verify the current tree before history rewrite

**Files:**
- Modify: `docs/superpowers/plans/2026-06-22-privacy-remediation.md` (checkbox state only)

- [ ] **Step 1: Run the project verification suite**

Run: `python3 -m pytest -q && node --check static/js/app.js && git diff --check`

Expected: all tests and checks exit `0`.

- [ ] **Step 2: Scan the current `master` tree without printing sensitive values**

Run Git searches for common private-key, token, password URL, local absolute-path, and personal-identifier patterns. Report matching file paths only.

Expected: no credential or personal-identifier matches; generic deployment placeholders are allowed.

### Task 4: Rewrite and publish sanitized history

**Files:**
- No tracked source files; operate only in a disposable mirror clone.

**Interfaces:**
- Consumes: the current GitHub `master` ref and in-memory replacement expressions
- Produces: a rewritten `master` with sanitized blob contents and noreply author/committer metadata

- [ ] **Step 1: Confirm `git filter-repo` availability and its replacement syntax**

Run: `git filter-repo --help`

Expected: command is available. If it is not installed, install it outside the repository before proceeding.

- [ ] **Step 2: Create a disposable bare mirror from GitHub**

Run: `git clone --mirror https://github.com/dayeonisme/personal-cinelog.git <temporary-directory>`

Expected: the mirror has the current `master` ref and no working tree.

- [ ] **Step 3: Rewrite blob contents and commit identity in the mirror**

Use `git filter-repo --force --replace-text` with process-substituted literal replacements. Use a `--commit-callback` to set both author and committer name/email to the GitHub noreply identity when either historical personal email is present.

- [ ] **Step 4: Scan rewritten history and author metadata**

Run the same path-only secret/identifier scan against every reachable rewritten commit and list unique author emails.

Expected: no replacement targets remain and only the noreply author email is present.

- [ ] **Step 5: Force-push only rewritten `master`**

Run: `git push origin +refs/heads/master:refs/heads/master`

Expected: GitHub accepts the non-fast-forward update.

- [ ] **Step 6: Fetch the workspace repository and verify its remote matches the rewritten master**

Run: `git fetch origin --prune && git rev-parse origin/master`

Expected: the remote SHA equals the rewritten mirror SHA.

### Task 5: Record final verification

**Files:**
- Modify: `docs/superpowers/plans/2026-06-22-privacy-remediation.md` (checkbox state only)

- [ ] **Step 1: Re-run the full test suite and syntax checks after the force-push**

Run: `python3 -m pytest -q && node --check static/js/app.js && git diff --check`

Expected: all commands exit `0`.

- [ ] **Step 2: Report operational follow-up**

State that clones must be refreshed, no `--no-verify` commits are permitted for this repository, and historical external clones/caches cannot be recalled.
