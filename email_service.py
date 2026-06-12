import smtplib
import socket
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def connect_smtp(smtp_settings):
    """Establishes an SMTP connection based on the security configuration."""
    host = smtp_settings.get('smtp_host', '').strip()
    try:
        port = int(smtp_settings.get('smtp_port', 587))
    except ValueError:
        port = 587
        
    security = smtp_settings.get('smtp_security', 'STARTTLS').strip().upper()
    user = smtp_settings.get('smtp_user', '').strip()
    password = smtp_settings.get('smtp_password', '').strip()
    
    # Auto-align standard ports to prevent configuration mismatches
    if port == 465:
        security = 'SSL_TLS'
    elif port == 587:
        security = 'STARTTLS'
        
    if not host:
        raise ValueError("SMTP host is not configured.")
        
    try:
        # Setup SMTP client
        if security == 'SSL_TLS':
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            
        server.ehlo()
        
        if security == 'STARTTLS':
            try:
                server.starttls()
                server.ehlo()
            except (socket.timeout, TimeoutError) as e:
                server.close()
                raise RuntimeError(
                    f"STARTTLS handshake timed out. This often happens if:\n"
                    f"1. Your ISP blocks or intercepts port 587 (common in India). Try switching to Port 465 with SSL/TLS security.\n"
                    f"2. An antivirus or firewall is intercepting secure email handshakes."
                )
            except Exception as e:
                server.close()
                raise RuntimeError(f"STARTTLS handshake failed. Ensure that port {port} supports STARTTLS. Error: {e}")
                
        if user and password:
            try:
                server.login(user, password)
            except Exception as e:
                server.close()
                raise RuntimeError(f"SMTP authentication failed. Check your username and password. (For Gmail, ensure you are using an App Password, not your regular password). Error: {e}")
                
        return server
        
    except (socket.timeout, TimeoutError) as e:
        raise RuntimeError(
            f"Connection timed out (10s limit). Check:\n"
            f"1. Is the SMTP Host '{host}' correct?\n"
            f"2. Is the Port {port} correct?\n"
            f"3. Are outbound connections on port {port} blocked by your internet provider, local firewall, or antivirus?"
        )
    except ConnectionRefusedError as e:
        raise RuntimeError(
            f"Connection refused by server. Ensure the SMTP Host '{host}' and Port {port} are correct."
        )
    except smtplib.SMTPServerDisconnected as e:
        suggestion = ""
        if port == 465 and security != 'SSL_TLS':
            suggestion = " (Hint: Port 465 usually requires 'SSL/TLS' connection security. Change Connection Security to SSL/TLS.)"
        elif port == 587 and security == 'SSL_TLS':
            suggestion = " (Hint: Port 587 usually requires 'STARTTLS' connection security. Change Connection Security to STARTTLS.)"
        raise RuntimeError(
            f"Connection unexpectedly closed by the SMTP server{suggestion}. Error: {e}"
        )
    except ssl.SSLError as e:
        raise RuntimeError(
            f"SSL/TLS protocol error. Your Connection Security might not match the SMTP port. Error: {e}"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to connect to SMTP server: {e}")

def verify_smtp_connection(smtp_settings, test_recipient):
    """
    Tests the SMTP connection by establishing a connection, authenticating,
    and sending a simple test email.
    """
    if not test_recipient:
        raise ValueError("Test recipient email is required.")
        
    server = connect_smtp(smtp_settings)
    
    sender_name = smtp_settings.get('smtp_sender_name', 'Gold Coin Consultancy').strip()
    sender_email = smtp_settings.get('smtp_sender_email', '').strip() or smtp_settings.get('smtp_user', '').strip()
    
    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = test_recipient
    msg['Subject'] = "Gold Coin Billing System — SMTP Test Email"
    
    body = (
        "Hello,\n\n"
        "This is a test email from the Gold Coin Consultancy Desktop Billing System.\n"
        "If you are reading this, your SMTP email integration is configured correctly and working!\n\n"
        "Regards,\n"
        "Gold Coin Consultancy"
    )
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        server.sendmail(sender_email, [test_recipient], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass

def send_ledger_email(recipient_email, pdf_bytes, pdf_filename, smtp_settings, custom_subject=None, custom_body=None):
    """
    Sends an email with the ledger PDF attached to the specified recipient.
    """
    if not recipient_email:
        raise ValueError("Recipient email is required.")
        
    server = connect_smtp(smtp_settings)
    
    sender_name = smtp_settings.get('smtp_sender_name', 'Gold Coin Consultancy').strip()
    sender_email = smtp_settings.get('smtp_sender_email', '').strip() or smtp_settings.get('smtp_user', '').strip()
    
    subject = custom_subject or smtp_settings.get('email_subject', 'Ledger Statement from Gold Coin Consultancy').strip()
    body = custom_body or smtp_settings.get('email_body', 'Dear Customer,\n\nPlease find attached the statement of your ledger account.\n\nRegards,\nGold Coin Consultancy').strip()
    
    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = recipient_email
    msg['Subject'] = subject
    
    # Body
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Attachment
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
    msg.attach(attachment)
    
    try:
        server.sendmail(sender_email, [recipient_email], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass
