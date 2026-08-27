"""
Database management for mock customer contact profiles.

Provides a SQLite-backed store of Salesforce-style contact records
seeded with 20 fictional customer contacts on first run.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import hashlib
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Lower than OWASP's production guidance (~600k) to keep this demo database's
# per-fixture reseeding fast in tests; still far stronger than plaintext.
_PBKDF2_ITERATIONS = 100_000


def _hash_password(password: str) -> str:
    """Hash a password for storage as ``iterations$salt_hex$hash_hex``."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a hash produced by ``_hash_password``."""
    try:
        iterations_str, salt_hex, digest_hex = stored.split("$")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return secrets.compare_digest(candidate.hex(), digest_hex)


# Column order used to build INSERT statements. Must match the columns
# defined in schema.sql (excluding rowid).
_CONTACT_COLUMNS = [
    "Id", "FirstName", "LastName", "Salutation", "Name", "Email", "Phone",
    "MobilePhone", "Title", "Department", "AccountId", "AccountName",
    "MailingStreet", "MailingCity", "MailingState", "MailingPostalCode",
    "MailingCountry", "LeadSource", "OwnerId", "CreatedDate",
    "LastModifiedDate", "Description", "DoNotCall", "HasOptedOutOfEmail",
    "IsDeleted", "ContactSource", "CaseCount", "Password",
]

