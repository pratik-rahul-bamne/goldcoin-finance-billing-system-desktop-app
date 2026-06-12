"""
Gold Coin Consultancy Finance Services
Desktop Billing & Ledger System
Flask + SQLite + PyWebView
"""

import os
import sys
import sqlite3
import hashlib
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, jsonify, send_file, session, flash)
from werkzeug.utils import secure_filename
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer, Image, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from email_service import send_ledger_email, verify_smtp_connection


# ── Path Handling for PyInstaller ──────────────────────────────────────────────
def resource_path(relative):
    """Absolute path to a bundled resource (templates/static). Works dev + PyInstaller."""
    base = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base, relative)


def data_path(filename):
    """Absolute path for persistent data files stored next to the .exe (or project root)."""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath('.'), filename)


# ── Flask App ──────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=resource_path('templates'),
    static_folder=resource_path('static')
)
app.secret_key = 'goldcoin_billing_2025_secure_key_!@#$%'
DB_PATH = data_path('goldcoin_billing.db')
ALLOWED_EXTENSIONS = {'xlsx'}
BACKUP_DIR = 'backup_files'
LOG_DIR = 'logs'


# ── Database Helpers ───────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def init_db():
    schema_path = resource_path('database.sql')
    conn = get_db()
    with open(schema_path, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    
    # Run migrations for existing databases
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN birth_date TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        # birth_date column already exists
        pass

    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS birthday_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            sent_year   INTEGER NOT NULL,
            sent_at     TEXT DEFAULT (datetime('now', 'localtime')),
            status      TEXT NOT NULL
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_birthday_logs_customer ON birthday_logs(customer_id)")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Error creating birthday logs table: {e}")

    # Seed new default settings if not exists
    birthday_defaults = [
        ('birthday_emails_enabled', '0'),
        ('birthday_email_time', '09:00'),
        ('birthday_sender_email', 'support@goldcoinfinance.com'),
        ('birthday_send_html', '1'),
        ('birthday_include_offer', '0')
    ]
    for key, val in birthday_defaults:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    conn.commit()
    
    conn.close()
    print(f"[OK] SQLite database ready at: {DB_PATH}")


init_db()


# ── Auth Helpers ───────────────────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── Auth Routes ────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = 'admin_password'").fetchone()
        conn.close()
        stored = row['value'] if row else 'admin123'

        # First run: stored is plain text → auto-upgrade to hash
        if len(stored) != 64:
            if password == stored:
                hashed = hash_password(stored)
                c = get_db()
                c.execute("UPDATE settings SET value = ? WHERE key = 'admin_password'", (hashed,))
                c.commit(); c.close()
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                error = 'Incorrect password. Please try again.'
        else:
            if hash_password(password) == stored:
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                error = 'Incorrect password. Please try again.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current = request.form.get('current_password', '')
    new_pw  = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = 'admin_password'").fetchone()
    stored = row['value'] if row else ''

    if hash_password(current) != stored:
        flash('Current password is incorrect.', 'error')
    elif new_pw != confirm:
        flash('New passwords do not match.', 'error')
    elif len(new_pw) < 4:
        flash('Password must be at least 4 characters.', 'error')
    else:
        conn.execute("UPDATE settings SET value = ? WHERE key = 'admin_password'", (hash_password(new_pw),))
        conn.commit()
        flash('Password changed successfully!', 'success')
    conn.close()
    return redirect(url_for('service_catalog'))


# ── Health ─────────────────────────────────────────────────────────────────────
@app.route('/health')
def health():
    return 'OK', 200


# ── Dashboard ──────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/dashboard')
@login_required
def index():
    conn = get_db()
    customers        = conn.execute('SELECT * FROM customers ORDER BY created_at DESC').fetchall()
    total_customers  = len(customers)
    total_charges    = conn.execute('SELECT COALESCE(SUM(charge),0) as t FROM services').fetchone()['t']
    total_received   = conn.execute('SELECT COALESCE(SUM(amount),0) as t FROM payments').fetchone()['t']
    total_outstanding = total_charges - total_received
    recent_customers = conn.execute('SELECT * FROM customers ORDER BY created_at DESC LIMIT 5').fetchall()
    conn.close()
    return render_template('index.html',
                           customers=customers,
                           recent_customers=recent_customers,
                           total_customers=total_customers,
                           total_charges=total_charges,
                           total_received=total_received,
                           total_outstanding=total_outstanding)


# ── Customer Routes ────────────────────────────────────────────────────────────
@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name          = request.form['name'].strip()
        mobile        = request.form['mobile'].strip()
        email         = request.form.get('email', '').strip()
        business_name = request.form.get('business_name', '').strip()
        village       = request.form.get('village', '').strip()
        birth_date    = request.form.get('birth_date', '').strip()
        bank_name     = request.form.get('bank_name', '').strip()
        loan_amount   = request.form.get('loan_amount', 0) or 0
        customer_date = request.form.get('customer_date') or datetime.now().strftime('%Y-%m-%d')
        conn = get_db()
        conn.execute(
            'INSERT INTO customers (name,mobile,email,business_name,village,bank_name,loan_amount,customer_date,birth_date) VALUES (?,?,?,?,?,?,?,?,?)',
            (name, mobile, email, business_name, village, bank_name, loan_amount, customer_date, birth_date)
        )
        conn.commit()
        conn.close()
        flash(f'Customer "{name}" added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_customer.html', today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    conn = get_db()
    if request.method == 'POST':
        conn.execute(
            'UPDATE customers SET name=?,mobile=?,email=?,business_name=?,village=?,bank_name=?,loan_amount=?,customer_date=?,birth_date=? WHERE id=?',
            (request.form['name'], request.form['mobile'], request.form.get('email',''),
             request.form.get('business_name',''), request.form.get('village',''),
             request.form.get('bank_name',''), request.form.get('loan_amount',0) or 0,
             request.form.get('customer_date',''), request.form.get('birth_date',''), customer_id)
        )
        conn.commit()
        conn.close()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('index'))
    customer = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    conn.close()
    if not customer:
        return "Customer not found", 404
    return render_template('edit_customer.html', customer=customer)


