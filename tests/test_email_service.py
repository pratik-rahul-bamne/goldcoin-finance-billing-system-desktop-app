import unittest
from unittest.mock import patch, MagicMock
import email
from email_service import connect_smtp, verify_smtp_connection, send_ledger_email

class TestEmailService(unittest.TestCase):

    @patch('smtplib.SMTP')
    def test_connect_smtp_starttls(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        settings = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': '587',
            'smtp_security': 'STARTTLS',
            'smtp_user': 'user@test.com',
            'smtp_password': 'password123'
        }

        server = connect_smtp(settings)

        # Assert SMTP was called with host and port
        mock_smtp.assert_called_once_with('smtp.test.com', 587, timeout=10)
        # Assert starttls was called
        mock_server.starttls.assert_called_once()
        # Assert login was called
        mock_server.login.assert_called_once_with('user@test.com', 'password123')
        self.assertEqual(server, mock_server)

    @patch('smtplib.SMTP_SSL')
    def test_connect_smtp_ssl_tls(self, mock_smtp_ssl):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server

        settings = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': '465',
            'smtp_security': 'SSL_TLS',
            'smtp_user': 'user@test.com',
            'smtp_password': 'password123'
        }

        server = connect_smtp(settings)

        # Assert SMTP_SSL was called
        mock_smtp_ssl.assert_called_once_with('smtp.test.com', 465, timeout=10)
        # Assert login was called
        mock_server.login.assert_called_once_with('user@test.com', 'password123')
        self.assertEqual(server, mock_server)

    @patch('smtplib.SMTP')
    def test_connect_smtp_none_security(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        settings = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': '25',
            'smtp_security': 'NONE',
            'smtp_user': '',
            'smtp_password': ''
        }

        server = connect_smtp(settings)

        mock_smtp.assert_called_once_with('smtp.test.com', 25, timeout=10)
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()
        self.assertEqual(server, mock_server)

    @patch('email_service.connect_smtp')
    def test_test_smtp_connection(self, mock_connect):
        mock_server = MagicMock()
        mock_connect.return_value = mock_server

        settings = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': '587',
            'smtp_security': 'STARTTLS',
            'smtp_user': 'user@test.com',
            'smtp_password': 'password123',
            'smtp_sender_name': 'Test Org',
            'smtp_sender_email': 'org@test.com'
        }

        verify_smtp_connection(settings, 'recipient@test.com')

        # Connect SMTP should be called with settings
        mock_connect.assert_called_once_with(settings)
        # Sendmail should be called
        mock_server.sendmail.assert_called_once()
        
        # Verify call args
        args, kwargs = mock_server.sendmail.call_args
        self.assertEqual(args[0], 'org@test.com')
        self.assertEqual(args[1], ['recipient@test.com'])
        
        # Parse email
        msg = email.message_from_string(args[2])
        
        # Decode subject header
        subject_header = email.header.decode_header(msg['Subject'])[0]
        subject = subject_header[0]
        if isinstance(subject, bytes):
            subject = subject.decode(subject_header[1] or 'utf-8')
            
        self.assertEqual(subject, "Gold Coin Billing System — SMTP Test Email")
        self.assertEqual(msg['To'], 'recipient@test.com')
        self.assertEqual(msg['From'], 'Test Org <org@test.com>')
        
        # Should call quit
        mock_server.quit.assert_called_once()

    @patch('email_service.connect_smtp')
    def test_send_ledger_email(self, mock_connect):
        mock_server = MagicMock()
        mock_connect.return_value = mock_server

        settings = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': '587',
            'smtp_security': 'STARTTLS',
            'smtp_user': 'user@test.com',
            'smtp_password': 'password123',
            'smtp_sender_name': 'Gold Coin',
            'smtp_sender_email': 'billing@goldcoin.com',
            'email_subject': 'Default Subject',
            'email_body': 'Default Body'
        }

        pdf_bytes = b'%PDF-1.4 mock pdf data'
        pdf_filename = 'Ledger_John_Doe.pdf'

        send_ledger_email(
            'customer@test.com', 
            pdf_bytes, 
            pdf_filename, 
            settings,
            custom_subject='Custom Subject',
            custom_body='Custom Body'
        )

        mock_connect.assert_called_once_with(settings)
        mock_server.sendmail.assert_called_once()
        
        args, kwargs = mock_server.sendmail.call_args
        self.assertEqual(args[0], 'billing@goldcoin.com')
        self.assertEqual(args[1], ['customer@test.com'])
        
        # Parse email
        msg = email.message_from_string(args[2])
        self.assertEqual(msg['Subject'], 'Custom Subject')
        self.assertEqual(msg['To'], 'customer@test.com')
        self.assertEqual(msg['From'], 'Gold Coin <billing@goldcoin.com>')
        
        # Verify attachments and body
        parts = list(msg.walk())
        
        # Decode body
        body_part = parts[1]
        self.assertEqual(body_part.get_payload(decode=True).decode('utf-8'), 'Custom Body')
        
        # Decode attachment
        attachment_part = parts[2]
        self.assertEqual(attachment_part.get_payload(decode=True), pdf_bytes)
        self.assertEqual(attachment_part.get_filename(), 'Ledger_John_Doe.pdf')
        
        mock_server.quit.assert_called_once()

if __name__ == '__main__':
    unittest.main()