# TODO: move this seed data out to a .sql file loaded by seed_contacts()
# instead of an in-code list (see CLAUDE.md TODO — cleanup).
_SEED_CONTACTS = [
    {
        "Id": "0031A00001aBC001", "FirstName": "James", "LastName": "Whitfield",
        "Salutation": "Mr.", "Name": "James Whitfield",
        "Email": "james.whitfield@meridiancorp.com", "Phone": "555-0101",
        "MobilePhone": "555-0102", "Title": "Chief Operating Officer",
        "Department": "Executive", "AccountId": "MC-001",
        "AccountName": "Meridian Corporation", "MailingStreet": "100 Corporate Dr",
        "MailingCity": "Chicago", "MailingState": "IL",
        "MailingPostalCode": "60601", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-01-15T10:30:00Z",
        "LastModifiedDate": "2024-06-01T14:00:00Z",
        "Description": "Top performer, consistently exceeds quarterly targets.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 5,
        "Password": "password123",
    },
    {
        "Id": "0031A00001aBC002", "FirstName": "Daniel", "LastName": "Reyes",
        "Salutation": "Mr.", "Name": "Daniel Reyes",
        "Email": "daniel.reyes@meridiancorp.com", "Phone": "555-0201",
        "MobilePhone": "555-0202", "Title": "VP of Marketing",
        "Department": "Marketing", "AccountId": "MC-001",
        "AccountName": "Meridian Corporation", "MailingStreet": "102 Corporate Dr",
        "MailingCity": "Chicago", "MailingState": "IL",
        "MailingPostalCode": "60601", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-02-10T09:00:00Z",
        "LastModifiedDate": "2024-05-20T11:30:00Z",
        "Description": "Enthusiastic about new campaigns; quick decision maker.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 12,
        "Password": "reyes_market99",
    },
    {
        "Id": "0031A00001aBC003", "FirstName": "Robert", "LastName": "Chen",
        "Salutation": "Mr.", "Name": "Robert Chen",
        "Email": "robert.chen@meridiancorp.com", "Phone": "555-0301",
        "MobilePhone": "555-0302", "Title": "Senior Communications Specialist",
        "Department": "Communications", "AccountId": "MC-001",
        "AccountName": "Meridian Corporation", "MailingStreet": "104 Corporate Dr",
        "MailingCity": "Chicago", "MailingState": "IL",
        "MailingPostalCode": "60601", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-03-05T08:15:00Z",
        "LastModifiedDate": "2024-04-10T16:45:00Z",
        "Description": "Handles press inquiries and internal communications.",
        "DoNotCall": 1, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 3,
        "Password": "chen_comms123",
    },
    {
        "Id": "0031A00001aBC004", "FirstName": "Frank", "LastName": "Douglas",
        "Salutation": "Mr.", "Name": "Frank Douglas",
        "Email": "frank.douglas@meridiancorp.com", "Phone": "555-0401",
        "MobilePhone": "555-0402", "Title": "Head of Field Operations",
        "Department": "Field Ops", "AccountId": "MC-001",
        "AccountName": "Meridian Corporation", "MailingStreet": "106 Corporate Dr",
        "MailingCity": "Chicago", "MailingState": "IL",
        "MailingPostalCode": "60601", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-03-20T07:00:00Z",
        "LastModifiedDate": "2024-03-15T10:00:00Z",
        "Description": "Oversees on-site crews across three regional offices.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 8,
        "Password": "douglas_ops77",
    },
    {
        "Id": "0031A00001aBC005", "FirstName": "Rachel", "LastName": "Adams",
        "Salutation": "Ms.", "Name": "Rachel Adams",
        "Email": "rachel.adams@cascademedia.com", "Phone": "555-0501",
        "MobilePhone": "555-0502", "Title": "Content Strategist",
        "Department": "Content Strategy", "AccountId": "CM-001",
        "AccountName": "Cascade Media Group", "MailingStreet": "200 Harbor Ave",
        "MailingCity": "Seattle", "MailingState": "WA",
        "MailingPostalCode": "98101", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-04-01T12:00:00Z",
        "LastModifiedDate": "2024-07-01T09:30:00Z",
        "Description": "Leads editorial calendar planning for two brands.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 2,
        "Password": "adams_content55",
    },
    {
        "Id": "0031A00001aBC006", "FirstName": "Victor", "LastName": "Alvarez",
        "Salutation": "Mr.", "Name": "Victor Alvarez",
        "Email": "victor.alvarez@cascademedia.com", "Phone": "555-0601",
        "MobilePhone": "555-0602", "Title": "Regional Field Agent",
        "Department": "Field Operations", "AccountId": "CM-001",
        "AccountName": "Cascade Media Group", "MailingStreet": "202 Harbor Ave",
        "MailingCity": "Seattle", "MailingState": "WA",
        "MailingPostalCode": "98101", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-04-15T14:00:00Z",
        "LastModifiedDate": "2024-06-15T08:00:00Z",
        "Description": "Coordinates on-location shoots for the Pacific Northwest.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 7,
        "Password": "alvarez_field88",
    },
    {
        "Id": "0031A00001aBC007", "FirstName": "Gary", "LastName": "Mitchell",
        "Salutation": "Mr.", "Name": "Gary Mitchell",
        "Email": "gary.mitchell@apexsupply.com", "Phone": "555-0701",
        "MobilePhone": "555-0702", "Title": "Chief Product Tester",
        "Department": "R&D", "AccountId": "AI-001",
        "AccountName": "Apex Industrial Supply", "MailingStreet": "999 Industrial Pkwy",
        "MailingCity": "Phoenix", "MailingState": "AZ",
        "MailingPostalCode": "85001", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000003owner",
        "CreatedDate": "2023-05-01T10:00:00Z",
        "LastModifiedDate": "2024-08-01T12:00:00Z",
        "Description": "Runs durability testing on new product lines.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 42,
        "Password": "mitchell_test1",
    },
    {
        "Id": "0031A00001aBC008", "FirstName": "Ethan", "LastName": "Park",
        "Salutation": "Mr.", "Name": "Ethan Park",
        "Email": "ethan.park@apexsupply.com", "Phone": "555-0801",
        "MobilePhone": "555-0802", "Title": "Logistics Coordinator",
        "Department": "Logistics", "AccountId": "AI-001",
        "AccountName": "Apex Industrial Supply", "MailingStreet": "1001 Industrial Pkwy",
        "MailingCity": "Phoenix", "MailingState": "AZ",
        "MailingPostalCode": "85001", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000003owner",
        "CreatedDate": "2023-05-15T06:00:00Z",
        "LastModifiedDate": "2024-07-20T15:00:00Z",
        "Description": "Manages same-day dispatch for regional deliveries.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 0,
        "Password": "park_logistics!",
    },
    {
        "Id": "0031A00001aBC009", "FirstName": "Walter", "LastName": "Briggs",
        "Salutation": "Mr.", "Name": "Walter Briggs",
        "Email": "walter.briggs@riversideholdings.com", "Phone": "555-0901",
        "MobilePhone": "555-0902", "Title": "Director of Security",
        "Department": "Security", "AccountId": "RH-001",
        "AccountName": "Riverside Holdings", "MailingStreet": "50 Frontier Rd",
        "MailingCity": "Tombstone", "MailingState": "AZ",
        "MailingPostalCode": "85638", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-06-01T11:00:00Z",
        "LastModifiedDate": "2024-09-01T10:00:00Z",
        "Description": "Manages site security across all regional facilities.",
        "DoNotCall": 1, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 15,
        "Password": "briggs_secure77",
    },
    {
        "Id": "0031A00001aBC010", "FirstName": "Harold", "LastName": "Jennings",
        "Salutation": "Mr.", "Name": "Harold Jennings",
        "Email": "harold.jennings@riversideholdings.com", "Phone": "555-1001",
        "MobilePhone": "555-1002", "Title": "Chief Communications Officer",
        "Department": "Communications", "AccountId": "RH-001",
        "AccountName": "Riverside Holdings", "MailingStreet": "75 Heritage Blvd",
        "MailingCity": "Nashville", "MailingState": "TN",
        "MailingPostalCode": "37201", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-06-15T13:00:00Z",
        "LastModifiedDate": "2024-08-15T11:30:00Z",
        "Description": "Primary media contact for the Nashville office.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 4,
        "Password": "jennings_comm!",
    },
    {
        "Id": "0031A00001aBC011", "FirstName": "Nicole", "LastName": "Sanders",
        "Salutation": "Ms.", "Name": "Nicole Sanders",
        "Email": "nicole.sanders@cascademedia.com", "Phone": "555-1101",
        "MobilePhone": "555-1102", "Title": "Athletic Director",
        "Department": "Sports", "AccountId": "CM-001",
        "AccountName": "Cascade Media Group", "MailingStreet": "204 Harbor Ave",
        "MailingCity": "Seattle", "MailingState": "WA",
        "MailingPostalCode": "98101", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-07-01T09:00:00Z",
        "LastModifiedDate": "2024-09-10T14:00:00Z",
        "Description": "Oversees sponsorship coverage for regional sports events.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 1,
        "Password": "sanders_sport22",
    },
    {
        "Id": "0031A00001aBC012", "FirstName": "Marcus", "LastName": "Webb",
        "Salutation": "Mr.", "Name": "Marcus Webb",
        "Email": "marcus.webb@cascademedia.com", "Phone": "555-1201",
        "MobilePhone": "555-1202", "Title": "Demolition Specialist",
        "Department": "Operations", "AccountId": "CM-001",
        "AccountName": "Cascade Media Group", "MailingStreet": "206 Harbor Ave",
        "MailingCity": "Seattle", "MailingState": "WA",
        "MailingPostalCode": "98101", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-07-20T07:30:00Z",
        "LastModifiedDate": "2024-10-01T08:00:00Z",
        "Description": "Handles teardown and set removal after productions.",
        "DoNotCall": 1, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 20,
        "Password": "webb_ops2023",
    },
    {
        "Id": "0031A00001aBC013", "FirstName": "Oliver", "LastName": "Grant",
        "Salutation": "Mr.", "Name": "Oliver Grant",
        "Email": "oliver.grant@novatech.com", "Phone": "555-1301",
        "MobilePhone": "555-1302", "Title": "Senior Strategy Analyst",
        "Department": "Strategy", "AccountId": "NT-001",
        "AccountName": "Nova Technologies", "MailingStreet": "1 Innovation Way",
        "MailingCity": "Austin", "MailingState": "TX",
        "MailingPostalCode": "73301", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000005owner",
        "CreatedDate": "2023-08-01T00:00:00Z",
        "LastModifiedDate": "2024-11-01T00:00:00Z",
        "Description": "Leads competitive analysis for the product roadmap.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 9,
        "Password": "grant_strategy!",
    },
    {
        "Id": "0031A00001aBC014", "FirstName": "Philippe", "LastName": "Moreau",
        "Salutation": "Mr.", "Name": "Philippe Moreau",
        "Email": "philippe.moreau@riversideholdings.com", "Phone": "555-1401",
        "MobilePhone": "555-1402", "Title": "Fragrance Consultant",
        "Department": "Marketing", "AccountId": "RH-001",
        "AccountName": "Riverside Holdings", "MailingStreet": "22 Rue de Commerce",
        "MailingCity": "Paris", "MailingState": "IDF",
        "MailingPostalCode": "75001", "MailingCountry": "FR",
        "LeadSource": "Referral", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-08-15T16:00:00Z",
        "LastModifiedDate": "2024-10-15T17:00:00Z",
        "Description": "Manages the European fragrance product line.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 6,
        "Password": "moreau_paris44",
    },
    {
        "Id": "0031A00001aBC015", "FirstName": "Mateo", "LastName": "Fernandez",
        "Salutation": "Mr.", "Name": "Mateo Fernandez",
        "Email": "mateo.fernandez@riversideholdings.com", "Phone": "555-1501",
        "MobilePhone": "555-1502", "Title": "Express Delivery Manager",
        "Department": "Logistics", "AccountId": "RH-001",
        "AccountName": "Riverside Holdings", "MailingStreet": "88 Avenida Central",
        "MailingCity": "Mexico City", "MailingState": "CDMX",
        "MailingPostalCode": "06600", "MailingCountry": "MX",
        "LeadSource": "Event", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-09-01T08:00:00Z",
        "LastModifiedDate": "2024-11-15T09:00:00Z",
        "Description": "Runs the rapid-delivery fleet for the Mexico City hub.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 0,
        "Password": "fernandez_exp!",
    },
    {
        "Id": "0031A00001aBC016", "FirstName": "Eleanor", "LastName": "Webster",
        "Salutation": "Mrs.", "Name": "Eleanor Webster",
        "Email": "eleanor.webster@cascademedia.com", "Phone": "555-1601",
        "MobilePhone": "555-1602", "Title": "Senior Advisor",
        "Department": "Executive", "AccountId": "CM-001",
        "AccountName": "Cascade Media Group", "MailingStreet": "208 Harbor Ave",
        "MailingCity": "Seattle", "MailingState": "WA",
        "MailingPostalCode": "98101", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-09-15T10:00:00Z",
        "LastModifiedDate": "2024-12-01T11:00:00Z",
        "Description": "Trusted advisor to the executive team for two decades.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 3,
        "Password": "webster_adv88",
    },
    {
        "Id": "0031A00001aBC017", "FirstName": "Gregory", "LastName": "Fontaine",
        "Salutation": "Mr.", "Name": "Gregory Fontaine",
        "Email": "gregory.fontaine@cascademedia.com", "Phone": "555-1701",
        "MobilePhone": "555-1702", "Title": "Entertainment Director",
        "Department": "Entertainment", "AccountId": "CM-001",
        "AccountName": "Cascade Media Group", "MailingStreet": "210 Harbor Ave",
        "MailingCity": "Seattle", "MailingState": "WA",
        "MailingPostalCode": "98101", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-10-01T12:00:00Z",
        "LastModifiedDate": "2025-01-01T12:00:00Z",
        "Description": "Books live entertainment for company events.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 1,
        "Password": "fontaine_ent66",
    },
    {
        "Id": "0031A00001aBC018", "FirstName": "Camille", "LastName": "Dupont",
        "Salutation": "Ms.", "Name": "Camille Dupont",
        "Email": "camille.dupont@riversideholdings.com", "Phone": "555-1801",
        "MobilePhone": "555-1802", "Title": "Brand Ambassador",
        "Department": "Marketing", "AccountId": "RH-001",
        "AccountName": "Riverside Holdings", "MailingStreet": "33 Rue de la Paix",
        "MailingCity": "Paris", "MailingState": "IDF",
        "MailingPostalCode": "75002", "MailingCountry": "FR",
        "LeadSource": "Referral", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-10-15T14:00:00Z",
        "LastModifiedDate": "2025-01-15T15:00:00Z",
        "Description": "Represents the brand at European trade shows.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 2,
        "Password": "dupont_brand!",
    },
    {
        "Id": "0031A00001aBC019", "FirstName": "Bruce", "LastName": "Sullivan",
        "Salutation": "Mr.", "Name": "Bruce Sullivan",
        "Email": "bruce.sullivan@novatech.com", "Phone": "555-1901",
        "MobilePhone": "555-1902", "Title": "Physical Security Lead",
        "Department": "Security", "AccountId": "NT-001",
        "AccountName": "Nova Technologies", "MailingStreet": "3 Innovation Way",
        "MailingCity": "Austin", "MailingState": "TX",
        "MailingPostalCode": "73301", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000005owner",
        "CreatedDate": "2023-11-01T06:00:00Z",
        "LastModifiedDate": "2025-02-01T07:00:00Z",
        "Description": "Manages badge access and site patrols for the campus.",
        "DoNotCall": 1, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 11,
        "Password": "sullivan_sec11",
    },
    {
        "Id": "0031A00001aBC020", "FirstName": "Diane", "LastName": "Coleman",
        "Salutation": "Ms.", "Name": "Diane Coleman",
        "Email": "diane.coleman@novatech.com", "Phone": "555-2001",
        "MobilePhone": "555-2002", "Title": "Product Development Lead",
        "Department": "R&D", "AccountId": "NT-001",
        "AccountName": "Nova Technologies", "MailingStreet": "5 Innovation Way",
        "MailingCity": "Austin", "MailingState": "TX",
        "MailingPostalCode": "73301", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000005owner",
        "CreatedDate": "2023-11-15T18:00:00Z",
        "LastModifiedDate": "2025-02-15T19:00:00Z",
        "Description": "Leads the early-stage prototyping team.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 6,
        "Password": "coleman_dev24",
    },
]


