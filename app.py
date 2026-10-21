"""Streamlit Cloud entry point for the shed demonstration."""
from pathlib import Path
exec(compile(Path(__file__).with_name('shed_app.py').read_text(encoding='utf-8'), str(Path(__file__).with_name('shed_app.py')), 'exec'))
