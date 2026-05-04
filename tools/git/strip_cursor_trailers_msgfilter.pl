#!/usr/bin/perl
# Used as: git filter-branch -f --msg-filter "perl tools/git/strip_cursor_trailers_msgfilter.pl"
# Run from repo root; path must exist in commits being rewritten (add file on a branch first) or use absolute path.
use strict;
use warnings;
while (<STDIN>) {
    next if /^\s*Co-authored-by:\s*Cursor\b/i;
    next if /^\s*Co-authored-by:.*cursoragent@/i;
    next if /^\s*Made-with:\s*Cursor\b/i;
    next if /^\s*Made with Cursor\b/i;
    print;
}
