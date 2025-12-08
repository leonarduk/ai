#!/usr/bin/env python3
"""
Test script for the data operations MCP server
"""
import subprocess
import json
import os
import sqlite3
from pathlib import Path

def setup_test_db():
    """Create a test SQLite database"""
    db_path = Path(__file__).parent / "test.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            age INTEGER
        )
    """)
    
    cursor.execute("DELETE FROM users")  # Clear existing data
    
    cursor.executemany("""
        INSERT INTO users (name, email, age) VALUES (?, ?, ?)
    """, [
        ("Alice Smith", "alice@example.com", 25),
        ("Bob Jones", "bob@example.com", 30),
        ("Charlie Brown", "charlie@example.com", 35)
    ])
    
    conn.commit()
    conn.close()
    
    return str(db_path)

def cleanup_test_db(db_path):
    """Remove test database"""
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception as e:
        print(f"Warning: Could not delete test database: {e}")

def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages"""
    
    # Setup test database
    db_path = setup_test_db()
    print(f"Created test database at: {db_path}\n")
    
    proc = subprocess.Popen(
        ["python", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.path.dirname(__file__)
    )
    
    # Initialize the connection
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    print("Sending initialize request...")
    proc.stdin.write(json.dumps(init_request) + "\n")
    proc.stdin.flush()
    
    # Read response
    response = proc.stdout.readline()
    print(f"Initialize response: {response}")
    
    # List tools
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    print("\nSending tools/list request...")
    proc.stdin.write(json.dumps(list_tools_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Tools list response: {response}")
    
    # Test SQLite query
    query_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "sqlite_query",
            "arguments": {
                "db_path": db_path,
                "query": "SELECT * FROM users WHERE age >= 30"
            }
        }
    }
    
    print("\nTesting SQLite query...")
    proc.stdin.write(json.dumps(query_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Query response: {response}")
    
    # Test datetime operations
    datetime_now_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "datetime_now",
            "arguments": {
                "format": "iso"
            }
        }
    }
    
    print("\nTesting datetime now...")
    proc.stdin.write(json.dumps(datetime_now_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Datetime response: {response}")
    
    # Test text search
    text_search_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "text_search",
            "arguments": {
                "text": "The quick brown fox jumps over the lazy dog",
                "pattern": "the",
                "case_sensitive": False
            }
        }
    }
    
    print("\nTesting text search...")
    proc.stdin.write(json.dumps(text_search_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Text search response: {response}")
    
    # Test encryption
    encrypt_request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "encrypt_text",
            "arguments": {
                "text": "This is a secret message",
                "password": "MySecretPassword123"
            }
        }
    }
    
    print("\nTesting encryption...")
    proc.stdin.write(json.dumps(encrypt_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Encrypt response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()
    
    # Clean up test database
    cleanup_test_db(db_path)
    print("\nTest database cleaned up")

if __name__ == "__main__":
    print("MCP Data Operations Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