@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    conn = get_db()
    customer = conn.execute('SELECT name FROM customers WHERE id=?', (customer_id,)).fetchone()
    if customer:
        conn.execute('DELETE FROM customers WHERE id=?', (customer_id,))
        conn.commit()
        flash(f'Customer "{customer["name"]}" deleted.', 'success')
    conn.close()
    return redirect(url_for('index'))


@app.route('/customer_catalog')
@login_required
def customer_catalog():
    search_query = request.args.get('search', '').strip()
    conn = get_db()
    if search_query:
        customers = conn.execute(
            "SELECT * FROM customers WHERE name LIKE ? OR mobile LIKE ? ORDER BY name",
            (f'%{search_query}%', f'%{search_query}%')
        ).fetchall()
    else:
        customers = conn.execute('SELECT * FROM customers ORDER BY name').fetchall()
    conn.close()
    return render_template('customer_catalog.html', customers=customers, search_query=search_query)


# ── Service Catalog Routes ─────────────────────────────────────────────────────
@app.route('/service_catalog')
@login_required
def service_catalog():
    conn = get_db()
    services = conn.execute('SELECT * FROM service_catalog ORDER BY service_name').fetchall()
    conn.close()
    return render_template('service_catalog.html', services=services)


@app.route('/service_catalog/add', methods=['POST'])
@login_required
def add_catalog_service():
    service_name = request.form.get('service_name', '').strip()
    try:
        default_charge = float(request.form.get('default_charge', 0) or 0)
    except ValueError:
        flash('Price must be a valid number.', 'error')
        return redirect(url_for('service_catalog'))

    if not service_name:
        flash('Service Name cannot be empty.', 'error')
        return redirect(url_for('service_catalog'))

    if default_charge < 0:
        flash('Price must be a non-negative number.', 'error')
        return redirect(url_for('service_catalog'))

    conn = get_db()
    try:
        # Check for duplicates
        dup = conn.execute('SELECT id FROM service_catalog WHERE service_name = ?', (service_name,)).fetchone()
        if dup:
            flash('Failed to add service. Service name already exists.', 'error')
            return redirect(url_for('service_catalog'))

        conn.execute('INSERT INTO service_catalog (service_name, default_charge) VALUES (?, ?)',
                     (service_name, default_charge))
        conn.commit()
        flash(f'Service "{service_name}" added successfully.', 'success')
    except Exception as e:
        print(f"Error adding service: {e}")
        flash('Failed to add service. Please try again.', 'error')
    finally:
        conn.close()
    return redirect(url_for('service_catalog'))


@app.route('/service_catalog/edit/<int:service_id>', methods=['POST'])
@login_required
def edit_catalog_service(service_id):
    service_name = request.form.get('service_name', '').strip()
    try:
        default_charge = float(request.form.get('default_charge', 0) or 0)
    except ValueError:
        flash('Price must be a valid number.', 'error')
        return redirect(url_for('service_catalog'))

    is_active = int(request.form.get('is_active', 1))

    if not service_name:
        flash('Service Name cannot be empty.', 'error')
        return redirect(url_for('service_catalog'))

    if default_charge < 0:
        flash('Price must be a non-negative number.', 'error')
        return redirect(url_for('service_catalog'))

    conn = get_db()
    try:
        # Check for duplicate service name (excluding current service)
        dup = conn.execute('SELECT id FROM service_catalog WHERE service_name = ? AND id != ?',
                           (service_name, service_id)).fetchone()
        if dup:
            flash('Failed to update service. Service name already exists.', 'error')
            return redirect(url_for('service_catalog'))

        conn.execute('UPDATE service_catalog SET service_name=?, default_charge=?, is_active=? WHERE id=?',
                     (service_name, default_charge, is_active, service_id))
        conn.commit()
        flash('Service updated successfully.', 'success')
    except Exception as e:
        print(f"Error updating service: {e}")
        flash('Failed to update service. Please try again.', 'error')
    finally:
        conn.close()

    return redirect(url_for('service_catalog'))


@app.route('/service_catalog/delete/<int:service_id>', methods=['POST'])
@login_required
def delete_catalog_service(service_id):
    conn = get_db()
    try:
        # Check if the service exists
        service = conn.execute('SELECT service_name FROM service_catalog WHERE id=?', (service_id,)).fetchone()
        if not service:
            flash('Service not found in catalog.', 'error')
            return redirect(url_for('service_catalog'))

        conn.execute('DELETE FROM service_catalog WHERE id=?', (service_id,))
        conn.commit()
        flash('Service deleted successfully.', 'success')
    except Exception as e:
        print(f"Error deleting service from catalog: {e}")
        flash('Failed to delete service. Please try again.', 'error')
    finally:
        conn.close()
    return redirect(url_for('service_catalog'))


