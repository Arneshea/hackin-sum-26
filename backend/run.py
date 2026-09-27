"""
Local dev entry point. In production, run behind gunicorn:
  gunicorn 'app:create_app()' --bind 0.0.0.0:8000 --workers 1

Note: keep --workers 1 (or use a preload + shared model strategy) if
running the triage transformer in-process — each worker process would
otherwise load its own copy of the model (section 41S).
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
