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