@app.route('/api/services')
@login_required
def api_services():
    conn = get_db()
    services = conn.execute('SELECT * FROM service_catalog WHERE is_active=1 ORDER BY service_name').fetchall()
    conn.close()
    return jsonify([{'id': s['id'], 'name': s['service_name'], 'charge': s['default_charge']} for s in services])


# ── Customer Services Routes ───────────────────────────────────────────────────
@app.route('/add_services/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def add_services(customer_id):
    conn = get_db()
    if request.method == 'POST':
        service_name = request.form['service_name']
        charge       = request.form.get('charge', 0) or 0
        conn.execute('INSERT INTO services (customer_id,service_name,charge) VALUES (?,?,?)',
                     (customer_id, service_name, charge))
        conn.commit()
        conn.close()
        return redirect(url_for('add_services', customer_id=customer_id))

    customer         = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    services         = conn.execute('SELECT * FROM services WHERE customer_id=?', (customer_id,)).fetchall()
    catalog_services = conn.execute('SELECT * FROM service_catalog WHERE is_active=1 ORDER BY service_name').fetchall()
    conn.close()
    return render_template('add_services.html', customer=customer, services=services, catalog_services=catalog_services)


@app.route('/delete_service/<int:service_id>', methods=['POST'])
@login_required
def delete_service(service_id):
    conn = get_db()
    service = conn.execute('SELECT customer_id FROM services WHERE id=?', (service_id,)).fetchone()
    if service:
        customer_id = service['customer_id']
        conn.execute('DELETE FROM services WHERE id=?', (service_id,))
        conn.commit()
        conn.close()
        referrer = request.referrer or ''
        return redirect(url_for('bill', customer_id=customer_id) if 'bill' in referrer
                        else url_for('add_services', customer_id=customer_id))
    conn.close()
    return "Service not found", 404


@app.route('/delete_multiple_services/<int:customer_id>', methods=['POST'])
@login_required
def delete_multiple_services(customer_id):
    service_ids = request.form.getlist('service_ids')
    if service_ids:
        conn = get_db()
        for sid in service_ids:
            conn.execute('DELETE FROM services WHERE id=? AND customer_id=?', (sid, customer_id))
        conn.commit()
        conn.close()
    return redirect(url_for('bill', customer_id=customer_id))


# ── Payment Routes ─────────────────────────────────────────────────────────────
@app.route('/add_payment/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def add_payment(customer_id):
    conn = get_db()
    if request.method == 'POST':
        date   = request.form['date']
        amount = request.form['amount']
        note   = request.form.get('note', '')
        conn.execute('INSERT INTO payments (customer_id,date,amount,note) VALUES (?,?,?,?)',
                     (customer_id, date, amount, note))
        conn.commit()
        conn.close()
        flash('Payment recorded successfully!', 'success')
        return redirect(url_for('add_payment', customer_id=customer_id))

    customer = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    payments = conn.execute('SELECT * FROM payments WHERE customer_id=? ORDER BY date DESC', (customer_id,)).fetchall()
    conn.close()
    return render_template('add_payment.html', customer=customer, payments=payments,
                           today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/delete_payment/<int:payment_id>', methods=['POST'])
@login_required
def delete_payment(payment_id):
    conn = get_db()
    payment = conn.execute('SELECT customer_id FROM payments WHERE id=?', (payment_id,)).fetchone()
    if payment:
        conn.execute('DELETE FROM payments WHERE id=?', (payment_id,))
        conn.commit()
        conn.close()
        flash('Payment deleted.', 'success')
        return redirect(url_for('add_payment', customer_id=payment['customer_id']))
    conn.close()
    return "Payment not found", 404


# ── Bill & PDF Routes ──────────────────────────────────────────────────────────
@app.route('/bill/<int:customer_id>')
@login_required
def bill(customer_id):
    conn = get_db()
    customer = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE customer_id=?', (customer_id,)).fetchall()
    payments = conn.execute('SELECT * FROM payments WHERE customer_id=? ORDER BY date', (customer_id,)).fetchall()

    # Fetch default email subject/body
    settings_rows = conn.execute("SELECT key, value FROM settings WHERE key IN ('email_subject', 'email_body')").fetchall()
    email_settings = {row['key']: row['value'] for row in settings_rows}

    conn.close()

    total_charges  = sum(s['charge'] for s in services)
    total_received = sum(p['amount'] for p in payments)
    balance        = total_charges - total_received
    return render_template('bill.html', customer=customer, services=services, payments=payments,
                           total_charges=total_charges, total_received=total_received,
                           balance=balance, current_date=datetime.now().strftime('%d/%m/%Y'),
                           email_settings=email_settings)


@app.route('/download_pdf/<int:customer_id>')
@login_required
def download_pdf(customer_id):
    conn = get_db()
    customer = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE customer_id=?', (customer_id,)).fetchall()
    payments = conn.execute('SELECT * FROM payments WHERE customer_id=? ORDER BY date', (customer_id,)).fetchall()
    conn.close()

    total_charges  = sum(s['charge'] for s in services)
    total_received = sum(p['amount'] for p in payments)
    balance        = total_charges - total_received

    buffer = BytesIO()
    generate_ledger_pdf(buffer, customer, services, payments, total_charges, total_received, balance)
    buffer.seek(0)
    filename = f"Ledger_{customer['name'].replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)


def generate_ledger_pdf(buffer, customer, services, payments, total_charges, total_received, balance):
    """Generate a professional A4 PDF ledger — full-page layout, 10mm margins."""
    # 10 mm = 28.35 pt
    MARGIN = 28.35
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN
    )
    elements = []
    styles = getSampleStyleSheet()

    # ── Font Registration ──────────────────────────────────────────
    font_regular = 'Helvetica'
    font_bold = 'Helvetica-Bold'
    font_italic = 'Helvetica-Oblique'
    has_rupee = False

    # Check for Arial in standard Windows Fonts directory
    win_font_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    arial_path = os.path.join(win_font_dir, 'arial.ttf')
    arial_bd_path = os.path.join(win_font_dir, 'arialbd.ttf')
    arial_it_path = os.path.join(win_font_dir, 'ariali.ttf')

    if os.path.exists(arial_path) and os.path.exists(arial_bd_path) and os.path.exists(arial_it_path):
        try:
            pdfmetrics.registerFont(TTFont('Arial', arial_path))
            pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bd_path))
            pdfmetrics.registerFont(TTFont('Arial-Italic', arial_it_path))
            font_regular = 'Arial'
            font_bold = 'Arial-Bold'
            font_italic = 'Arial-Italic'
            has_rupee = True
        except Exception:
            pass

    def fmt_rupee(val):
        symbol = '\u20b9' if has_rupee else 'Rs. '
        return f"{symbol}{val:,.2f}"

    def fmt_rupee_no_decimal(val):
        symbol = '\u20b9' if has_rupee else 'Rs. '
        return f"{symbol}{val:,.0f}"

    # ── Palette ───────────────────────────────────────────────────
    NAVY_DARK  = colors.HexColor('#162C4A')
    NAVY       = colors.HexColor('#1F3A5F')
    GOLD       = colors.HexColor('#C9A227')
    GOLD_LIGHT = colors.HexColor('#E8C547')
    SURFACE    = colors.HexColor('#F1F4F8')
    WHITE      = colors.white
    TEXT_DARK  = colors.HexColor('#1A2332')
    TEXT_MID   = colors.HexColor('#4A5568')
    TEXT_LIGHT = colors.HexColor('#8A9BB0')
    GREEN_BG   = colors.HexColor('#D1FAE5')
    GREEN_FG   = colors.HexColor('#065F46')
    ALT_ROW    = colors.HexColor('#F5F7FA')
    BORDER     = colors.HexColor('#DDE3ED')

    def ps(name, **kw):
        if 'fontName' not in kw:
            kw['fontName'] = font_regular
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    # Full usable width: A4 width minus 2 × 10 mm margins  ≈ 538 pt
    usable_w = A4[0] - 2 * MARGIN

    # ════════════════════════════════════════════════════════════════════
    # 1. HEADER — dark navy full-width banner
    # ════════════════════════════════════════════════════════════════════
    logo_path = resource_path('static/logo.png')
    has_logo = os.path.exists(logo_path)
    
    if has_logo:
        try:
            logo_img = Image(logo_path, width=50, height=50)
            header_tbl = Table([
                [logo_img, Paragraph("GOLD COIN CONSULTANCY FINANCE SERVICES<br/><font color='#E8C547' size='11'><i>Professional Financial Consultancy</i></font>", 
                                      ps('HT', fontSize=18, fontName=font_bold, textColor=WHITE, leading=22, alignment=0))]
            ], colWidths=[65, usable_w - 65])
            header_tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0,0),(-1,-1), NAVY),
                ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
                ('TOPPADDING',    (0,0),(-1,-1), 10),
                ('BOTTOMPADDING', (0,0),(-1,-1), 10),
                ('LEFTPADDING',   (0,0),(-1,-1), 12),
                ('RIGHTPADDING',  (0,0),(-1,-1), 12),
            ]))
        except Exception:
            has_logo = False
            
    if not has_logo:
        header_tbl = Table([
            [Paragraph("GOLD COIN CONSULTANCY FINANCE SERVICES",
                       ps('HT', fontSize=24, fontName=font_bold,
                          textColor=WHITE, alignment=TA_CENTER, leading=28))],
            [Paragraph("Professional Financial Consultancy",
                       ps('HS', fontSize=12, fontName=font_italic,
                          textColor=GOLD_LIGHT, alignment=TA_CENTER, leading=15))],
        ], colWidths=[usable_w])
        header_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), NAVY),
            ('TOPPADDING',    (0,0),(-1,0),  10),
            ('BOTTOMPADDING', (0,0),(-1,0),  2),
            ('TOPPADDING',    (0,1),(-1,1),  2),
            ('BOTTOMPADDING', (0,1),(-1,1),  10),
            ('LEFTPADDING',   (0,0),(-1,-1), 12),
            ('RIGHTPADDING',  (0,0),(-1,-1), 12),
        ]))
    elements.append(header_tbl)

    # ════════════════════════════════════════════════════════════════════
    # 2. LEDGER ACCOUNT title
    # ════════════════════════════════════════════════════════════════════
    ledger_tbl = Table([
        [Paragraph("LEDGER ACCOUNT",
                   ps('LT', fontSize=18, fontName=font_bold,
                      textColor=NAVY_DARK, alignment=TA_CENTER, leading=22))]
    ], colWidths=[usable_w])
    ledger_tbl.setStyle(TableStyle([
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LINEBELOW',     (0,0),(-1,-1), 1, BORDER),
    ]))
    elements += [ledger_tbl, Spacer(1, 12)]

    # ════════════════════════════════════════════════════════════════════
    # 3. CUSTOMER INFO — 4-column clean grid (label|value|label|value)
    # ════════════════════════════════════════════════════════════════════
    def info_lbl(uid, txt):
        return Paragraph(f"<b>{txt}:</b>", ps(f'IL{uid}', fontSize=11, fontName=font_bold, textColor=NAVY_DARK))
    def info_val(uid, txt):
        return Paragraph(str(txt), ps(f'IV{uid}', fontSize=11, fontName=font_regular, textColor=TEXT_DARK))

    loan_str     = fmt_rupee_no_decimal(customer['loan_amount']) if customer['loan_amount'] else '\u2014'
    business_str = customer['business_name'] or '\u2014'

    lbl_w1 = usable_w * 0.22
    val_w1 = usable_w * 0.28
    lbl_w2 = usable_w * 0.18
    val_w2 = usable_w * 0.32

    ci_rows = [
        [info_lbl('n', 'Customer Name'), info_val('n', customer['name']),
         info_lbl('d', 'Date'),          info_val('d', datetime.now().strftime('%d/%m/%Y'))],
        [info_lbl('b', 'Business'),      info_val('b', business_str),
         info_lbl('m', 'Mobile No.'),    info_val('m', customer['mobile'])],
        [info_lbl('v', 'Village'),       info_val('v', customer['village'] or '\u2014'),
         info_lbl('bk', 'Bank Name'),   info_val('bk', customer['bank_name'] or '\u2014')],
        [info_lbl('l', 'Loan Amount'),   info_val('l', loan_str),
         Paragraph('', ps('ep1')),       Paragraph('', ps('ep2'))],
    ]

    ci_style = [
        ('BACKGROUND',    (0,0),(-1,-1), SURFACE),
        ('BOX',           (0,0),(-1,-1), 1, BORDER),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 12),
        ('RIGHTPADDING',  (0,0),(-1,-1), 12),
    ]

    ci_tbl = Table(ci_rows, colWidths=[lbl_w1, val_w1, lbl_w2, val_w2])
    ci_tbl.setStyle(TableStyle(ci_style))
    elements += [ci_tbl, Spacer(1, 12)]

    # ════════════════════════════════════════════════════════════════════
    # 4. TRANSACTION LEDGER TABLE — no vertical lines, clean typography
    # ════════════════════════════════════════════════════════════════════
    style_th_c = ps('TH_C', fontSize=11, fontName=font_bold, textColor=WHITE, alignment=TA_CENTER)
    style_th_l = ps('TH_L', fontSize=11, fontName=font_bold, textColor=WHITE)
    style_th_r = ps('TH_R', fontSize=11, fontName=font_bold, textColor=WHITE, alignment=TA_RIGHT)

    style_c_reg = ps('C_REG', fontSize=11, fontName=font_regular, textColor=TEXT_DARK, alignment=TA_CENTER)
    style_l_reg = ps('L_REG', fontSize=11, fontName=font_regular, textColor=TEXT_DARK)
    style_r_reg = ps('R_REG', fontSize=11, fontName=font_regular, textColor=TEXT_DARK, alignment=TA_RIGHT)

    style_c_bold = ps('C_BOLD', fontSize=11, fontName=font_bold, textColor=TEXT_DARK, alignment=TA_CENTER)
    style_l_bold = ps('L_BOLD', fontSize=11, fontName=font_bold, textColor=TEXT_DARK)
    style_r_bold = ps('R_BOLD', fontSize=11, fontName=font_bold, textColor=TEXT_DARK, alignment=TA_RIGHT)

    # Green variants for payments
    style_c_green = ps('C_GREEN', fontSize=11, fontName=font_regular, textColor=GREEN_FG, alignment=TA_CENTER)
    style_l_green = ps('L_GREEN', fontSize=11, fontName=font_regular, textColor=GREEN_FG)
    style_r_green = ps('R_GREEN', fontSize=11, fontName=font_regular, textColor=GREEN_FG, alignment=TA_RIGHT)

    style_c_green_bold = ps('C_GREEN_BOLD', fontSize=11, fontName=font_bold, textColor=GREEN_FG, alignment=TA_CENTER)
    style_l_green_bold = ps('L_GREEN_BOLD', fontSize=11, fontName=font_bold, textColor=GREEN_FG)
    style_r_green_bold = ps('R_GREEN_BOLD', fontSize=11, fontName=font_bold, textColor=GREEN_FG, alignment=TA_RIGHT)

    def cell_c(txt, color=None, bold=False):
        val = str(txt) if txt is not None else ''
        if color == GREEN_FG:
            style = style_c_green_bold if bold else style_c_green
        else:
            style = style_c_bold if bold else style_c_reg
        return Paragraph(val, style)

    def cell_l(txt, color=None, bold=False):
        val = str(txt) if txt is not None else ''
        if color == GREEN_FG:
            style = style_l_green_bold if bold else style_l_green
        else:
            style = style_l_bold if bold else style_l_reg
        return Paragraph(val, style)

    def cell_r(txt, color=None, bold=False):
        val = str(txt) if txt is not None else ''
        if color == GREEN_FG:
            style = style_r_green_bold if bold else style_r_green
        else:
            style = style_r_bold if bold else style_r_reg
        return Paragraph(val, style)

    col_d = usable_w * 0.160
    col_p = usable_w * 0.360
    col_n = usable_w * 0.160

    cur_sym = '(\u20b9)' if has_rupee else '(Rs.)'
    ldata = [[
        Paragraph('DATE', style_th_c),
        Paragraph('PARTICULARS', style_th_l),
        Paragraph(f'CREDIT {cur_sym}', style_th_r),
        Paragraph(f'RECEIVED {cur_sym}', style_th_r),
        Paragraph(f'BALANCE {cur_sym}', style_th_r),
    ]]
    running = 0.0

    for s in services:
        running += s['charge']
        dt = str(s['created_at'])[:10] if s['created_at'] else '\u2014'
        ldata.append([
            cell_c(dt),
            cell_l(s['service_name']),
            cell_r(f"{s['charge']:,.2f}"),
            cell_c('\u2014'),
            cell_r(f"{running:,.2f}")
        ])

    total_row_idx = None
    if services:
        total_row_idx = len(ldata)
        style_tot_c = ps('TOT_C', fontSize=11, fontName=font_bold, textColor=NAVY_DARK, alignment=TA_CENTER)
        style_tot_l = ps('TOT_L', fontSize=11, fontName=font_bold, textColor=NAVY_DARK)
        style_tot_r = ps('TOT_R', fontSize=11, fontName=font_bold, textColor=NAVY_DARK, alignment=TA_RIGHT)
        style_tot_mid_c = ps('TOT_MID_C', fontSize=11, fontName=font_bold, textColor=TEXT_MID, alignment=TA_CENTER)

        ldata.append([
            Paragraph('', style_tot_c),
            Paragraph('TOTAL CHARGES', style_tot_l),
            Paragraph(f"{total_charges:,.2f}", style_tot_r),
            Paragraph('\u2014', style_tot_mid_c),
            Paragraph(f"{total_charges:,.2f}", style_tot_r),
        ])

    payment_row_indices = []
    for p in payments:
        running -= p['amount']
        note_txt = f" ({p['note']})" if p['note'] else ''
        payment_row_indices.append(len(ldata))
        ldata.append([
            cell_c(p['date'], color=GREEN_FG),
            cell_l(f"Payment Received{note_txt}", color=GREEN_FG),
            cell_r('\u2014', color=GREEN_FG),
            cell_r(f"{p['amount']:,.2f}", color=GREEN_FG, bold=True),
            cell_r(f"{running:,.2f}", color=GREEN_FG, bold=True),
        ])

    ltbl = Table(ldata, colWidths=[col_d, col_p, col_n, col_n, col_n], repeatRows=1)
    tstyle = [
        ('BACKGROUND',    (0,0),(-1,0),  NAVY),
        ('TOPPADDING',    (0,0),(-1,0),  8),
        ('BOTTOMPADDING', (0,0),(-1,0),  8),
        ('LINEBELOW',     (0,0),(-1,-1), 0.5, BORDER),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ('TOPPADDING',    (0,1),(-1,-1), 6),
        ('BOTTOMPADDING', (0,1),(-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1),(-1, (total_row_idx-1) if total_row_idx else -1),
         [WHITE, ALT_ROW]),
    ]
    if total_row_idx is not None:
        tstyle += [
            ('BACKGROUND',    (0,total_row_idx),(-1,total_row_idx), SURFACE),
            ('LINEABOVE',     (0,total_row_idx),(-1,total_row_idx), 1, BORDER),
            ('LINEBELOW',     (0,total_row_idx),(-1,total_row_idx), 1, BORDER),
            ('TOPPADDING',    (0,total_row_idx),(-1,total_row_idx), 6),
            ('BOTTOMPADDING', (0,total_row_idx),(-1,total_row_idx), 6),
        ]
    for ri in payment_row_indices:
        tstyle.append(('BACKGROUND', (0,ri),(-1,ri), GREEN_BG))

    ltbl.setStyle(TableStyle(tstyle))
    elements += [ltbl, Spacer(1, 12)]

    # ════════════════════════════════════════════════════════════════════
    # 5. CLOSING — balance card + footer table (kept together)
    # ════════════════════════════════════════════════════════════════════
    if balance <= 0:
        bal_bg     = GREEN_BG
        bal_border = GREEN_FG
        bal_html   = (
            '<font color="#065F46" size="11"><b>ACCOUNT STATUS</b></font><br/>'
            f'<font color="#065F46" size="24"><b>{fmt_rupee(0)}</b></font><br/>'
            '<font color="#065F46" size="10"><b>FULLY PAID</b> - No outstanding dues</font>'
        )
    else:
        bal_bg     = NAVY_DARK
        bal_border = GOLD
        bal_html   = (
            '<font color="white" size="11"><b>OUTSTANDING BALANCE</b></font><br/>'
            f'<font color="#E8C547" size="24"><b>{fmt_rupee(balance)}</b></font><br/>'
            '<font color="#8A9BB0" size="10">Please pay before due date</font>'
        )

    bal_para = Paragraph(bal_html, ps('BAL', fontName=font_bold, alignment=TA_CENTER, leading=26))

    balance_tbl = Table([[bal_para]], colWidths=[usable_w])
    balance_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), bal_bg),
        ('BOX',           (0,0),(-1,-1), 1.5, bal_border),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 12),
        ('BOTTOMPADDING', (0,0),(-1,-1), 12),
        ('LEFTPADDING',   (0,0),(-1,-1), 14),
        ('RIGHTPADDING',  (0,0),(-1,-1), 14),
    ]))

    ft = ps('FT', fontSize=10, fontName=font_regular, textColor=TEXT_MID, leading=13)

    company_para = Paragraph(
        '<b>COMPANY</b><br/>'
        '<b>Gold Coin Consultancy<br/>Finance Services</b><br/>'
        'Laxmi Narayan Nivas Samor,<br/>Savarkar Nagar, Vita - 415311',
        ft)

    contact_para = Paragraph(
        '<b>CONTACT</b><br/>'
        'Ravikiran:<br/>+91 84216 24116<br/>'
        'Shriyash:<br/>+91 90216 74548',
        ft)

    bank_para = Paragraph(
        '<b>BANK DETAILS</b><br/>'
        'IDBI Bank<br/>'
        'A/C: 0640102000009416<br/>'
        'IFSC: IBKL0000640<br/>'
        'Branch: Vita',
        ft)

    qr_path = resource_path('static/qr_code.png')
    qr_size = 1.1 * inch
    if os.path.isfile(qr_path):
        qr_img = Image(qr_path, width=qr_size, height=qr_size)
        qr_col = Table([
            [qr_img],
            [Paragraph('Scan to Pay', ps('QRF_T', fontSize=9, fontName=font_bold, textColor=NAVY_DARK, alignment=TA_CENTER, leading=11))]
        ], colWidths=[qr_size + 8])
        qr_col.setStyle(TableStyle([
            ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0),(-1,-1), 0),
            ('BOTTOMPADDING', (0,0),(-1,-1), 0),
            ('LEFTPADDING',   (0,0),(-1,-1), 0),
            ('RIGHTPADDING',  (0,0),(-1,-1), 0),
            ('BOTTOMPADDING', (0,-1),(-1,-1), 4),
        ]))
    else:
        qr_col = Paragraph('<b>Scan to Pay</b><br/>(QR Code N/A)', ps('QRF_NA', fontSize=9, fontName=font_bold, textColor=NAVY_DARK, alignment=TA_CENTER, leading=11))

    footer_col_w1 = usable_w * 0.28
    footer_col_w2 = usable_w * 0.22
    footer_col_w3 = usable_w * 0.28
    footer_col_w4 = usable_w * 0.22

    footer_tbl = Table([[company_para, contact_para, bank_para, qr_col]], colWidths=[footer_col_w1, footer_col_w2, footer_col_w3, footer_col_w4])
    footer_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), SURFACE),
        ('BOX',           (0,0),(-1,-1), 1, BORDER),
        ('LINEAFTER',     (0,0),(2,-1),  0.5, BORDER),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
    ]))

    note = Paragraph(
        "E. &amp; O.E. - Errors and Omissions Excepted",
        ps('Note', fontSize=9, alignment=TA_CENTER, textColor=TEXT_LIGHT, fontName=font_regular, leading=11))

    elements.append(KeepTogether([
        balance_tbl,
        Spacer(1, 12),
        footer_tbl,
        Spacer(1, 8),
        note,
    ]))
    doc.build(elements)
    return buffer


