"""
Database management for mock customer contact profiles.

Provides a SQLite-backed store of Salesforce-style contact records
seeded with 20 Warner Bros. cartoon characters on first run.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import sqlite3
from typing import Optional


_CONTACT_COLUMNS = [
    "Id", "FirstName", "LastName", "Salutation", "Name", "Email", "Phone",
    "MobilePhone", "Title", "Department", "AccountId", "AccountName",
    "MailingStreet", "MailingCity", "MailingState", "MailingPostalCode",
    "MailingCountry", "LeadSource", "OwnerId", "CreatedDate",
    "LastModifiedDate", "Description", "DoNotCall", "HasOptedOutOfEmail",
    "IsDeleted", "ContactSource", "CaseCount", "Password",
]

_SEED_CONTACTS = [
    {
        "Id": "0031A00001aBC001", "FirstName": "Bugs", "LastName": "Bunny",
        "Salutation": "Mr.", "Name": "Bugs Bunny",
        "Email": "bugs.bunny@acme.com", "Phone": "555-0101",
        "MobilePhone": "555-0102", "Title": "Chief Carrot Officer",
        "Department": "Executive", "AccountId": "ACME-001",
        "AccountName": "ACME Corporation", "MailingStreet": "123 Rabbit Hole Ln",
        "MailingCity": "Burbank", "MailingState": "CA",
        "MailingPostalCode": "91505", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-01-15T10:30:00Z",
        "LastModifiedDate": "2024-06-01T14:00:00Z",
        "Description": "Top performer, loves carrots.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 5,
        "Password": "password123",
    },
    {
        "Id": "0031A00001aBC002", "FirstName": "Daffy", "LastName": "Duck",
        "Salutation": "Mr.", "Name": "Daffy Duck",
        "Email": "daffy.duck@acme.com", "Phone": "555-0201",
        "MobilePhone": "555-0202", "Title": "VP of Mischief",
        "Department": "Marketing", "AccountId": "ACME-001",
        "AccountName": "ACME Corporation", "MailingStreet": "456 Pond Ave",
        "MailingCity": "Burbank", "MailingState": "CA",
        "MailingPostalCode": "91505", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-02-10T09:00:00Z",
        "LastModifiedDate": "2024-05-20T11:30:00Z",
        "Description": "Enthusiastic but unpredictable.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 12,
        "Password": "daffy_quack99",
    },
    {
        "Id": "0031A00001aBC003", "FirstName": "Porky", "LastName": "Pig",
        "Salutation": "Mr.", "Name": "Porky Pig",
        "Email": "porky.pig@acme.com", "Phone": "555-0301",
        "MobilePhone": "555-0302", "Title": "Senior Stuttering Specialist",
        "Department": "Communications", "AccountId": "ACME-001",
        "AccountName": "ACME Corporation", "MailingStreet": "789 Farm Rd",
        "MailingCity": "Burbank", "MailingState": "CA",
        "MailingPostalCode": "91505", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-03-05T08:15:00Z",
        "LastModifiedDate": "2024-04-10T16:45:00Z",
        "Description": "Th-th-that's all folks!",
        "DoNotCall": 1, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 3,
        "Password": "porky_pig123",
    },
    {
        "Id": "0031A00001aBC004", "FirstName": "Elmer", "LastName": "Fudd",
        "Salutation": "Mr.", "Name": "Elmer Fudd",
        "Email": "elmer.fudd@acme.com", "Phone": "555-0401",
        "MobilePhone": "555-0402", "Title": "Head of Hunting Operations",
        "Department": "Field Ops", "AccountId": "ACME-001",
        "AccountName": "ACME Corporation", "MailingStreet": "321 Shotgun Blvd",
        "MailingCity": "Burbank", "MailingState": "CA",
        "MailingPostalCode": "91505", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000001owner",
        "CreatedDate": "2023-03-20T07:00:00Z",
        "LastModifiedDate": "2024-03-15T10:00:00Z",
        "Description": "Be vewy vewy quiet.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 8,
        "Password": "wabbit_season!",
    },
    {
        "Id": "0031A00001aBC005", "FirstName": "Tweety", "LastName": "Bird",
        "Salutation": "Ms.", "Name": "Tweety Bird",
        "Email": "tweety.bird@wbstudios.com", "Phone": "555-0501",
        "MobilePhone": "555-0502", "Title": "Canary Consultant",
        "Department": "Intelligence", "AccountId": "WB-001",
        "AccountName": "WB Studios", "MailingStreet": "100 Birdcage Walk",
        "MailingCity": "Hollywood", "MailingState": "CA",
        "MailingPostalCode": "90028", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-04-01T12:00:00Z",
        "LastModifiedDate": "2024-07-01T09:30:00Z",
        "Description": "I tawt I taw a puddy tat!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 2,
        "Password": "tweety_fly55",
    },
    {
        "Id": "0031A00001aBC006", "FirstName": "Sylvester", "LastName": "Cat",
        "Salutation": "Mr.", "Name": "Sylvester Cat",
        "Email": "sylvester.cat@wbstudios.com", "Phone": "555-0601",
        "MobilePhone": "555-0602", "Title": "Feline Field Agent",
        "Department": "Intelligence", "AccountId": "WB-001",
        "AccountName": "WB Studios", "MailingStreet": "101 Alley Way",
        "MailingCity": "Hollywood", "MailingState": "CA",
        "MailingPostalCode": "90028", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-04-15T14:00:00Z",
        "LastModifiedDate": "2024-06-15T08:00:00Z",
        "Description": "Sufferin' succotash!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 7,
        "Password": "sylvester_pounce!",
    },
    {
        "Id": "0031A00001aBC007", "FirstName": "Wile E.", "LastName": "Coyote",
        "Salutation": "Mr.", "Name": "Wile E. Coyote",
        "Email": "wile.coyote@acmeproducts.com", "Phone": "555-0701",
        "MobilePhone": "555-0702", "Title": "Chief Product Tester",
        "Department": "R&D", "AccountId": "AP-001",
        "AccountName": "ACME Products", "MailingStreet": "999 Desert Hwy",
        "MailingCity": "Phoenix", "MailingState": "AZ",
        "MailingPostalCode": "85001", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000003owner",
        "CreatedDate": "2023-05-01T10:00:00Z",
        "LastModifiedDate": "2024-08-01T12:00:00Z",
        "Description": "Super genius. Product returns frequent.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 42,
        "Password": "genius_coyote1",
    },
    {
        "Id": "0031A00001aBC008", "FirstName": "Road", "LastName": "Runner",
        "Salutation": "Mr.", "Name": "Road Runner",
        "Email": "road.runner@acmeproducts.com", "Phone": "555-0801",
        "MobilePhone": "555-0802", "Title": "Speed Specialist",
        "Department": "Logistics", "AccountId": "AP-001",
        "AccountName": "ACME Products", "MailingStreet": "1 Fast Lane",
        "MailingCity": "Phoenix", "MailingState": "AZ",
        "MailingPostalCode": "85001", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000003owner",
        "CreatedDate": "2023-05-15T06:00:00Z",
        "LastModifiedDate": "2024-07-20T15:00:00Z",
        "Description": "Meep meep!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 0,
        "Password": "meepmeep_fast!",
    },
    {
        "Id": "0031A00001aBC009", "FirstName": "Yosemite", "LastName": "Sam",
        "Salutation": "Mr.", "Name": "Yosemite Sam",
        "Email": "yosemite.sam@toontown.com", "Phone": "555-0901",
        "MobilePhone": "555-0902", "Title": "Director of Security",
        "Department": "Security", "AccountId": "TT-001",
        "AccountName": "Toontown Inc", "MailingStreet": "50 Gunslinger Rd",
        "MailingCity": "Tombstone", "MailingState": "AZ",
        "MailingPostalCode": "85638", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-06-01T11:00:00Z",
        "LastModifiedDate": "2024-09-01T10:00:00Z",
        "Description": "Great horny toads!",
        "DoNotCall": 1, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 15,
        "Password": "yosemite_bang77",
    },
    {
        "Id": "0031A00001aBC010", "FirstName": "Foghorn", "LastName": "Leghorn",
        "Salutation": "Mr.", "Name": "Foghorn Leghorn",
        "Email": "foghorn.leghorn@toontown.com", "Phone": "555-1001",
        "MobilePhone": "555-1002", "Title": "Chief Communications Officer",
        "Department": "Communications", "AccountId": "TT-001",
        "AccountName": "Toontown Inc", "MailingStreet": "75 Barnyard Blvd",
        "MailingCity": "Nashville", "MailingState": "TN",
        "MailingPostalCode": "37201", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-06-15T13:00:00Z",
        "LastModifiedDate": "2024-08-15T11:30:00Z",
        "Description": "I say, I say, boy!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 4,
        "Password": "foghorn_rooster!",
    },
    {
        "Id": "0031A00001aBC011", "FirstName": "Lola", "LastName": "Bunny",
        "Salutation": "Ms.", "Name": "Lola Bunny",
        "Email": "lola.bunny@wbstudios.com", "Phone": "555-1101",
        "MobilePhone": "555-1102", "Title": "Athletic Director",
        "Department": "Sports", "AccountId": "WB-001",
        "AccountName": "WB Studios", "MailingStreet": "200 Slam Dunk Dr",
        "MailingCity": "Hollywood", "MailingState": "CA",
        "MailingPostalCode": "90028", "MailingCountry": "US",
        "LeadSource": "Event", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-07-01T09:00:00Z",
        "LastModifiedDate": "2024-09-10T14:00:00Z",
        "Description": "Don't call me doll.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 1,
        "Password": "lola_slam22",
    },
    {
        "Id": "0031A00001aBC012", "FirstName": "Tasmanian", "LastName": "Devil",
        "Salutation": "Mr.", "Name": "Tasmanian Devil",
        "Email": "taz.devil@wbstudios.com", "Phone": "555-1201",
        "MobilePhone": "555-1202", "Title": "Demolition Specialist",
        "Department": "Operations", "AccountId": "WB-001",
        "AccountName": "WB Studios", "MailingStreet": "303 Tornado Alley",
        "MailingCity": "Hollywood", "MailingState": "CA",
        "MailingPostalCode": "90028", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-07-20T07:30:00Z",
        "LastModifiedDate": "2024-10-01T08:00:00Z",
        "Description": "Blarghargharg!",
        "DoNotCall": 1, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 20,
        "Password": "taz_spin2023",
    },
    {
        "Id": "0031A00001aBC013", "FirstName": "Marvin", "LastName": "Martian",
        "Salutation": "Mr.", "Name": "Marvin Martian",
        "Email": "marvin.martian@marstech.com", "Phone": "555-1301",
        "MobilePhone": "555-1302", "Title": "Intergalactic Strategist",
        "Department": "Strategy", "AccountId": "MT-001",
        "AccountName": "Mars Technologies", "MailingStreet": "1 Crater Ct",
        "MailingCity": "Olympus Mons", "MailingState": "MR",
        "MailingPostalCode": "00001", "MailingCountry": "Mars",
        "LeadSource": "Web", "OwnerId": "0051A000005owner",
        "CreatedDate": "2023-08-01T00:00:00Z",
        "LastModifiedDate": "2024-11-01T00:00:00Z",
        "Description": "Where's the kaboom?",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 9,
        "Password": "marvin_kaboom!",
    },
    {
        "Id": "0031A00001aBC014", "FirstName": "Pepe", "LastName": "Le Pew",
        "Salutation": "Mr.", "Name": "Pepe Le Pew",
        "Email": "pepe.lepew@toontown.com", "Phone": "555-1401",
        "MobilePhone": "555-1402", "Title": "Fragrance Consultant",
        "Department": "Marketing", "AccountId": "TT-001",
        "AccountName": "Toontown Inc", "MailingStreet": "22 Parfum Pl",
        "MailingCity": "Paris", "MailingState": "IDF",
        "MailingPostalCode": "75001", "MailingCountry": "FR",
        "LeadSource": "Referral", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-08-15T16:00:00Z",
        "LastModifiedDate": "2024-10-15T17:00:00Z",
        "Description": "Ah, l'amour!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 6,
        "Password": "pepe_amour44",
    },
    {
        "Id": "0031A00001aBC015", "FirstName": "Speedy", "LastName": "Gonzales",
        "Salutation": "Mr.", "Name": "Speedy Gonzales",
        "Email": "speedy.gonzales@toontown.com", "Phone": "555-1501",
        "MobilePhone": "555-1502", "Title": "Express Delivery Manager",
        "Department": "Logistics", "AccountId": "TT-001",
        "AccountName": "Toontown Inc", "MailingStreet": "88 Rapido St",
        "MailingCity": "Mexico City", "MailingState": "CDMX",
        "MailingPostalCode": "06600", "MailingCountry": "MX",
        "LeadSource": "Event", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-09-01T08:00:00Z",
        "LastModifiedDate": "2024-11-15T09:00:00Z",
        "Description": "Arriba! Arriba! Andale! Andale!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 0,
        "Password": "speedy_arriba!",
    },
    {
        "Id": "0031A00001aBC016", "FirstName": "Granny", "LastName": "Webster",
        "Salutation": "Mrs.", "Name": "Granny Webster",
        "Email": "granny.webster@wbstudios.com", "Phone": "555-1601",
        "MobilePhone": "555-1602", "Title": "Senior Advisor",
        "Department": "Executive", "AccountId": "WB-001",
        "AccountName": "WB Studios", "MailingStreet": "44 Knitting Ln",
        "MailingCity": "Hollywood", "MailingState": "CA",
        "MailingPostalCode": "90028", "MailingCountry": "US",
        "LeadSource": "Referral", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-09-15T10:00:00Z",
        "LastModifiedDate": "2024-12-01T11:00:00Z",
        "Description": "Don't mess with Granny.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 3,
        "Password": "granny_tough88",
    },
    {
        "Id": "0031A00001aBC017", "FirstName": "Michigan J.", "LastName": "Frog",
        "Salutation": "Mr.", "Name": "Michigan J. Frog",
        "Email": "michigan.frog@wbstudios.com", "Phone": "555-1701",
        "MobilePhone": "555-1702", "Title": "Entertainment Director",
        "Department": "Entertainment", "AccountId": "WB-001",
        "AccountName": "WB Studios", "MailingStreet": "55 Lily Pad Ct",
        "MailingCity": "Hollywood", "MailingState": "CA",
        "MailingPostalCode": "90028", "MailingCountry": "US",
        "LeadSource": "Web", "OwnerId": "0051A000002owner",
        "CreatedDate": "2023-10-01T12:00:00Z",
        "LastModifiedDate": "2025-01-01T12:00:00Z",
        "Description": "Hello my baby, hello my honey!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 1, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 1,
        "Password": "michigan_sing66",
    },
    {
        "Id": "0031A00001aBC018", "FirstName": "Penelope", "LastName": "Pussycat",
        "Salutation": "Ms.", "Name": "Penelope Pussycat",
        "Email": "penelope.pussycat@toontown.com", "Phone": "555-1801",
        "MobilePhone": "555-1802", "Title": "Brand Ambassador",
        "Department": "Marketing", "AccountId": "TT-001",
        "AccountName": "Toontown Inc", "MailingStreet": "33 Catwalk Ave",
        "MailingCity": "Paris", "MailingState": "IDF",
        "MailingPostalCode": "75002", "MailingCountry": "FR",
        "LeadSource": "Referral", "OwnerId": "0051A000004owner",
        "CreatedDate": "2023-10-15T14:00:00Z",
        "LastModifiedDate": "2025-01-15T15:00:00Z",
        "Description": "Silent but effective.",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Partner", "CaseCount": 2,
        "Password": "penelope_meow!",
    },
    {
        "Id": "0031A00001aBC019", "FirstName": "Gossamer", "LastName": "Monster",
        "Salutation": "Mr.", "Name": "Gossamer Monster",
        "Email": "gossamer.monster@marstech.com", "Phone": "555-1901",
        "MobilePhone": "555-1902", "Title": "Physical Security Lead",
        "Department": "Security", "AccountId": "MT-001",
        "AccountName": "Mars Technologies", "MailingStreet": "666 Hairy Beast Rd",
        "MailingCity": "Olympus Mons", "MailingState": "MR",
        "MailingPostalCode": "00002", "MailingCountry": "Mars",
        "LeadSource": "Web", "OwnerId": "0051A000005owner",
        "CreatedDate": "2023-11-01T06:00:00Z",
        "LastModifiedDate": "2025-02-01T07:00:00Z",
        "Description": "Big, red, and hairy.",
        "DoNotCall": 1, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Inbound", "CaseCount": 11,
        "Password": "gossamer_smash!",
    },
    {
        "Id": "0031A00001aBC020", "FirstName": "Witch", "LastName": "Hazel",
        "Salutation": "Ms.", "Name": "Witch Hazel",
        "Email": "witch.hazel@marstech.com", "Phone": "555-2001",
        "MobilePhone": "555-2002", "Title": "Potion Development Lead",
        "Department": "R&D", "AccountId": "MT-001",
        "AccountName": "Mars Technologies", "MailingStreet": "13 Cauldron Ct",
        "MailingCity": "Olympus Mons", "MailingState": "MR",
        "MailingPostalCode": "00003", "MailingCountry": "Mars",
        "LeadSource": "Event", "OwnerId": "0051A000005owner",
        "CreatedDate": "2023-11-15T18:00:00Z",
        "LastModifiedDate": "2025-02-15T19:00:00Z",
        "Description": "Hehehehe! A visitor!",
        "DoNotCall": 0, "HasOptedOutOfEmail": 0, "IsDeleted": 0,
        "ContactSource": "Event", "CaseCount": 6,
        "Password": "hazel_brew2024",
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

        Creates the ``contacts`` table if it does not exist, then calls
        ``seed_contacts()`` to populate with sample data when the table
        is empty.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            columns_sql = ", ".join(f"{col} TEXT" for col in _CONTACT_COLUMNS)
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS contacts "
                f"(rowid INTEGER PRIMARY KEY AUTOINCREMENT, {columns_sql})"
            )
            conn.commit()
            self.seed_contacts(conn)
        finally:
            conn.close()

    def seed_contacts(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Seed the contacts table with sample data if it is empty.

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
                    values = [contact[col] for col in _CONTACT_COLUMNS]
                    conn.execute(
                        f"INSERT INTO contacts ({col_names}) VALUES ({placeholders})",
                        values,
                    )
                conn.commit()
        finally:
            if close:
                conn.close()

    def _rows_to_dicts(self, cursor: sqlite3.Cursor) -> list[dict]:
        """Convert cursor results to a list of dicts."""
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

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
                "SELECT * FROM contacts WHERE Email = ? COLLATE NOCASE AND Password = ?",
                (email, password),
            )
            results = self._rows_to_dicts(cursor)
            if not results:
                return None
            contact = results[0]
            contact.pop("Password", None)
            return contact
        finally:
            conn.close()
