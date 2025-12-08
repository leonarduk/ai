#!/usr/bin/env python3
"""
Simple test script for the OS info MCP server
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
    
    # Test get_cpu_usage
    cpu_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_cpu_usage",
            "arguments": {
                "interval": 1
            }
        }
    }
    
    print("\nGetting CPU usage...")
    proc.stdin.write(json.dumps(cpu_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"CPU usage response: {response}")
    
    # Test get_memory_usage
    memory_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_memory_usage",
            "arguments": {}
        }
    }
    
    print("\nGetting memory usage...")
    proc.stdin.write(json.dumps(memory_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Memory usage response: {response}")
    
    # Test get_system_info
    system_info_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "get_system_info",
            "arguments": {}
        }
    }
    
    print("\nGetting system info...")
    proc.stdin.write(json.dumps(system_info_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"System info response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP OS Info Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
