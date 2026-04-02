"""
Gold Coin Consultancy Finance Services
Desktop Billing & Ledger System
Flask + SQLite + PyWebView

Developed By PB Dev Company (pbdev100@gmail.com)
"""

import os
import sys
import io
import atexit
import sqlite3
import hashlib
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, jsonify, send_file, session, flash)
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


# ── Path Handling for PyInstaller ──────────────────────────────────────────────
def resource_path(relative):
    """Absolute path to a bundled resource (templates/static). Works dev + PyInstaller."""
    base = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base, relative)


def data_path(filename):
    """Absolute path for persistent data files.

    In frozen (PyInstaller) mode we store data under %LOCALAPPDATA% so Windows
    installs work without admin permissions.
    """
    if getattr(sys, 'frozen', False):
        base = os.environ.get('LOCALAPPDATA') or os.path.abspath('.')
        app_dir = os.path.join(base, 'GoldCoinBilling')
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, filename)
    return os.path.join(os.path.abspath('.'), filename)


# ── Flask App ──────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=resource_path('templates'),
    static_folder=resource_path('static')
)
app.secret_key = 'goldcoin_billing_2025_secure_key_!@#$%'
DB_PATH = data_path('goldcoin_billing.db')
DEVELOPER_CREDIT = 'Developed By PB Dev Company'
DEVELOPER_EMAIL = 'pbdev100@gmail.com'
app.config['DEVELOPER_CREDIT'] = DEVELOPER_CREDIT
app.config['DEVELOPER_EMAIL'] = DEVELOPER_EMAIL


@app.context_processor
def inject_developer_credit():
    return {
        'developer_credit': DEVELOPER_CREDIT,
        'developer_email': DEVELOPER_EMAIL,
    }


@app.after_request
def add_developer_header(response):
    response.headers['X-App-Developer'] = DEVELOPER_CREDIT
    response.headers['X-App-Developer-Email'] = DEVELOPER_EMAIL
    return response


