"""
Database management for the mock "Acme Support" retail backend.

Provides a SQLite-backed store of customer orders (seeded with a small,
fixed set of orders in every lifecycle state), plus return requests and
support tickets. Used by ``acme_api.py`` to give Artemis learning-guide
labs a realistic, publicly reachable order/returns/tickets API.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Optional


_ORDER_COLUMNS = [
    "OrderId", "CustomerName", "CustomerEmail", "Status", "OrderDate",
    "Carrier", "TrackingNumber", "EstimatedDelivery", "DeliveredDate",
    "Items", "Total", "ReturnWindowDays",
]

# Fixed seed data. Dates are absolute so lab "You should see" output is
# stable; return eligibility is computed against DeliveredDate + window.
_SEED_ORDERS = [
    {
        "OrderId": "ACM-1001", "CustomerName": "Maria Lopez",
        "CustomerEmail": "maria.lopez@example.com", "Status": "processing",
        "OrderDate": "2026-10-05", "Carrier": "", "TrackingNumber": "",
        "EstimatedDelivery": "2026-10-12", "DeliveredDate": "",
        "Items": [{"sku": "HP-200", "name": "Wireless Headphones", "qty": 1, "price": 89.99}],
        "Total": 89.99, "ReturnWindowDays": 30,
    },
    {
        "OrderId": "ACM-1002", "CustomerName": "Maria Lopez",
        "CustomerEmail": "maria.lopez@example.com", "Status": "shipped",
        "OrderDate": "2026-10-01", "Carrier": "UPS",
        "TrackingNumber": "1Z999AA10123456784", "EstimatedDelivery": "2026-10-09",
        "DeliveredDate": "",
        "Items": [{"sku": "KB-310", "name": "Mechanical Keyboard", "qty": 1, "price": 129.00}],
        "Total": 129.00, "ReturnWindowDays": 30,
    },
    {
        "OrderId": "ACM-1003", "CustomerName": "James Chen",
        "CustomerEmail": "james.chen@example.com", "Status": "out_for_delivery",
        "OrderDate": "2026-09-30", "Carrier": "FedEx",
        "TrackingNumber": "612999AA1012", "EstimatedDelivery": "2026-10-07",
        "DeliveredDate": "",
        "Items": [
            {"sku": "MS-120", "name": "Ergonomic Mouse", "qty": 1, "price": 49.50},
            {"sku": "PD-050", "name": "Desk Pad", "qty": 2, "price": 15.00},
        ],
        "Total": 79.50, "ReturnWindowDays": 30,
    },
    {
        "OrderId": "ACM-1004", "CustomerName": "James Chen",
        "CustomerEmail": "james.chen@example.com", "Status": "delivered",
        "OrderDate": "2026-09-20", "Carrier": "USPS",
        "TrackingNumber": "9400111899223344556677", "EstimatedDelivery": "2026-09-25",
        "DeliveredDate": "2026-09-25",
        "Items": [{"sku": "MN-270", "name": "27-inch Monitor", "qty": 1, "price": 249.99}],
        "Total": 249.99, "ReturnWindowDays": 30,
    },
    {
        "OrderId": "ACM-1005", "CustomerName": "Aisha Patel",
        "CustomerEmail": "aisha.patel@example.com", "Status": "delivered",
        "OrderDate": "2026-07-28", "Carrier": "UPS",
        "TrackingNumber": "1Z999AA10198765432", "EstimatedDelivery": "2026-08-02",
        "DeliveredDate": "2026-08-02",
        "Items": [{"sku": "CH-900", "name": "Office Chair", "qty": 1, "price": 399.00}],
        "Total": 399.00, "ReturnWindowDays": 30,
    },
    {
        "OrderId": "ACM-1006", "CustomerName": "Aisha Patel",
        "CustomerEmail": "aisha.patel@example.com", "Status": "cancelled",
        "OrderDate": "2026-09-15", "Carrier": "", "TrackingNumber": "",
        "EstimatedDelivery": "", "DeliveredDate": "",
        "Items": [{"sku": "LT-015", "name": "Desk Lamp", "qty": 1, "price": 34.99}],
        "Total": 34.99, "ReturnWindowDays": 30,
    },
]

# Orders with special behavior for the reliability labs (see acme_api.py).
SIMULATED_SLOW_ORDER = "ACM-1099"
SIMULATED_DOWN_ORDER = "ACM-1098"
SIMULATED_FLAKY_ORDER = "ACM-1097"


class AcmeDatabaseManager:
    """
    Manages SQLite database operations for the mock Acme retail backend.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "acme.db"):
        """
        Initialize the AcmeDatabaseManager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def init_db(self) -> None:
        """
        Create the ``orders``, ``returns`` and ``tickets`` tables if needed
        and seed the orders table when it is empty.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            columns_sql = ", ".join(f"{col} TEXT" for col in _ORDER_COLUMNS)
            conn.execute(f"CREATE TABLE IF NOT EXISTS orders ({columns_sql})")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS returns ("
                "ReturnId INTEGER PRIMARY KEY AUTOINCREMENT, "
                "OrderId TEXT, Reason TEXT, Status TEXT, CreatedAt TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tickets ("
                "TicketId INTEGER PRIMARY KEY AUTOINCREMENT, "
                "CustomerEmail TEXT, Subject TEXT, Description TEXT, "
                "Priority TEXT, Status TEXT, CreatedAt TEXT)"
            )
            conn.commit()
            self.seed_orders(conn)
        finally:
            conn.close()

    def seed_orders(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Seed the orders table with sample data if it is empty.

        Args:
            conn: Optional existing database connection. If ``None``,
                  a new connection is opened and closed automatically.
        """
        close = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            close = True
        try:
            row = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
            if row[0] == 0:
                placeholders = ", ".join("?" for _ in _ORDER_COLUMNS)
                col_names = ", ".join(_ORDER_COLUMNS)
                for order in _SEED_ORDERS:
                    values = [
                        json.dumps(order[col]) if col == "Items" else str(order[col])
                        for col in _ORDER_COLUMNS
                    ]
                    conn.execute(
                        f"INSERT INTO orders ({col_names}) VALUES ({placeholders})",
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

    @staticmethod
    def _return_eligibility(row: dict, today: date) -> tuple[bool, str]:
        """Compute whether an order can be returned today, and why (not)."""
        if row["Status"] != "delivered" or not row["DeliveredDate"]:
            return False, ""
        delivered = date.fromisoformat(row["DeliveredDate"])
        window = int(row["ReturnWindowDays"])
        deadline = date.fromordinal(delivered.toordinal() + window)
        return today <= deadline, deadline.isoformat()

    def _row_to_order_dict(self, row: dict, today: Optional[date] = None) -> dict:
        """Convert a stored order row to the public API shape."""
        today = today or datetime.now(timezone.utc).date()
        eligible, deadline = self._return_eligibility(row, today)
        return {
            "order_id": row["OrderId"],
            "customer_name": row["CustomerName"],
            "customer_email": row["CustomerEmail"],
            "status": row["Status"],
            "order_date": row["OrderDate"],
            "carrier": row["Carrier"] or None,
            "tracking_number": row["TrackingNumber"] or None,
            "estimated_delivery": row["EstimatedDelivery"] or None,
            "delivered_date": row["DeliveredDate"] or None,
            "items": json.loads(row["Items"]),
            "total": float(row["Total"]),
            "return_eligible": eligible,
            "return_deadline": deadline or None,
        }

    def get_order(self, order_id: str, today: Optional[date] = None) -> Optional[dict]:
        """
        Look up one order by ID (case-insensitive).

        Args:
            order_id: Order ID such as ``ACM-1002``.
            today: Override "today" for return-eligibility math (tests).

        Returns:
            An order dict, or ``None`` if no matching order exists.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM orders WHERE OrderId = ? COLLATE NOCASE",
                (order_id.strip(),),
            )
            results = self._rows_to_dicts(cursor)
            return self._row_to_order_dict(results[0], today) if results else None
        finally:
            conn.close()

    def list_orders_by_email(self, email: str, today: Optional[date] = None) -> list[dict]:
        """
        List every order for a customer email (case-insensitive exact match).

        Args:
            email: Customer email address.
            today: Override "today" for return-eligibility math (tests).

        Returns:
            A (possibly empty) list of order dicts, newest first.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM orders WHERE CustomerEmail = ? COLLATE NOCASE "
                "ORDER BY OrderDate DESC",
                (email.strip(),),
            )
            return [self._row_to_order_dict(r, today) for r in self._rows_to_dicts(cursor)]
        finally:
            conn.close()

    def create_return(
        self, order_id: str, reason: str, today: Optional[date] = None
    ) -> dict:
        """
        Open a return for an order if it is eligible.

        Args:
            order_id: Order to return.
            reason: Customer's reason for the return.
            today: Override "today" for return-eligibility math (tests).

        Returns:
            ``{"ok": True, "return": {...}}`` on success, or
            ``{"ok": False, "error": <code>, "message": <text>}`` when the
            order is missing or not eligible.
        """
        order = self.get_order(order_id, today)
        if order is None:
            return {"ok": False, "error": "order_not_found",
                    "message": f"No order found with ID {order_id}."}
        if not order["return_eligible"]:
            if order["status"] != "delivered":
                msg = f"Order {order['order_id']} is {order['status']}; only delivered orders can be returned."
            else:
                msg = f"The return window for order {order['order_id']} closed on {order['return_deadline']}."
            return {"ok": False, "error": "not_eligible", "message": msg}
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO returns (OrderId, Reason, Status, CreatedAt) "
                "VALUES (?, ?, ?, ?)",
                (order["order_id"], reason, "open", created),
            )
            conn.commit()
            return_id = cursor.lastrowid
        finally:
            conn.close()
        return {"ok": True, "return": {
            "return_id": f"RET-{return_id}", "order_id": order["order_id"],
            "reason": reason, "status": "open", "created_at": created,
        }}

    def get_return(self, return_id: str) -> Optional[dict]:
        """
        Look up a return by its ``RET-<n>`` ID.

        Returns:
            A return dict, or ``None`` if not found or malformed.
        """
        raw = return_id.strip().upper().removeprefix("RET-")
        if not raw.isdigit():
            return None
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM returns WHERE ReturnId = ?", (int(raw),))
            rows = self._rows_to_dicts(cursor)
        finally:
            conn.close()
        if not rows:
            return None
        r = rows[0]
        return {"return_id": f"RET-{r['ReturnId']}", "order_id": r["OrderId"],
                "reason": r["Reason"], "status": r["Status"], "created_at": r["CreatedAt"]}

    def create_ticket(
        self, customer_email: str, subject: str, description: str, priority: str = "normal"
    ) -> dict:
        """
        Open a support ticket (used for human-escalation labs).

        Returns:
            The created ticket dict with a ``TKT-<n>`` ID.
        """
        priority = priority if priority in ("low", "normal", "high", "urgent") else "normal"
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO tickets (CustomerEmail, Subject, Description, Priority, "
                "Status, CreatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                (customer_email, subject, description, priority, "open", created),
            )
            conn.commit()
            ticket_id = cursor.lastrowid
        finally:
            conn.close()
        return {"ticket_id": f"TKT-{ticket_id}", "customer_email": customer_email,
                "subject": subject, "description": description, "priority": priority,
                "status": "open", "created_at": created}

    def get_ticket(self, ticket_id: str) -> Optional[dict]:
        """
        Look up a ticket by its ``TKT-<n>`` ID.

        Returns:
            A ticket dict, or ``None`` if not found or malformed.
        """
        raw = ticket_id.strip().upper().removeprefix("TKT-")
        if not raw.isdigit():
            return None
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM tickets WHERE TicketId = ?", (int(raw),))
            rows = self._rows_to_dicts(cursor)
        finally:
            conn.close()
        if not rows:
            return None
        t = rows[0]
        return {"ticket_id": f"TKT-{t['TicketId']}", "customer_email": t["CustomerEmail"],
                "subject": t["Subject"], "description": t["Description"],
                "priority": t["Priority"], "status": t["Status"],
                "created_at": t["CreatedAt"]}
