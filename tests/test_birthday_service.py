import unittest
from unittest.mock import patch, MagicMock
import os
import sqlite3
from datetime import datetime
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.birthday_service import check_and_send_birthdays

class TestBirthdayService(unittest.TestCase):

    def setUp(self):
        # Setup an in-memory or temp sqlite db for testing
        self.db_path = "test_goldcoin_billing.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Create schema
        self.conn.execute("""
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        
        self.conn.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            email TEXT DEFAULT '',
            business_name TEXT DEFAULT '',
            village TEXT DEFAULT '',
            bank_name TEXT DEFAULT '',
            loan_amount REAL DEFAULT 0,
            customer_date TEXT,
            birth_date TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """)
        
        self.conn.execute("""
        CREATE TABLE birthday_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            sent_year INTEGER NOT NULL,
            sent_at TEXT DEFAULT (datetime('now', 'localtime')),
            status TEXT NOT NULL
        )
        """)
        
        # Seed default settings
        self.conn.execute("INSERT INTO settings (key, value) VALUES ('birthday_emails_enabled', '1')")
        self.conn.execute("INSERT INTO settings (key, value) VALUES ('birthday_email_time', '09:00')")
        self.conn.execute("INSERT INTO settings (key, value) VALUES ('birthday_sender_email', 'support@test.com')")
        self.conn.execute("INSERT INTO settings (key, value) VALUES ('birthday_send_html', '1')")
        self.conn.execute("INSERT INTO settings (key, value) VALUES ('birthday_include_offer', '1')")
        self.conn.execute("INSERT INTO settings (key, value) VALUES ('company_name', 'Gold Coin Test')")
        
        # Seed customers: one with birthday today, one with birthday on another day
        self.today_str = datetime.now().strftime('%Y-%m-%d')
        # Birthday today but different year
        self.bday_today = f"1990-{datetime.now().strftime('%m-%d')}"
        # Birthday tomorrow
        self.bday_other = "1995-12-31" if datetime.now().strftime('%m-%d') != '12-31' else "1995-01-01"
        
        self.conn.execute("""
        INSERT INTO customers (name, mobile, email, birth_date)
        VALUES ('Birthday Customer', '1234567890', 'birthday@test.com', ?)
        """, (self.bday_today,))
        
        self.conn.execute("""
        INSERT INTO customers (name, mobile, email, birth_date)
        VALUES ('Other Customer', '9876543210', 'other@test.com', ?)
        """, (self.bday_other,))
        
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    @patch('services.birthday_service.send_birthday_email')
    def test_send_birthday_success(self, mock_send):
        # Verify check_and_send_birthdays sends the email and logs success
        check_and_send_birthdays(self.db_path)
        
        # Email should be sent to 'Birthday Customer' and not 'Other Customer'
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(args[0], 'birthday@test.com')
        self.assertEqual(args[1], '🎉 Happy Birthday!')
        self.assertIn('Birthday Customer', args[2]) # HTML content contains name
        
        # Check that log was created with 'SUCCESS'
        log = self.conn.execute("SELECT * FROM birthday_logs").fetchone()
        self.assertIsNotNone(log)
        self.assertEqual(log['customer_id'], 1)
        self.assertEqual(log['sent_year'], datetime.now().year)
        self.assertEqual(log['status'], 'SUCCESS')

    @patch('services.birthday_service.send_birthday_email')
    def test_send_birthday_already_sent(self, mock_send):
        # Seed log that email was already successfully sent this year
        self.conn.execute("""
        INSERT INTO birthday_logs (customer_id, sent_year, status)
        VALUES (1, ?, 'SUCCESS')
        """, (datetime.now().year,))
        self.conn.commit()
        
        check_and_send_birthdays(self.db_path)
        
        # Email should NOT be sent
        mock_send.assert_not_called()

    @patch('services.birthday_service.send_birthday_email')
    def test_send_birthday_failed_retry(self, mock_send):
        # Seed log that email sending failed previously this year
        self.conn.execute("""
        INSERT INTO birthday_logs (customer_id, sent_year, status)
        VALUES (1, ?, 'FAILED')
        """, (datetime.now().year,))
        self.conn.commit()
        
        check_and_send_birthdays(self.db_path)
        
        # Email should be attempted again
        mock_send.assert_called_once()

    @patch('services.birthday_service.send_birthday_email')
    def test_disabled_settings(self, mock_send):
        # Update settings to disabled
        self.conn.execute("UPDATE settings SET value = '0' WHERE key = 'birthday_emails_enabled'")
        self.conn.commit()
        
        check_and_send_birthdays(self.db_path)
        
        # Email should NOT be sent
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
