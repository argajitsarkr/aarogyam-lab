"""Who can log in - the single list of lab accounts (same model as TGMA's scripts/init_db.py).

Accounts are created and updated only by `python manage.py seed_users` on the server
(`bash deploy.sh seed-users`); there is no sign-up and no in-app "Add user".

Passwords are NEVER in this file. Each account's one-time bootstrap password is read from
the server .env variable named in `password_env` (min 12 characters). Every new account is
created with must_change_password=True, so that value stops working the moment the person
sets their own password at first login. Afterwards the .env line can be cleared.

Fields:
  username      login name; use the person's email for named logins (as TGMA does)
  first_name / last_name
  role          "ADMIN" or "EMPLOYEE" (roles and access will be redefined later)
  home_centre   centre short code ("ARP", "RRM", "BHY"); required for EMPLOYEE
  extra_centres short codes the person may also read (optional)
  password_env  .env variable holding the bootstrap password
"""

SEED_USERS = [
    {
        "username": "argajit05@gmail.com",
        "first_name": "Argajit",
        "last_name": "Sarkar",
        "role": "ADMIN",  # site developer; also listed in DEVELOPER_ACCOUNTS (outside the 3-Admin cap)
        "home_centre": None,
        "extra_centres": [],
        "password_env": "SEED_PW_ARGAJIT05",
    },
]

# Usernames to deactivate on the next seed run (soft delete: history and audit trail are kept).
REMOVE_USERS = []
