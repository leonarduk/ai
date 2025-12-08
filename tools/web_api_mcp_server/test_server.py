#!/usr/bin/env python3
"""
Test script for the web API MCP server
"""
import subprocess
import json
import os

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
    
    # Test HTTP GET with a public API
    get_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "http_get",
            "arguments": {
                "url": "https://api.github.com/zen"
            }
        }
    }
    
    print("\nTesting HTTP GET request...")
    proc.stdin.write(json.dumps(get_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"GET response: {response}")
    
    # Test HTTP POST with JSONPlaceholder
    post_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "http_post",
            "arguments": {
                "url": "https://jsonplaceholder.typicode.com/posts",
                "json_data": {
                    "title": "Test Post",
                    "body": "This is a test",
                    "userId": 1
                }
            }
        }
    }
    
    print("\nTesting HTTP POST request...")
    proc.stdin.write(json.dumps(post_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"POST response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP Web API Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
