# Body for: git filter-repo --name-callback @tools/git/filter_repo_name_callback.py
BOT = b"dependabot[bot]"
HUMAN = b"vaquarkhan"
if name == BOT:
    return name
return HUMAN
