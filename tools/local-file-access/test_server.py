#!/usr/bin/env python3
"""
Simple test script for the local file access MCP server
"""
import subprocess
import json
import os
from pathlib import Path

def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages"""
    
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
    
    # Test list_directory
    list_dir_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "list_directory",
            "arguments": {
                "path": r"C:\Users\steph\workspace\GitHub\ai\tools"
            }
        }
    }
    
    print("\nListing tools directory...")
    proc.stdin.write(json.dumps(list_dir_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"List directory response: {response}")
    
    # Test search_files
    search_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "search_files",
            "arguments": {
                "path": r"C:\Users\steph\workspace\GitHub\ai\tools",
                "pattern": "server.py"
            }
        }
    }
    
    print("\nSearching for server.py files...")
    proc.stdin.write(json.dumps(search_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Search files response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP Local File Access Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
