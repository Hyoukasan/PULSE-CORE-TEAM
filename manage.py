#!/usr/bin/env python
"""Entry point for Flask CLI commands."""

from app.main import create_app

if __name__ == '__main__':
    app = create_app()
    app.cli()
