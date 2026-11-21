---
name: git-commit
description: Generate Conventional Commits-style commit messages by analyzing git diffs. Use this skill whenever the user asks for help writing a commit message, reviewing staged changes, splitting work into atomic commits, or needs a commit message for the current changes. Works in any git repository regardless of language or stack.
allowed-tools: Bash, Read, Grep, Glob
argument-hint: [issue-ref]
---

# Git Commit Message Generator

Generate a commit message for the current staged/unstaged changes, following the
[Conventional Commits](https://www.conventionalcommits.org/) standard.

**Adapt to the project first.** Before applying the defaults below, check whether the repository
defines its own commit conventions and follow those instead when present:

1. Look for a conventions doc — `CONTRIBUTING.md`, `COMMITS.md`, `docs/commit*.md`, or similar. If one
   exists, read it and follow it.
2. Inspect recent history for the established style: `git log --oneline -20`. Match the prevailing
   type/scope/casing/issue-reference conventions you observe.
3. If the repo defines nothing, use the Conventional Commits defaults in this skill.

## Workflow

1. Run `git status` to see all changed files (staged and unstaged).
2. Run `git diff --staged` to inspect staged changes. If nothing is staged, run `git diff` to analyze
   all unstaged changes.
3. **Check commit atomicity** (see below).
4. **If changes are cohesive**: determine type and scope, propose the commit message, and offer to
   stage the files.
5. **If changes should be split**: present the split plan and ask the user which group to stage first.

**IMPORTANT**: Do NOT run `git commit` unless the user explicitly asks for it. By default this skill
only stages files (`git add`) and proposes commit messages; committing is the developer's decision.

## Commit atomicity check

Before generating a message, verify that the changes represent **a single logical change**. Suggest
splitting if any of these apply:

- Changes mix **different types** (e.g. a `feat` and a `fix`, or a `refactor` and a `style` change).
- Changes affect **multiple scopes** with **unrelated purposes** (e.g. a UI feature + an unrelated API fix).
- Changes include **unrelated modifications** in the same file (e.g. a bugfix + formatting cleanup elsewhere).

### When splitting is needed

Present a numbered plan with each logical commit, the files involved, and the proposed message. Then
ask the user which one to stage first. Example:

```
I detected 2 independent changes that should be separate commits:

1. refactor(auth): extract token refresh into a dedicated service
   Files: src/auth/token.service.ts

2. fix(ui): prevent null crash in the profile view
   Files: src/profile/profile.component.ts

Which one do you want to stage first? (1/2/skip)
```

User responses:
- **A number (e.g. "1")**: run `git add` for those files, show the commit message to use, then ask about the next group.
- **"skip"**: skip the atomicity suggestion and stage everything with a single commit message.
- **Custom input**: the user may adjust the message or grouping — follow their instructions.

### When changes are cohesive

Show the proposed commit message and offer to stage the files. If nothing is staged yet, ask before
running `git add`.

## Staging

When the user confirms:
1. Run `git add` with the specific files for that logical change.
2. Show the commit message for the user to copy or use.
3. If there are remaining unstaged changes from the split plan, ask: "Ready for the next one?" and show
   the next proposed group with its message.

## Commit format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

- Issue references go in a footer (see [Issue references](#issue-references)). Omit them when there's no issue.
- `scope` is optional — include it when it adds clarity, omit it when the change is repo-wide.
- Keep it to the parts the project actually uses. If recent history shows no scopes, don't invent them.
- **Hooks:** if the repo has a `commit-msg`/`prepare-commit-msg` hook that injects content automatically
  (e.g. a branch name or an issue id), do NOT add that content manually — check `.git/hooks/` or the
  project's hook config if unsure.

## Types

| Type | Use when |
|------|----------|
| `feat` | New functionality |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructuring, no behavior change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `build` | Build system, packaging, dependencies |
| `ci` | CI configuration |
| `chore` | Tooling, config, maintenance |
| `revert` | Reverting a previous commit |

## Scope detection

Scope is the area of the codebase the change touches. Derive it from the changed file paths rather than
a fixed list — infer it from the repository's own structure:

- **Monorepo / packages** → the package or app name (`packages/<name>/`, `apps/<name>/`).
- **Layered repo** → the top-level area (`api`, `ui`, `auth`, `db`, `core`, `docs`, `ci`).
- **Feature folders** → the feature/module the files belong to.

Confirm against `git log` — reuse scopes the project already uses instead of introducing new ones.

- If changes affect **one scope**, use it.
- If changes affect **multiple scopes**, omit the scope or use the primary one.

## Description rules

- **Imperative present tense**: "add", "fix", "change" (not "added", "fixed").
- Start with a lowercase letter by default (Conventional Commits style). If `git log` shows the project
  capitalizes the first letter, match it.
- Keep the whole first line within **72 characters** (type + scope + description).
- Write in the project's commit language; default to English if unspecified.

## Body rules

- Optional. Explains the **why**, not the **what**.
- Separated from the description by a blank line.
- Lines wrapped at **72 characters**.
- Imperative present tense. Keep it brief — if the body sprawls, the commit should probably be split.

## Issue references

Reference issues in a footer, separated from the body by a blank line. If `git log` shows the project
uses another format, follow it. Default (GitHub/GitLab syntax):

```
fix(ui): prevent duplicate click on the submit button

Refs: #123
```

Use `Closes #123` (or `Fixes #123`) when the commit resolves the issue — GitHub and GitLab close it
automatically on merge. For multiple issues, separate them with commas:

```
fix(api): handle null values in the event handlers

Refs: #120, #121
```

Include the reference when the user passes it as the argument (`$ARGUMENTS`) or mentions an issue.
If there's no issue, omit it.

## Breaking changes

Conventional Commits marks breaking changes with a `!` before the colon and/or a `BREAKING CHANGE:`
footer. Use them unless the project explicitly avoids them.

```
feat(api)!: drop support for v1 auth tokens

BREAKING CHANGE: Clients using v1 tokens must migrate to OAuth before upgrading.
```

## Revert commits

Use `revert` as the type. Reference the reverted commit SHAs in a `Refs:` footer:

```
revert(ui): remove tooltip from the settings panel

The tooltip caused rendering issues on low-resolution displays.
A new approach will be implemented in a follow-up.

Refs: 676104e, a215868
```

## Examples

**Feature:**
```
feat(ui): add volume slider to the audio player
```

**Bug fix with body and issue ref:**
```
fix(api): prevent duplicate websocket connections

The connection manager was not checking for existing connections
before creating a new one, causing duplicate event handlers.

Closes #123
```

**Refactor with file list:**
```
refactor(auth): reorganize the session module structure

- Move session logic from the controller into a dedicated service
- Extract session types into a separate file
- Update related imports
```

**Documentation:**
```
docs: update the getting-started guide with the new lint rules
```

**Build / dependencies:**
```
build: upgrade the test runner from v14 to v15
```
