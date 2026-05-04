# Removing Cursor attribution from Git history

Commit messages must not include IDE vendor trailers (see `.cursor/rules/git-commit-no-cursor.mdc` and `CONTRIBUTING.md`). The canonical `main` branch is kept free of those lines.

## Check for trailers

```bash
git log --all --format=%B | rg -i "co-authored-by:.*cursor|cursoragent@|made-with:.*cursor|made with cursor"
```

If this prints nothing, there is nothing to rewrite.

## Rewrite (advanced)

Use **[git-filter-repo](https://github.com/newren/git-filter-repo)** with a `--message-callback` that drops matching lines, or `git filter-branch` with `--msg-filter` and a small script. A reference filter script lives at [`tools/git/strip_cursor_trailers_msgfilter.pl`](../tools/git/strip_cursor_trailers_msgfilter.pl); pass its **absolute** path to `--msg-filter` so early commits can run the filter even before that file existed in the tree.

After any rewrite: delete `refs/original/`, expire reflogs, `git gc --prune=now`, then coordinate **force-with-lease** pushes and fork resets.

## If GitHub still lists `cursoragent` as a contributor

GitHub’s **Insights → Contributors** graph is driven by **commits that reached the default branch** (and can lag after you fix messages). It is **not** something you can toggle off in settings—you have to remove the underlying commits or wait for the graph to refresh.

1. **Search the repo on GitHub** (not only local):  
   `https://github.com/<org>/<repo>/search?q=cursoragent&type=commits`  
   If anything appears, those SHAs still need rewriting or reverting.

2. **Confirm locally** (should print nothing after a clean scrub):

   ```bash
   git fetch --all
   git log --all --format=%B | rg -i "cursoragent|co-authored-by:.*cursor|made-with:.*cursor"
   ```

3. **If you find hits on a branch**: rewrite **all** branches that still contain them (including old feature branches), then `git push --force-with-lease --all` and `git push --force-with-lease --tags` (only after coordinating with collaborators). Dependabot branches usually do not matter; **default branch + long-lived branches** do.

   After a `filter-repo` mailmap pass, **re-fetch** (`git fetch --all`) and compare local tips to `origin/*`. If `git shortlog -sne origin/dev/...` still shows **`Vaquar Khan <vaquar.cna@gmail.com>`** or an old email on a **remote-tracking** branch, that branch was never force-pushed — run e.g. `git push origin dev/workbench-next --force` for each stale head so GitHub stops serving old SHAs on branch tips.

   You **cannot** delete GitHub’s internal `refs/pull/*/head` snapshots from your laptop; those point at whatever was last pushed to each PR. If search still finds bad SHAs only under old PRs, the contributors list usually updates once **default branch** history is clean, but extreme cases may need [GitHub Support](https://support.github.com/).

4. **If `cursoragent` is a GitHub user** shown under **Settings → Collaborators** (or a pending invite), remove access there—that is separate from the contributors graph.

5. **After history is clean**, allow up to **~24 hours** for the contributors graph to update.

6. **Prevent recurrence**: Cursor **Agent → Attribution** off; use `git -c core.hooksPath=.git/hooks commit …` if a global hook still appends trailers; keep the home `commit-msg` hook stripping `Co-authored-by: Cursor` / `cursoragent@` (see your `~/.githooks/commit-msg` or Windows equivalent).
