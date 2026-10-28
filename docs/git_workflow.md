# Git workflow (branches, testing, rollback)

The kit itself (rules, SOP, tools, templates) is versioned with git. Your videos are not: `videos/*` is ignored.

## Rule
Every **non-trivial** change to the kit (new rules, template changes, new scripts, workflow or pipeline
changes) goes on its **own branch**, never straight to `main`.

1. Branch from main: `git checkout -b v<MAJOR>.<MINOR>-<short-description>` (e.g. `v1.2-tighter-edges`).
2. Make the changes there. Clear commits, one topic each.
3. Push the branch: `git push -u origin <branch>`.
4. The editor **tests the branch on a real video** before merging.
5. Only after the editor approves: merge into `main`.
6. Tag the merge: `git tag v<MAJOR>.<MINOR>` and push the tag (`git push origin v<MAJOR>.<MINOR>`).
7. Small fixes (a typo, a one-line bug) may go straight to `main`; Claude says what it did.

While the editor tests a branch, the kit folder stays **on that branch**: Claude reads the rules from disk,
so `git checkout main` brings back the old rules. Before starting a video, `git branch --show-current`
tells you which rules are active.

## Never
- Commit untested changes straight to `main`.
- Squash-merge without asking.
- Force-push to `main` or to a branch that was already pushed.
- Push without the editor's OK (Claude shows the list of changed files first).

## Rollback
`git checkout <previous-tag>` or `git revert <commit>` + push. If the editor asks to go back, do it without arguing.
