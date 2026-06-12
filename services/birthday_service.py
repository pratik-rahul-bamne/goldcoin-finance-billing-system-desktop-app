import os
import sys
import sqlite3
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# Add project root to sys.path so we can import email_service
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from email_service import send_birthday_email

def get_db_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'goldcoin_billing.db')
    return os.path.join(project_root, 'goldcoin_billing.db')

def check_and_send_birthdays(db_path=None):
    if not db_path:
        db_path = get_db_path()
        
    if not os.path.exists(db_path):
        print(f"[Error] Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. Load birthday and SMTP settings
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings = {row['key']: row['value'] for row in rows}
    
    enabled = settings.get('birthday_emails_enabled') == '1'
    if not enabled:
        print("Birthday emails are disabled in settings.")
        conn.close()
        return
        
    # 2. Find customers with birthday today
    query = """
    SELECT id, name, email, mobile
    FROM customers
    WHERE strftime('%m-%d', birth_date) = strftime('%m-%d', 'now', 'localtime')
    """
    todays_birthdays = conn.execute(query).fetchall()
    
    if not todays_birthdays:
        print("No customers have a birthday today.")
        conn.close()
        return
        
    print(f"Found {len(todays_birthdays)} customers with birthdays today.")
    
    current_year = datetime.now().year
    
    for customer in todays_birthdays:
        cust_id = customer['id']
        name = customer['name']
        email = customer['email']
        
        if not email or '@' not in email:
            print(f"Skipping {name} (invalid or missing email: '{email}')")
            continue
            
        # Check if already sent
        log = conn.execute(
            "SELECT 1 FROM birthday_logs WHERE customer_id = ? AND sent_year = ? AND status = 'SUCCESS'",
            (cust_id, current_year)
        ).fetchone()
        
        if log:
            print(f"Birthday email already sent to {name} for year {current_year}. Skipping.")
            continue
            
        print(f"Sending birthday email to {name} ({email})...")
        
        # Build subject and body
        subject = "🎉 Happy Birthday!"
        
        # Load templates via Jinja2 FileSystemLoader
        templates_dir = os.path.join(project_root, 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir))
        
        company_name = settings.get('company_name', 'Gold Coin Consultancy')
        company_address = settings.get('company_address', '')
        contact_1 = settings.get('contact_1', '')
        contact_2 = settings.get('contact_2', '')
        
        include_offer = settings.get('birthday_include_offer') == '1'
        send_html = settings.get('birthday_send_html', '1') == '1'
        
        # Build raw text version
        offer_text = ""
        if include_offer:
            offer_text = "\n\n🎁 Special Birthday Offer:\nEnjoy a 15% waiver on processing fees for your next service request or consult. Simply mention this card!"
            
        body_text = f"Dear {name},\n\nHappy Birthday! 🌟\n\nThank you for being a valued customer of {company_name}. We hope your special day is filled with joy, and that the coming year brings you happiness, success, and prosperity.{offer_text}\n\nBest Wishes,\n{company_name}\n{company_address}\nContact: {contact_1} {f'| {contact_2}' if contact_2 else ''}"
        
        body_html = ""
        if send_html:
            try:
                template = env.get_template('birthday.html')
                body_html = template.render(
                    customer_name=name,
                    company_name=company_name,
                    company_address=company_address,
                    contact_1=contact_1,
                    contact_2=contact_2,
                    include_offer=include_offer
                )
            except Exception as e:
                print(f"Error loading HTML template, falling back to plain text: {e}")
                body_html = body_text.replace('\n', '<br/>')
        else:
            body_html = body_text.replace('\n', '<br/>')
            
        try:
            send_birthday_email(email, subject, body_html, body_text, settings)
            # Log success
            conn.execute(
                "INSERT INTO birthday_logs (customer_id, sent_year, status) VALUES (?, ?, 'SUCCESS')",
                (cust_id, current_year)
            )
            conn.commit()
            print(f"Successfully sent birthday email to {name}.")
        except Exception as e:
            # Log failure
            print(f"Failed to send birthday email to {name}: {e}")
            conn.execute(
                "INSERT INTO birthday_logs (customer_id, sent_year, status) VALUES (?, ?, 'FAILED')",
                (cust_id, current_year)
            )
            conn.commit()
            
    conn.close()

if __name__ == '__main__':
    print("Running birthday service directly...")
    check_and_send_birthdays()
