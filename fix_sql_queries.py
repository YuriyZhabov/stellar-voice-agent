#!/usr/bin/env python3
"""
Script to fix SQLAlchemy 2.0 compatibility issues by wrapping raw SQL strings with text().
"""

import os
import re
from pathlib import Path

def fix_sql_queries_in_file(file_path):
    """Fix SQL queries in a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Add text import if not present
    if 'from sqlalchemy import' in content and 'text' not in content:
        # Find the sqlalchemy import line and add text to it
        content = re.sub(
            r'from sqlalchemy import ([^)]+)',
            lambda m: f'from sqlalchemy import {m.group(1)}, text' if 'text' not in m.group(1) else m.group(0),
            content
        )
    
    # Fix execute calls with raw SQL strings
    patterns = [
        # Pattern for await session.execute("SELECT ...")
        (r'await\s+(\w+)\.execute\(\s*"([^"]+)"\s*\)', r'await \1.execute(text("\2"))'),
        # Pattern for await session.execute('SELECT ...')
        (r"await\s+(\w+)\.execute\(\s*'([^']+)'\s*\)", r"await \1.execute(text('\2'))"),
        # Pattern for session.execute("SELECT ...")
        (r'(\w+)\.execute\(\s*"([^"]+)"\s*\)', r'\1.execute(text("\2"))'),
        # Pattern for session.execute('SELECT ...')
        (r"(\w+)\.execute\(\s*'([^']+)'\s*\)", r"\1.execute(text('\2'))"),
        # Pattern for conn.execute("SELECT ...")
        (r'(\w+)\.execute\(\s*"([^"]+)"\s*\)', r'\1.execute(text("\2"))'),
        # Pattern for conn.execute('SELECT ...')
        (r"(\w+)\.execute\(\s*'([^']+)'\s*\)", r"\1.execute(text('\2'))"),
    ]
    
    for pattern, replacement in patterns:
        # Only replace if it's not already wrapped with text()
        matches = re.finditer(pattern, content)
        for match in matches:
            full_match = match.group(0)
            if 'text(' not in full_match:
                content = content.replace(full_match, re.sub(pattern, replacement, full_match))
    
    # Fix specific patterns for multi-line SQL
    multiline_patterns = [
        # Pattern for """SELECT ..."""
        (r'await\s+(\w+)\.execute\(\s*"""([^"]+)"""\s*\)', r'await \1.execute(text("""\2"""))'),
        (r"await\s+(\w+)\.execute\(\s*'''([^']+)'''\s*\)", r"await \1.execute(text('''\2'''))"),
        (r'(\w+)\.execute\(\s*"""([^"]+)"""\s*\)', r'\1.execute(text("""\2"""))'),
        (r"(\w+)\.execute\(\s*'''([^']+)'''\s*\)", r"\1.execute(text('''\2'''))"),
    ]
    
    for pattern, replacement in multiline_patterns:
        matches = re.finditer(pattern, content, re.DOTALL)
        for match in matches:
            full_match = match.group(0)
            if 'text(' not in full_match:
                content = content.replace(full_match, re.sub(pattern, replacement, full_match, flags=re.DOTALL))
    
    # Write back if changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
        return True
    
    return False

def main():
    """Main function to fix all Python files."""
    # Files to fix
    files_to_fix = [
        'src/database/connection.py',
        'src/database/repository.py',
        'src/database/migrations.py',
        'tests/test_database/test_connection.py',
        'tests/test_database/test_repository.py',
        'tests/test_database/test_migrations.py',
        'tests/test_database/test_logging_integration.py',
    ]
    
    fixed_count = 0
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            if fix_sql_queries_in_file(file_path):
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")
    
    print(f"\nFixed {fixed_count} files")

if __name__ == '__main__':
    main()