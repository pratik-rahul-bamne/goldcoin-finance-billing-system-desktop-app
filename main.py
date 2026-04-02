"""
main.py — Desktop entry point for Gold Coin Billing System
Starts Flask in a background thread, then opens PyWebView window.

Developed By PB Dev Company (pbdev100@gmail.com)
"""

import threading
import time
import sys
import os


def main():
    # Start Flask server in background
    from app import app, DEVELOPER_CREDIT, DEVELOPER_EMAIL

    def run_flask():
        app.run(host='127.0.0.1', port=5050, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Small delay to let Flask fully start before opening window
    time.sleep(1.2)
    print(f"  {DEVELOPER_CREDIT}")
    print(f"  {DEVELOPER_EMAIL}")

    import webview

    # Determine icon path
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, 'assets', 'icon.png')
    else:
        icon_path = os.path.join(os.path.abspath('.'), 'assets', 'icon.png')

    window = webview.create_window(
        title='Gold Coin Consultancy — Billing System',
        url='http://127.0.0.1:5050/login',
        width=1366,
        height=800,
        min_size=(1100, 650),
        resizable=True,
        text_select=True,
        confirm_close=True
    )

    webview.start(debug=False)


if __name__ == '__main__':
    main()
