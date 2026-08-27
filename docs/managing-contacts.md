# Managing Contacts

Contact records are stored in `contacts.db` and auto-seeded with 20 fictional customer contacts on first run. You can view, add, update, and delete records directly with `sqlite3`.

> **Windows users**: `sqlite3` is not installed by default. Download it from [sqlite.org/download](https://www.sqlite.org/download.html) (look for "sqlite-tools" under "Precompiled Binaries for Windows"), unzip it, and add the folder to your PATH — or use [DB Browser for SQLite](https://sqlitebrowser.org/) for a graphical interface instead.

> **Passwords are never stored in plaintext.** The `Password` column holds a PBKDF2
> hash (`iterations$salt$hash`), not the password itself — `search_by_*` tools never
> return this column, and `authenticate` verifies against the hash. Writing a plaintext
> value into `Password` with raw SQL will break login for that contact. Whenever a
> command below needs a password, hash it first with the project's own hashing
> function so the format matches what `authenticate` expects:
>
> ```bash
> NEW_HASH=$(uv run python -c "
> from mcp_server_kit.contact_database import _hash_password
> print(_hash_password('changeme123'))
> ")
> ```

## View all contacts

```bash
sqlite3 contacts.db "SELECT Id, FirstName, LastName, Email, AccountName FROM contacts;"
```

## Search for a contact

```bash
# By last name
sqlite3 contacts.db "SELECT * FROM contacts WHERE LastName LIKE '%Webb%';"

# By email
sqlite3 contacts.db "SELECT * FROM contacts WHERE Email = 'james.whitfield@meridiancorp.com' COLLATE NOCASE;"

# By account ID
sqlite3 contacts.db "SELECT * FROM contacts WHERE AccountId = 'MC-001';"
```

## Add a new contact

Hash the password first (see the note above), then embed the hash — never the
plaintext value — in the `INSERT`:

```bash
NEW_HASH=$(uv run python -c "
from mcp_server_kit.contact_database import _hash_password
print(_hash_password('changeme123'))
")

sqlite3 contacts.db "
INSERT INTO contacts (
  Id, FirstName, LastName, Salutation, Name,
  Email, Phone, MobilePhone, Title, Department,
  AccountId, AccountName,
  MailingStreet, MailingCity, MailingState, MailingPostalCode, MailingCountry,
  LeadSource, OwnerId, CreatedDate, LastModifiedDate,
  Description, DoNotCall, HasOptedOutOfEmail, IsDeleted,
  ContactSource, CaseCount, Password
) VALUES (
  '0031A00001aBC021', 'Alex', 'Sample', 'Mr.', 'Alex Sample',
  'alex.sample@example.com', '555-9999', '555-9998', 'Test User', 'Engineering',
  'MC-001', 'Meridian Corporation',
  '1 Test St', 'Chicago', 'IL', '60601', 'US',
  'Web', '0051A000001owner', '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z',
  'Test contact.', 0, 0, 0,
  'Inbound', 0, '$NEW_HASH'
);"
```

## Update a contact's password

```bash
NEW_HASH=$(uv run python -c "
from mcp_server_kit.contact_database import _hash_password
print(_hash_password('newpassword!'))
")

sqlite3 contacts.db "UPDATE contacts SET Password = '$NEW_HASH' WHERE Email = 'james.whitfield@meridiancorp.com' COLLATE NOCASE;"
```

## Delete a contact

```bash
sqlite3 contacts.db "DELETE FROM contacts WHERE Id = '0031A00001aBC021';"
```

## Reset to seed data

To wipe all contacts and re-seed with the original 20 fictional contacts, delete the database file and restart the server — it will recreate and re-seed automatically:

**macOS:**
```bash
rm contacts.db
uv run -m mcp_server_kit.contacts
```

**Windows (PowerShell):**
```powershell
del contacts.db
uv run -m mcp_server_kit.contacts
```
