
#!/usr/bin/env python3
"""
Simple test script for the Internet Search MCP server
"""
import subprocess
import json
import os

def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages"""

    # Start the MCP server process
    proc = subprocess.Popen(
        ["python", "server.py"],  # Change to your actual server filename
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

    # Test search_web tool
    search_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_web",
            "arguments": {
                "query": "Python asyncio tutorial",
                "format": "text"
            }
        }
    }

    print("\nSearching the web for 'Python asyncio tutorial'...")
    proc.stdin.write(json.dumps(search_request) + "\n")
    proc.stdin.flush()
    response = proc.stdout.readline()
    print(f"Search response: {response}")

    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP Internet Search Server Test")
    print("=" * 50)
    print()
