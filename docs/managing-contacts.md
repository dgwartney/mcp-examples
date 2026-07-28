# Managing Contacts

Contact records are stored in `contacts.db` and auto-seeded with 20 Warner Bros. characters on first run. You can view, add, update, and delete records directly with `sqlite3`.

> **Windows users**: `sqlite3` is not installed by default. Download it from [sqlite.org/download](https://www.sqlite.org/download.html) (look for "sqlite-tools" under "Precompiled Binaries for Windows"), unzip it, and add the folder to your PATH — or use [DB Browser for SQLite](https://sqlitebrowser.org/) for a graphical interface instead.

## View all contacts

```bash
sqlite3 contacts.db "SELECT Id, FirstName, LastName, Email, AccountName FROM contacts;"
```

## Search for a contact

```bash
# By last name
sqlite3 contacts.db "SELECT * FROM contacts WHERE LastName LIKE '%Bunny%';"

# By email
sqlite3 contacts.db "SELECT * FROM contacts WHERE Email = 'bugs.bunny@acme.com' COLLATE NOCASE;"

# By account ID
sqlite3 contacts.db "SELECT * FROM contacts WHERE AccountId = 'ACME-001';"
```

## Add a new contact

```bash
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
  '0031A00001aBC021', 'Elmer', 'Sample', 'Mr.', 'Elmer Sample',
  'elmer.sample@example.com', '555-9999', '555-9998', 'Test User', 'Engineering',
  'ACME-001', 'ACME Corporation',
  '1 Test St', 'Burbank', 'CA', '91505', 'US',
  'Web', '0051A000001owner', '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z',
  'Test contact.', 0, 0, 0,
  'Inbound', 0, 'changeme123'
);"
```

## Update a contact's password

```bash
sqlite3 contacts.db "UPDATE contacts SET Password = 'newpassword!' WHERE Email = 'bugs.bunny@acme.com' COLLATE NOCASE;"
```

## Delete a contact

```bash
sqlite3 contacts.db "DELETE FROM contacts WHERE Id = '0031A00001aBC021';"
```

## Reset to seed data

To wipe all contacts and re-seed with the original 20 Warner Bros. characters, delete the database file and restart the server — it will recreate and re-seed automatically:

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