@app.route('/backup_now', methods=['POST'])
@login_required
def backup_now():
    from backup.backup_service import create_backup

    try:
        result = create_backup(DB_PATH)
        flash(f"Backup created: {result['path']}", 'success')
    except Exception as e:
        flash(f"Backup failed: {e}", 'error')
    return redirect(url_for('index'))


@app.route('/restore', methods=['GET', 'POST'])
@login_required
def restore():
    if request.method == 'POST':
        file = request.files.get('file')
        mode = request.form.get('mode', 'append')

        if not file or file.filename == '':
            flash('Please select an .xlsx file.', 'error')
            return redirect(url_for('restore'))

        if not allowed_file(file.filename):
            flash('Only .xlsx files are allowed.', 'error')
            return redirect(url_for('restore'))

        safe = secure_filename(file.filename)
        tmp_path = os.path.join(BACKUP_DIR, f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe}")
        os.makedirs(BACKUP_DIR, exist_ok=True)
        file.save(tmp_path)

        try:
            from backup.restore_service import restore_from_excel
            result = restore_from_excel(tmp_path, DB_PATH, mode=mode)
            flash(f"Restore completed (sheets: {len(result['sheets'])}).", 'success')
        except Exception as e:
            flash(f"Restore failed: {e}", 'error')
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        return redirect(url_for('index'))

    return render_template('restore.html')


