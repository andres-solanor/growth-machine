# Branching Strategy — Explained for Non-Developers

> **Who is this for?** You (Andrés), the project owner. No programming knowledge needed.
> **Keep updated:** if the branch setup ever changes, update this document in the same commit.

---

## 1. What is a "branch"? (the photocopy analogy)

Think of the project as a **master binder** containing every page of your work (the code).

A **branch** is like making a **photocopy of the entire binder** and working on the copy. You can scribble on it, rip pages out, rewrite chapters — the original binder is never touched. When (and only when) you're happy with the copy, you can carefully transfer the good changes back into another binder. Git (the version control tool) does this copying instantly and for free, and it remembers every version of every page forever.

Important mental model: **branches live inside the same repository (the same folder on your computer)**. Switching branches just swaps which "binder" you're currently looking at. The files on your disk change automatically when you switch — nothing is lost, the other binder is safely stored by git.

## 2. Our two main branches

| Branch | What it is | Rule |
|---|---|---|
| **`main`** | The **safe, working copy** that produces the reports you deliver to La Panettería every week. Today it works; it must keep working. | Only bakery-related fixes and improvements go here. Nothing experimental. |
| **`saas`** | The **construction site** for the new online application (the subscription/funnel product). Everything new — the website, database, user accounts — is built here. | Can be messy or temporarily broken; it never affects `main`. |

There are also short-lived **feature branches** (e.g. `saas/web-scaffold`). These are photocopies *of the photocopy*: small workspaces for one specific feature, merged back into `saas` when done. You don't need to manage these — Claude/your developer tools handle them — but you'll see their names in the history.

(You may also see two older branches, `base-code` and `chore/professional-layout` — they are historical leftovers, not part of this strategy.)

## 3. Why this protects La Panettería

Your weekly routine (running `run_reports.ps1`, generating `report.html`) reads the files **of whichever branch is currently active**. As long as you are on `main`, you are using the proven, untouched version — even if the `saas` branch is mid-construction and completely broken that day.

The new app will also **move files around** (the analysis engine moves into a `worker/engine/` folder on `saas`). That reorganization only exists on `saas`. On `main`, everything stays exactly where it is today.

## 4. How changes flow between branches

```
main  ──────●──────●─────────●────────►   (bakery deliveries, always working)
             \              ↑ fixes flow DOWN into saas regularly
              \             │
saas  ─────────●──●──●──●──●──●───────►   (the new online app being built)
                   ↑  ↑
        feature branches merge in
```

- **`main` → `saas` (regular):** when the bakery analysis gets a fix or improvement on `main`, we merge it into `saas` so the online app's engine stays up to date. This is routine and safe.
- **`saas` → `main` (rare, deliberate):** only when something built for the app is also clearly useful for the local bakery workflow, and only after testing.
- The Hostinger website will deploy **from `saas`** (later from a dedicated `production` branch). It will **never** deploy from `main`, and deploying never modifies any branch.

## 5. Your practical cheat sheet

**To check which branch you're on** (safe, always):
```
git branch
```
The one with the `*` is active.

**Before your weekly La Panettería report, make sure you're on `main`:**
```
git checkout main
```
Then run `.\run_reports.ps1` as always.

**Safe at any time** (they only look, never change anything):
- `git branch` — list branches
- `git status` — what's modified right now
- `git log --oneline -10` — last 10 saved snapshots

**Ask before running** (they change things; not dangerous if used right, but easy to misuse):
- `git merge ...` — combines branches
- `git reset ...` / `git checkout -- file` — can discard work
- `git push --force` — can overwrite history on GitHub

**Golden rules:**
1. Bakery work → be on `main`. App work → be on `saas` (Claude handles this automatically in sessions).
2. If `git status` shows files you don't recognize as yours, ask before deleting anything.
3. You can't really destroy committed work — git keeps history. The worst case is confusion, not loss. When in doubt, stop and ask.

## 6. FAQ

**"If I switch to `saas`, did I lose my `main` files?"**
No. Switching swaps what you see; both versions are stored. Switch back anytime with `git checkout main`.

**"Why not a separate repository for the app?"**
The app reuses the same analysis engine. One repo means bug fixes flow between bakery and app with a one-line merge instead of error-prone manual copying between two repos.

**"What if both branches change the same file?"**
Git flags it as a "conflict" during merge and a human (or Claude) resolves it by choosing/combining the versions. Nothing is silently overwritten.

**"Where do my uploaded sales files (.xls) live?"**
POS exports in `reports/input_data/` are deliberately **not tracked by git** (they're ignored), so they stay on your disk regardless of branch switching.
