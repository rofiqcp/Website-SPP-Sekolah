"""WSGI entry point. Gunicorn: `app:app`."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from spp import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=os.getenv("BACKEND_HOST", "0.0.0.0"), port=int(os.getenv("BACKEND_PORT", "5101")),
            debug=os.getenv("APP_ENV") == "development")
