-- Gold Coin Consultancy Finance Services
-- Desktop Billing System — SQLite Schema
-- Converted from PostgreSQL for local desktop use

PRAGMA foreign_keys = ON;

-- Settings table (stores admin password and app config)
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Default admin password: admin123 (will be hashed on first login)
INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'admin123');
INSERT OR IGNORE INTO settings (key, value) VALUES ('company_name', 'Gold Coin Consultancy Finance Services');
INSERT OR IGNORE INTO settings (key, value) VALUES ('company_address', 'Laxmi Narayan Nivas Samor, Savarkar Nagar, Vita, Khanapur, Dist. Sangli - 415311');
INSERT OR IGNORE INTO settings (key, value) VALUES ('contact_1', '+91 84216 24116');
INSERT OR IGNORE INTO settings (key, value) VALUES ('contact_2', '+91 90216 74548');

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    mobile        TEXT NOT NULL,
    email         TEXT DEFAULT '',
    business_name TEXT DEFAULT '',
    village       TEXT DEFAULT '',
    bank_name     TEXT DEFAULT '',
    loan_amount   REAL DEFAULT 0,
    customer_date TEXT,
    created_at    TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Global service catalog
CREATE TABLE IF NOT EXISTS service_catalog (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name   TEXT NOT NULL UNIQUE,
    default_charge REAL DEFAULT 0,
    is_active      INTEGER DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Per-customer service instances
CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    service_name TEXT NOT NULL,
    charge       REAL NOT NULL DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Payments received from customers
CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    amount      REAL NOT NULL DEFAULT 0,
    note        TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_services_customer      ON services(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_customer      ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_service_catalog_active ON service_catalog(is_active);
CREATE INDEX IF NOT EXISTS idx_customers_name         ON customers(name);
CREATE INDEX IF NOT EXISTS idx_customers_mobile       ON customers(mobile);

-- Pre-seeded service catalog (17 standard services)
INSERT OR IGNORE INTO service_catalog (service_name, default_charge) VALUES
    ('Xerox', 0),
    ('ITR', 0),
    ('Search Report', 0),
    ('Valuation Report', 0),
    ('Plan Design & Estimate', 0),
    ('Rubber Stamp', 0),
    ('Agreement', 0),
    ('Typing', 0),
    ('Data Entry', 0),
    ('Stamp Duty', 0),
    ('Aadhaar-PAN Colour Xerox', 0),
    ('7/12', 0),
    ('Guarantor for Mortgage', 0),
    ('Affidavit', 0),
    ('Vendor Fee', 0),
    ('Dast Xerox', 0),
    ('Consultancy Charge (2%)', 0);
