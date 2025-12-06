#!/usr/bin/env python3
"""
Simple test script for the email MCP server
"""
import subprocess
import json
import os
from pathlib import Path

def load_env():
    """Load environment variables from .env file in project root"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    env_vars = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages"""
    
    # Load env vars from .env file
    env = os.environ.copy()
    env_vars = load_env()
    env.update(env_vars)
    
    # Check if we have the required vars
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]
    missing = [var for var in required if var not in env_vars]
    if missing:
        print(f"ERROR: Missing environment variables in .env file: {', '.join(missing)}")
        print("\nPlease add these to C:\\Users\\steph\\workspace\\GitHub\\ai\\.env")
        return
    
    proc = subprocess.Popen(
        ["python", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
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
    
    # Test send_email
    test_email = env_vars.get("TEST_EMAIL_TO", "test@example.com")
    send_email_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "send_email",
            "arguments": {
                "to": test_email,
                "subject": "Test Email from MCP Server",
                "body": "This is a test email sent via the MCP server."
            }
        }
    }
    
    print(f"\nSending test email to {test_email}...")
    proc.stdin.write(json.dumps(send_email_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Send email response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP Email Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
