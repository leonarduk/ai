#!/usr/bin/env python3
"""
Test script for the data format MCP server
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
    
    # Test JSON parse
    json_parse_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "json_parse",
            "arguments": {
                "json_string": '{"name": "John", "age": 30, "city": "New York"}'
            }
        }
    }
    
    print("\nTesting JSON parse...")
    proc.stdin.write(json.dumps(json_parse_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"JSON parse response: {response}")
    
    # Test JSON generate
    json_gen_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "json_generate",
            "arguments": {
                "data": {
                    "users": [
                        {"name": "Alice", "age": 25},
                        {"name": "Bob", "age": 30}
                    ]
                },
                "indent": 2
            }
        }
    }
    
    print("\nTesting JSON generate...")
    proc.stdin.write(json.dumps(json_gen_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"JSON generate response: {response}")
    
    # Test XML parse
    xml_parse_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "xml_parse",
            "arguments": {
                "xml_string": '<person><name>John</name><age>30</age></person>'
            }
        }
    }
    
    print("\nTesting XML parse...")
    proc.stdin.write(json.dumps(xml_parse_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"XML parse response: {response}")
    
    # Test XML generate
    xml_gen_request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "xml_generate",
            "arguments": {
                "root_tag": "person",
                "data": {
                    "name": "Alice",
                    "age": 25,
                    "city": "Boston"
                },
                "pretty": True
            }
        }
    }
    
    print("\nTesting XML generate...")
    proc.stdin.write(json.dumps(xml_gen_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"XML generate response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP Data Format Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
