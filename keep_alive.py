import logging
from threading import Thread
from flask import Flask
from config import PORT

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Flask / Werkzeug loglarini kamaytirish
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.ERROR)


@app.route("/")
def home() -> str:
    return "Kino Bot Server Active & Running!"


@app.route("/health")
def health() -> str:
    return "OK"


def _run_server() -> None:
    try:
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Keep-alive serverini ishga tushirishda xatolik: {e}")


def keep_alive() -> None:
    """
    Render va boshqa bulutli hostinglarda bot uzluksiz ishlashini
    ta'minlash uchun Flask serverini alohida potokda (thread) ishga tushiradi.
    """
    thread = Thread(target=_run_server, daemon=True)
    thread.start()
    logger.info(f"Flask keep-alive veb-serveri {PORT}-portda ishga tushirildi.")