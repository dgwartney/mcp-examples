-- Schema for the contacts table used by ContactDatabaseManager.
--
-- Email is UNIQUE COLLATE NOCASE so two contacts can never share a login
-- email, matching the case-insensitive lookup used by authenticate() and
-- the search_by_email tool.
CREATE TABLE IF NOT EXISTS contacts (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    Id TEXT,
    FirstName TEXT,
    LastName TEXT,
    Salutation TEXT,
    Name TEXT,
    Email TEXT UNIQUE COLLATE NOCASE,
    Phone TEXT,
    MobilePhone TEXT,
    Title TEXT,
    Department TEXT,
    AccountId TEXT,
    AccountName TEXT,
    MailingStreet TEXT,
    MailingCity TEXT,
    MailingState TEXT,
    MailingPostalCode TEXT,
    MailingCountry TEXT,
    LeadSource TEXT,
    OwnerId TEXT,
    CreatedDate TEXT,
    LastModifiedDate TEXT,
    Description TEXT,
    DoNotCall TEXT,
    HasOptedOutOfEmail TEXT,
    IsDeleted TEXT,
    ContactSource TEXT,
    CaseCount TEXT,
    Password TEXT
);