class ContactDatabaseManager:
    """
    Manages SQLite database operations for mock customer contact profiles.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "contacts.db"):
        """
        Initialize the ContactDatabaseManager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def init_db(self) -> None:
        """
        Initialize the contacts database and seed data if empty.

        Creates the ``contacts`` table from ``schema.sql`` if it does not
        exist, then calls ``seed_contacts()`` to populate with sample data
        when the table is empty. ``Email`` is declared ``UNIQUE COLLATE
        NOCASE`` in the schema so two contacts can never share a login
        email, matching the case-insensitive lookup used by
        ``authenticate()`` and the ``search_by_email`` tool.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA_PATH.read_text())
            conn.commit()
            self.seed_contacts(conn)
        finally:
            conn.close()

    def seed_contacts(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Seed the contacts table with sample data if it is empty.

        Seed passwords are stored as PBKDF2 hashes (see ``_hash_password``),
        never in plaintext, even though ``_SEED_CONTACTS`` lists them in
        plaintext for readability as demo credentials.

        Args:
            conn: Optional existing database connection. If ``None``,
                  a new connection is opened and closed automatically.
        """
        close = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            close = True
        try:
            row = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()
            if row[0] == 0:
                placeholders = ", ".join("?" for _ in _CONTACT_COLUMNS)
                col_names = ", ".join(_CONTACT_COLUMNS)
                for contact in _SEED_CONTACTS:
                    values = [
                        _hash_password(contact[col]) if col == "Password" else contact[col]
                        for col in _CONTACT_COLUMNS
                    ]
                    conn.execute(
                        f"INSERT INTO contacts ({col_names}) VALUES ({placeholders})",
                        values,
                    )
                conn.commit()
        finally:
            if close:
                conn.close()

    def _rows_to_dicts(self, cursor: sqlite3.Cursor) -> list[dict]:
        """Convert cursor results to a list of dicts, excluding the Password column."""
        columns = [desc[0] for desc in cursor.description]
        return [
            {k: v for k, v in zip(columns, row) if k != "Password"}
            for row in cursor.fetchall()
        ]

    def search_by_last_name(self, last_name: str) -> list[dict]:
        """
        Search contacts by last name using case-insensitive partial match.

        Args:
            last_name: Partial or full last name to search for.

        Returns:
            List of matching contact dicts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM contacts WHERE LastName LIKE ? COLLATE NOCASE",
                (f"%{last_name}%",),
            )
            return self._rows_to_dicts(cursor)
        finally:
            conn.close()

    def search_by_email(self, email: str) -> list[dict]:
        """
        Search contacts by email using case-insensitive exact match.

        Args:
            email: Email address to search for.

        Returns:
            List of matching contact dicts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM contacts WHERE Email = ? COLLATE NOCASE",
                (email,),
            )
            return self._rows_to_dicts(cursor)
        finally:
            conn.close()

    def search_by_account_id(self, account_id: str) -> list[dict]:
        """
        Search contacts by account ID using exact match.

        Args:
            account_id: Account ID to search for.

        Returns:
            List of matching contact dicts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM contacts WHERE AccountId = ?",
                (account_id,),
            )
            return self._rows_to_dicts(cursor)
        finally:
            conn.close()

    def search_by_department(self, department: str) -> list[dict]:
        """
        Search contacts by department using case-insensitive partial match.

        Args:
            department: Partial or full department name to search for.

        Returns:
            List of matching contact dicts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM contacts WHERE Department LIKE ? COLLATE NOCASE",
                (f"%{department}%",),
            )
            return self._rows_to_dicts(cursor)
        finally:
            conn.close()

    def authenticate(self, email: str, password: str) -> Optional[dict]:
        """
        Authenticate a contact by email and password.

        Args:
            email: Contact email address.
            password: Contact password.

        Returns:
            Contact dict (without ``Password`` field) on success, ``None`` on failure.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM contacts WHERE Email = ? COLLATE NOCASE",
                (email,),
            )
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row is None:
                return None
            record = dict(zip(columns, row))
            stored_hash = record.pop("Password", None)
            if not stored_hash or not _verify_password(password, stored_hash):
                return None
            return record
        finally:
            conn.close()
