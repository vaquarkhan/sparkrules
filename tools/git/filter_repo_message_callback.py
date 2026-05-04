# Body for: git filter-repo --message-callback @tools/git/filter_repo_message_callback.py
# Drop Co-authored-by lines (removes Cursor/GitHub bot attribution trailers).
lines = [ln for ln in message.split(b"\n") if not ln.lower().startswith(b"co-authored-by:")]
out = b"\n".join(lines)
if message.endswith(b"\n"):
    out += b"\n"
return out
