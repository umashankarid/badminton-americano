"""Desktop launcher: runs Flask app and opens browser."""
import threading
import webbrowser
import time
from app import app
from models import init_db

def start_server():
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    server = threading.Thread(target=start_server, daemon=True)
    server.start()
    time.sleep(1)
    webbrowser.open('http://127.0.0.1:5000')
    input('Press Enter to stop the server...')
