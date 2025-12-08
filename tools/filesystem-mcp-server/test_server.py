
#!/usr/bin/env python3
"""
Test script for the Filesystem MCP server, including edit_file functionality
"""
import subprocess
import json
import os
from pathlib import Path

def send_request(proc, request):
    """Send a JSON-RPC request and return the response"""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return proc.stdout.readline()

def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages"""

    # Start the MCP server process
    proc = subprocess.Popen(
        ["python", "server.py"],  # Adjust filename if needed
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.path.dirname(__file__)
    )

    # Initialize
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
    print(send_request(proc, init_request))

    # List tools
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    print("\nSending tools/list request...")
    print(send_request(proc, list_tools_request))

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
    print(send_request(proc, list_dir_request))

    # Test get_file_info
    file_info_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_file_info",
            "arguments": {
                "path": r"C:\Users\steph\workspace\GitHub\ai\tools\filesystem-mcp-server\server.py"
            }
        }
    }
    print("\nGetting file info...")
    print(send_request(proc, file_info_request))

    # Prepare a temporary file for edit_file test
    test_file = Path(r"C:\Users\steph\workspace\test_edit.txt")
    test_file.write_text("Line 1\nLine 2\nLine 3", encoding="utf-8")

    # Test edit_file: replace line 2
    edit_request_replace = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "edit_file",
            "arguments": {
                "path": str(test_file),
                "action": "replace",
                "line_number": 2,
                "content": "This is the new line 2"
            }
        }
    }
    print("\nReplacing line 2 in test file...")
    print(send_request(proc, edit_request_replace))

    # Test edit_file: add a line at position 4
    edit_request_add = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "edit_file",
            "arguments": {
                "path": str(test_file),
                "action": "add",
                "line_number": 4,
                "content": "Added line 4"
            }
        }
    }
    print("\nAdding line 4 in test file...")
    print(send_request(proc, edit_request_add))

    # Test edit_file: delete line 1
    edit_request_delete = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "edit_file",
            "arguments": {
                "path": str(test_file),
                "action": "delete",
                "line_number": 1
            }
        }
    }
    print("\nDeleting line 1 in test file...")
    print(send_request(proc, edit_request_delete))

    # Show final file content
    print("\nFinal file content:")
    print(test_file.read_text(encoding="utf-8"))

    # Cleanup
    proc.stdin.close()
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    print("MCP Filesystem Server Test (with edit_file)")
    print("=" * 50)
    print()
    test_mcp_server()
