#!/usr/bin/env python3
"""
Test script for the file processing MCP server
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
    
    # Test CSV write
    test_csv_path = r"C:\Users\steph\workspace\GitHub\ai\tools\file_processing_mcp_server\test_data.csv"
    csv_write_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "csv_write",
            "arguments": {
                "path": test_csv_path,
                "header": ["Name", "Age", "City"],
                "data": [
                    ["Alice", "25", "New York"],
                    ["Bob", "30", "Boston"],
                    ["Charlie", "35", "Chicago"]
                ]
            }
        }
    }
    
    print("\nTesting CSV write...")
    proc.stdin.write(json.dumps(csv_write_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"CSV write response: {response}")
    
    # Test CSV read
    csv_read_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "csv_read",
            "arguments": {
                "path": test_csv_path,
                "has_header": True
            }
        }
    }
    
    print("\nTesting CSV read...")
    proc.stdin.write(json.dumps(csv_read_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"CSV read response: {response}")
    
    # Test Excel write
    test_excel_path = r"C:\Users\steph\workspace\GitHub\ai\tools\file_processing_mcp_server\test_data.xlsx"
    excel_write_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "excel_write",
            "arguments": {
                "path": test_excel_path,
                "header": ["Product", "Price", "Quantity"],
                "data": [
                    ["Widget A", 19.99, 100],
                    ["Widget B", 29.99, 50],
                    ["Widget C", 39.99, 25]
                ],
                "sheet_name": "Products"
            }
        }
    }
    
    print("\nTesting Excel write...")
    proc.stdin.write(json.dumps(excel_write_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    print(f"Excel write response: {response}")
    
    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()
    
    # Clean up test files
    try:
        Path(test_csv_path).unlink(missing_ok=True)
        Path(test_excel_path).unlink(missing_ok=True)
        print("\nTest files cleaned up")
    except Exception as e:
        print(f"\nWarning: Could not clean up test files: {e}")

if __name__ == "__main__":
    print("MCP File Processing Server Test")
    print("=" * 50)
    print()
    test_mcp_server()
