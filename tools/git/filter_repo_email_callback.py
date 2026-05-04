# Body for: git filter-repo --email-callback @tools/git/filter_repo_email_callback.py
# Keeps dependabot; maps everyone else to primary GitHub noreply.
BOT = b"49699333+dependabot[bot]@users.noreply.github.com"
HUMAN = b"vaquarkhan@users.noreply.github.com"
if email == BOT:
    return email
return HUMAN