@app.route('/backup_logs')
@login_required
def backup_logs():
    log_path = os.path.join(LOG_DIR, 'backup_restore.log')
    entries = []
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            entries = f.read().strip().split('\n')[-200:]
    return render_template('backup_logs.html', entries=entries)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    conn = get_db()
    if request.method == 'POST':
        # Update settings in db
        keys = [
            'company_name', 'company_address', 'contact_1', 'contact_2',
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
            'smtp_security', 'smtp_sender_name', 'smtp_sender_email',
            'email_subject', 'email_body'
        ]
        for key in keys:
            val = request.form.get(key, '').strip()
            # Special check: keep existing password if not updated/provided
            if key == 'smtp_password' and not val:
                # Retrieve current password
                row = conn.execute("SELECT value FROM settings WHERE key='smtp_password'").fetchone()
                if row:
                    val = row['value']
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, val))

        # Save birthday settings
        for key in ['birthday_emails_enabled', 'birthday_send_html', 'birthday_include_offer']:
            val = '1' if request.form.get(key) else '0'
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, val))

        for key in ['birthday_email_time', 'birthday_sender_email']:
            val = request.form.get(key, '').strip()
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, val))

        conn.commit()
        conn.close()

        # Re-initialize the birthday scheduler job with new settings
        try:
            setup_birthday_scheduler()
        except NameError:
            pass

        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings_page'))

    # GET request
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    settings = {row['key']: row['value'] for row in rows}
    return render_template('settings.html', settings=settings)