# ── Database Helpers ───────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    schema_path = resource_path('database.sql')
    conn = get_db()
    with open(schema_path, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[OK] SQLite database ready at: {DB_PATH}")


init_db()

# ── Backup / restore (Excel) ───────────────────────────────────────────────────
from services.backup_logger import log_error, log_info
from services.backup_service import (
    cleanup_old_backups,
    export_database,
    list_backup_files,
    run_scheduled_monthly_backup,
)
from services.import_service import import_workbook_stream, validate_workbook_stream
from services.paths import backup_dir, backup_log_file


def _start_monthly_backup_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        return None

    sched = BackgroundScheduler(daemon=True)

    def job():
        try:
            run_scheduled_monthly_backup(DB_PATH, backup_dir())
        except Exception as e:
            log_error(backup_log_file(), f"Scheduled backup job error: {e}")

    sched.add_job(
        job,
        CronTrigger(day=1, hour=4, minute=0),
        id="goldcoin_monthly_backup",
        replace_existing=True,
    )
    sched.start()
    atexit.register(lambda: sched.shutdown(wait=False))
    return sched


_start_monthly_backup_scheduler()


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


@app.route('/api/app-info')
def app_info():
    """Non-sensitive build / attribution metadata for tools and integrations."""
    return jsonify(
        app='Gold Coin Billing',
        developer=DEVELOPER_CREDIT,
        email=DEVELOPER_EMAIL,
    )


# ── Backup & Restore ───────────────────────────────────────────────────────────
@app.route('/backup')
@login_required
def backup_page():
    preview = session.pop('backup_preview', None)
    backups = list_backup_files(backup_dir())
    return render_template('backup_restore.html', backups=backups, preview=preview)


@app.route('/backup/run', methods=['POST'])
@login_required
def backup_run():
    bdir = backup_dir()
    log_path = backup_log_file()
    path, err = export_database(DB_PATH, bdir, log_path)
    if err:
        flash(f'Backup failed: {err}', 'error')
    else:
        flash(f'Backup saved: {os.path.basename(path)}', 'success')
    return redirect(url_for('backup_page'))


@app.route('/backup/cleanup', methods=['POST'])
@login_required
def backup_cleanup():
    n = cleanup_old_backups(backup_dir(), backup_log_file(), max_age_days=90, keep_minimum=10)
    flash(f'Retention cleanup removed {n} old file(s).', 'info')
    return redirect(url_for('backup_page'))


@app.route('/backup/import', methods=['POST'])
@login_required
def backup_import():
    from werkzeug.utils import secure_filename

    action = request.form.get('action', 'import')
    up = request.files.get('file')
    if not up or not up.filename:
        flash('Choose an Excel file first.', 'error')
        return redirect(url_for('backup_page'))
    if not up.filename.lower().endswith('.xlsx'):
        flash('Only .xlsx files are supported.', 'error')
        return redirect(url_for('backup_page'))

    raw = up.read()
    if not raw:
        flash('File is empty.', 'error')
        return redirect(url_for('backup_page'))

    mode = request.form.get('mode', 'append')
    duplicate_mobile = request.form.get('duplicate_mobile', 'reuse')
    merge_settings = request.form.get('merge_settings') == '1'

    if action == 'validate':
        conn = get_db()
        try:
            summary = validate_workbook_stream(io.BytesIO(raw), conn)
        except ValueError as e:
            flash(str(e), 'error')
            log_error(backup_log_file(), f"Import validate failed: {e}")
            return redirect(url_for('backup_page'))
        finally:
            conn.close()
        session['backup_preview'] = summary
        flash(f'Valid backup file ({secure_filename(up.filename)}).', 'success')
        return redirect(url_for('backup_page'))

    if action != 'import':
        flash('Unknown action.', 'error')
        return redirect(url_for('backup_page'))

    conn = get_db()
    try:
        stats = import_workbook_stream(
            io.BytesIO(raw),
            conn,
            mode=mode,
            merge_settings=merge_settings,
            duplicate_mobile=duplicate_mobile,
        )
    except ValueError as e:
        conn.rollback()
        flash(str(e), 'error')
        log_error(backup_log_file(), f"Import failed: {e}")
        return redirect(url_for('backup_page'))
    except Exception as e:
        conn.rollback()
        flash(f'Import error: {e}', 'error')
        log_error(backup_log_file(), f"Import failed: {e}")
        return redirect(url_for('backup_page'))
    finally:
        conn.close()

    log_info(
        backup_log_file(),
        f"Import OK mode={stats.get('mode')} file={secure_filename(up.filename)} "
        f"customers_inserted={stats.get('customers_inserted')} "
        f"customers_reused={stats.get('customers_reused')} "
        f"settings_keys={stats.get('settings_keys')}",
    )
    flash(
        f"Import finished ({stats.get('mode')}): "
        f"{stats.get('customers_inserted', 0)} customers inserted, "
        f"{stats.get('customers_reused', 0)} reused by mobile, "
        f"{stats.get('settings_keys', 0)} settings keys merged.",
        'success',
    )
    return redirect(url_for('backup_page'))


@app.route('/backup/download/<path:filename>')
@login_required
def backup_download(filename):
    from werkzeug.utils import secure_filename

    safe = secure_filename(filename)
    if not safe or safe != os.path.basename(filename):
        flash('Invalid file name.', 'error')
        return redirect(url_for('backup_page'))
    root = os.path.abspath(backup_dir())
    path = os.path.abspath(os.path.join(root, safe))
    try:
        if os.path.commonpath([root, path]) != root:
            flash('Invalid path.', 'error')
            return redirect(url_for('backup_page'))
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('backup_page'))
    if not os.path.isfile(path):
        flash('File not found.', 'error')
        return redirect(url_for('backup_page'))
    return send_file(path, as_attachment=True, download_name=safe)


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
        bank_name     = request.form.get('bank_name', '').strip()
        loan_amount   = request.form.get('loan_amount', 0) or 0
        customer_date = request.form.get('customer_date') or datetime.now().strftime('%Y-%m-%d')
        conn = get_db()
        conn.execute(
            'INSERT INTO customers (name,mobile,email,business_name,village,bank_name,loan_amount,customer_date) VALUES (?,?,?,?,?,?,?,?)',
            (name, mobile, email, business_name, village, bank_name, loan_amount, customer_date)
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
            'UPDATE customers SET name=?,mobile=?,email=?,business_name=?,village=?,bank_name=?,loan_amount=?,customer_date=? WHERE id=?',
            (request.form['name'], request.form['mobile'], request.form.get('email',''),
             request.form.get('business_name',''), request.form.get('village',''),
             request.form.get('bank_name',''), request.form.get('loan_amount',0) or 0,
             request.form.get('customer_date',''), customer_id)
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
    service_name   = request.form['service_name'].strip()
    default_charge = request.form.get('default_charge', 0) or 0
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO service_catalog (service_name,default_charge) VALUES (?,?)',
                 (service_name, default_charge))
    conn.commit()
    conn.close()
    flash(f'Service "{service_name}" added.', 'success')
    return redirect(url_for('service_catalog'))


