"""Desktop launcher: runs Flask app in a native window."""
import threading
import webview
from app import app, init_db

def start_server():
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    server = threading.Thread(target=start_server, daemon=True)
    server.start()
    webview.create_window('Komet Badminton Americano', 'http://127.0.0.1:5000', width=1200, height=800)
    webview.start()