@app.route('/api/test_smtp', methods=['POST'])
@login_required
def api_test_smtp():
    recipient = request.form.get('test_recipient', '').strip()
    if not recipient:
        return jsonify({'status': 'error', 'message': 'Test recipient email is required.'}), 400

    smtp_settings = {
        'smtp_host': request.form.get('smtp_host', '').strip(),
        'smtp_port': request.form.get('smtp_port', '').strip(),
        'smtp_user': request.form.get('smtp_user', '').strip(),
        'smtp_password': request.form.get('smtp_password', '').strip(),
        'smtp_security': request.form.get('smtp_security', 'STARTTLS').strip(),
        'smtp_sender_name': request.form.get('smtp_sender_name', 'Gold Coin Consultancy').strip(),
        'smtp_sender_email': request.form.get('smtp_sender_email', '').strip()
    }

    # If password is empty (and matches placeholder or not typed), retrieve it from db
    if not smtp_settings['smtp_password']:
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key='smtp_password'").fetchone()
        conn.close()
        if row:
            smtp_settings['smtp_password'] = row['value']

    try:
        verify_smtp_connection(smtp_settings, recipient)
        return jsonify({'status': 'success', 'message': f'Test email sent successfully to {recipient}!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/customer/<int:customer_id>/email_ledger', methods=['POST'])
@login_required
def email_ledger(customer_id):
    recipient = request.form.get('recipient_email', '').strip()
    subject = request.form.get('email_subject', '').strip()
    body = request.form.get('email_body', '').strip()

    if not recipient:
        return jsonify({'status': 'error', 'message': 'Recipient email is required.'}), 400

    conn = get_db()
    customer = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    if not customer:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Customer not found.'}), 404

    # Fetch SMTP settings from db
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    smtp_settings = {row['key']: row['value'] for row in rows}

    services = conn.execute('SELECT * FROM services WHERE customer_id=?', (customer_id,)).fetchall()
    payments = conn.execute('SELECT * FROM payments WHERE customer_id=? ORDER BY date', (customer_id,)).fetchall()

    # If the customer's email in DB is blank or different, update it
    if recipient and customer['email'] != recipient:
        conn.execute('UPDATE customers SET email = ? WHERE id = ?', (recipient, customer_id))
        conn.commit()

    conn.close()

    total_charges = sum(s['charge'] for s in services)
    total_received = sum(p['amount'] for p in payments)
    balance = total_charges - total_received

    # Compile the PDF in-memory
    buffer = BytesIO()
    generate_ledger_pdf(buffer, customer, services, payments, total_charges, total_received, balance)
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()

    filename = f"Ledger_{customer['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    try:
        send_ledger_email(recipient, pdf_bytes, filename, smtp_settings, custom_subject=subject, custom_body=body)
        return jsonify({'status': 'success', 'message': f'Ledger emailed successfully to {recipient}!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Optional automatic monthly backup using APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler

    def monthly_backup_job():
        from backup.backup_service import create_backup
        try:
            create_backup(DB_PATH)
            print('Monthly backup done')
        except Exception as exc:
            print('Monthly backup failed:', exc)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(monthly_backup_job, 'cron', day=1, hour=1, minute=0)
    scheduler.start()
except Exception:
    scheduler = None
    print('APScheduler not available; monthly backup disabled.')


def setup_birthday_scheduler():
    if not scheduler:
        return
    try:
        conn = get_db()
        row_enabled = conn.execute("SELECT value FROM settings WHERE key='birthday_emails_enabled'").fetchone()
        row_time = conn.execute("SELECT value FROM settings WHERE key='birthday_email_time'").fetchone()
        conn.close()

        enabled = (row_enabled['value'] == '1') if row_enabled else False
        time_str = row_time['value'] if row_time else '09:00'

        # Remove existing job if any
        try:
            scheduler.remove_job('birthday_job')
        except Exception:
            pass

        if enabled:
            try:
                hour, minute = map(int, time_str.split(':'))
            except ValueError:
                hour, minute = 9, 0

            def birthday_job_wrapper():
                from services.birthday_service import check_and_send_birthdays
                check_and_send_birthdays(DB_PATH)

            scheduler.add_job(
                birthday_job_wrapper,
                'cron',
                hour=hour,
                minute=minute,
                id='birthday_job'
            )
            print(f"[OK] Birthday email job scheduled daily at {time_str}")
    except Exception as e:
        print(f"Error setting up birthday scheduler: {e}")


def run_birthday_check_on_startup():
    import threading
    import time
    def check():
        time.sleep(5)
        try:
            from services.birthday_service import check_and_send_birthdays
            check_and_send_birthdays(DB_PATH)
        except Exception as e:
            print(f"Error running birthday check on startup: {e}")
    
    t = threading.Thread(target=check, daemon=True)
    t.start()


# Setup birthday scheduler and run check on startup
setup_birthday_scheduler()
run_birthday_check_on_startup()


if __name__ == '__main__':
    print("\n" + "=" * 56)
    print("  Gold Coin Consultancy — Desktop Billing System")
    print("=" * 56)
    print(f"  Database: {DB_PATH}")
    print("  URL:      http://localhost:5050")
    print("=" * 56 + "\n")
    app.run(debug=True, port=5050)