@app.route('/service_catalog/edit/<int:service_id>', methods=['POST'])
@login_required
def edit_catalog_service(service_id):
    default_charge = request.form.get('default_charge', 0) or 0
    is_active      = request.form.get('is_active', 1)
    conn = get_db()
    conn.execute('UPDATE service_catalog SET default_charge=?,is_active=? WHERE id=?',
                 (default_charge, is_active, service_id))
    conn.commit()
    conn.close()
    flash('Service updated.', 'success')
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
    conn.close()

    total_charges  = sum(s['charge'] for s in services)
    total_received = sum(p['amount'] for p in payments)
    balance        = total_charges - total_received
    return render_template('bill.html', customer=customer, services=services, payments=payments,
                           total_charges=total_charges, total_received=total_received,
                           balance=balance, current_date=datetime.now().strftime('%d/%m/%Y'))


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
    """Generate a professional A4 PDF ledger."""
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=20, bottomMargin=20)
    elements = []
    styles   = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    # Header
    elements += [
        Paragraph("GOLD COIN CONSULTANCY FINANCE SERVICES",
                  ps('H', fontSize=22, fontName='Helvetica-Bold',
                     textColor=colors.HexColor('#1F3A5F'), alignment=TA_CENTER, spaceAfter=6)),
        Paragraph("Professional Financial Consultancy",
                  ps('Sub', fontSize=10, fontName='Helvetica-Bold',
                     textColor=colors.HexColor('#C9A227'), alignment=TA_CENTER, spaceAfter=12)),
        Paragraph("LEDGER ACCOUNT",
                  ps('T', fontSize=16, fontName='Helvetica-Bold',
                     textColor=colors.HexColor('#1F3A5F'), alignment=TA_CENTER,
                     spaceAfter=12, spaceBefore=4,
                     borderWidth=2, borderColor=colors.HexColor('#C9A227'),
                     borderPadding=6, backColor=colors.HexColor('#F8F9FA'))),
        Spacer(1, 12),
    ]

    # Customer info
    cdata = [['Customer Name:', customer['name'], 'Date:', datetime.now().strftime('%d/%m/%Y')]]
    if customer['business_name']:
        cdata.append(['Business:', customer['business_name'], '', ''])
    cdata += [
        ['Mobile:', customer['mobile'], 'Village:', customer['village'] or '-'],
        ['Bank:', customer['bank_name'] or '-', 'Loan Amt:', f"Rs. {customer['loan_amount']:,.0f}" if customer['loan_amount'] else '-'],
    ]
    ctbl = Table(cdata, colWidths=[1.4*inch, 2.6*inch, 1.2*inch, 1.8*inch])
    ctbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,-1), colors.HexColor('#1F3A5F')),
        ('BACKGROUND',    (2,0),(2,-1), colors.HexColor('#1F3A5F')),
        ('TEXTCOLOR',     (0,0),(0,-1), colors.white),
        ('TEXTCOLOR',     (2,0),(2,-1), colors.white),
        ('BACKGROUND',    (1,0),(1,-1), colors.HexColor('#F8F9FA')),
        ('BACKGROUND',    (3,0),(3,-1), colors.HexColor('#F8F9FA')),
        ('GRID',          (0,0),(-1,-1), 0.5, colors.HexColor('#1F3A5F')),
        ('FONTNAME',      (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTNAME',      (2,0),(2,-1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 9),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
    ]))
    elements += [ctbl, Spacer(1, 16)]

    # Transaction ledger
    elements.append(Paragraph("Transaction Ledger",
                               ps('Sec', fontSize=12, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1F3A5F'), spaceAfter=8)))
    ldata   = [['Date', 'Particulars', 'Credit (Rs.)', 'Received (Rs.)', 'Balance (Rs.)']]
    running = 0.0

    for s in services:
        running += s['charge']
        dt = str(s['created_at'])[:10] if s['created_at'] else '-'
        ldata.append([dt, s['service_name'], f"{s['charge']:,.0f}", '-', f"{running:,.0f}"])

    if services:
        ldata.append(['', 'TOTAL CHARGES', f"{total_charges:,.0f}", '-', f"{total_charges:,.0f}"])

    for p in payments:
        running -= p['amount']
        note_txt = f" ({p['note']})" if p['note'] else ''
        ldata.append([p['date'], f"Payment Received{note_txt}", '-', f"{p['amount']:,.0f}", f"{running:,.0f}"])

    ldata.append(['', 'FINAL BALANCE DUE', '', '', f"Rs. {balance:,.0f}"])

    ltbl   = Table(ldata, colWidths=[1.1*inch, 2.8*inch, 1.3*inch, 1.3*inch, 1.5*inch])
    tstyle = [
        ('BACKGROUND',    (0,0),(-1,0),  colors.HexColor('#1F3A5F')),
        ('TEXTCOLOR',     (0,0),(-1,0),  colors.whitesmoke),
        ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,0),  10),
        ('FONTSIZE',      (0,1),(-1,-1), 9),
        ('ALIGN',         (2,0),(-1,-1), 'RIGHT'),
        ('GRID',          (0,0),(-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('ROWBACKGROUNDS',(0,1),(-1,-2), [colors.white, colors.HexColor('#F8F9FA')]),
    ]

    tri = len(services) + 1
    if services:
        tstyle += [
            ('BACKGROUND', (0,tri),(-1,tri), colors.HexColor('#1F3A5F')),
            ('TEXTCOLOR',  (0,tri),(-1,tri), colors.white),
            ('FONTNAME',   (0,tri),(-1,tri), 'Helvetica-Bold'),
        ]

    pstart = tri + 1 if services else 1
    for i in range(len(payments)):
        ri = pstart + i
        tstyle += [
            ('BACKGROUND', (0,ri),(-1,ri), colors.HexColor('#D4EDDA')),
            ('TEXTCOLOR',  (0,ri),(-1,ri), colors.HexColor('#155724')),
        ]

    bri = len(ldata) - 1
    tstyle += [
        ('BACKGROUND', (0,bri),(-1,bri), colors.HexColor('#FFF3CD')),
        ('TEXTCOLOR',  (0,bri),(-1,bri), colors.HexColor('#856404')),
        ('FONTNAME',   (0,bri),(-1,bri), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,bri),(-1,bri), 11),
    ]
    ltbl.setStyle(TableStyle(tstyle))
    elements += [ltbl, Spacer(1, 16)]

    # Balance summary
    bal_text = ("ACCOUNT FULLY PAID — Balance: Rs. 0/-" if balance == 0
                else f"Outstanding Balance: Rs. {balance:,.0f}/-")
    elements.append(Paragraph(bal_text,
                               ps('Bal', fontSize=12, fontName='Helvetica-Bold',
                                  alignment=TA_CENTER, textColor=colors.HexColor('#1F3A5F'))))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("E. &amp; O.E. (Errors and Omissions Excepted)",
                               ps('Note', fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))
    elements.append(Spacer(1, 16))

    # Footer
    ft = ps('FT', fontSize=9, textColor=colors.HexColor('#333333'), leading=13)
    fdata = [[
        Paragraph("<b>Gold Coin Consultancy Finance Services</b><br/>"
                  "<font size=8>Laxmi Narayan Nivas Samor,<br/>"
                  "Savarkar Nagar, Vita, Khanapur,<br/>"
                  "Dist. Sangli - 415311</font>", ft),
        Paragraph("<b>Contact Numbers:</b><br/>"
                  "<font size=8>Ravikiran: +91 84216 24116<br/>"
                  "Shriyash: +91 90216 74548</font>", ft),
        Paragraph("<b>Services Offered:</b><br/>"
                  "<font size=8>Personal Loan, Business Loan<br/>"
                  "Mortgage Loan, Home Loan<br/>"
                  "Vehicle Loan, CMEGP/PMEGP<br/>"
                  "Annasaheb Patil Mahamandal Loans</font>", ft),
    ]]
    ftbl = Table(fdata, colWidths=[2.5*inch, 2*inch, 3.5*inch])
    ftbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#F8F9FA')),
        ('BOX',           (0,0),(-1,-1), 2, colors.HexColor('#C9A227')),
        ('GRID',          (0,0),(-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
    ]))
    elements.append(ftbl)
    doc.build(elements)
    return buffer


if __name__ == '__main__':
    print("\n" + "=" * 56)
    print("  Gold Coin Consultancy — Desktop Billing System")
    print("=" * 56)
    print(f"  Database: {DB_PATH}")
    print("  URL:      http://localhost:5050")
    print(f"  {DEVELOPER_CREDIT}")
    print(f"  {DEVELOPER_EMAIL}")
    print("=" * 56 + "\n")
    app.run(debug=True, port=5050)
