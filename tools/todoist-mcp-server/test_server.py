#!/usr/bin/env python3
"""
Test script for the Todoist MCP server
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
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    return env_vars

def send_request(proc, request):
    """Send a JSON-RPC request and get response"""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return proc.stdout.readline()

def initialize_server(proc):
    """Initialize the MCP server"""
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
    response = send_request(proc, init_request)
    print(f"Initialize response: {response}")
    return response

def list_tools(proc):
    """List available tools"""
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    response = send_request(proc, list_tools_request)
    print(f"Tools list response: {response}\n")
    return response

def create_task(proc, request_id, title, description="", date="", priority="", labels=None, assignee=""):
    """Create a Todoist task"""
    if labels is None:
        labels = []
    
    arguments = {
        "title": title
    }
    
    if description:
        arguments["description"] = description
    if date:
        arguments["date"] = date
    if priority:
        arguments["priority"] = priority
    if labels:
        arguments["labels"] = labels
    if assignee:
        arguments["assignee"] = assignee
    
    create_task_request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "create_todoist_task",
            "arguments": arguments
        }
    }
    
    # Build display string
    display_parts = [f"'{title}'"]
    if date:
        display_parts.append(f"date={date}")
    if labels:
        display_parts.append(f"labels={labels}")
    if priority:
        display_parts.append(f"priority={priority}")
    if assignee:
        display_parts.append(f"assignee={assignee}")
    
    print(f"Creating task: {', '.join(display_parts)}")
    if description:
        print(f"  Description: {description}")
    response = send_request(proc, create_task_request)
    print(f"Response: {response}\n")
    return response

class TodoistMCPTests:
    """Test suite for Todoist MCP server based on examples from Todoist documentation"""
    
    def __init__(self, proc):
        self.proc = proc
        self.request_id = 3
    
    def test_basic_task(self):
        """Test creating a basic task with no special formatting"""
        print("=" * 60)
        print("TEST 1: Basic task")
        print("=" * 60)
        create_task(self.proc, self.request_id, 
                   "Send weekly team update")
        self.request_id += 1
    
    def test_task_with_date(self):
        """Test: Join our next event! <date Friday> p1"""
        print("=" * 60)
        print("TEST 2: Task with date and priority")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Join our next event!",
                   date="Friday",
                   priority="p1")
        self.request_id += 1
    
    def test_task_with_date_label_priority(self):
        """Test: Fwd: Tomorrow's meeting <date tomorrow> @work p2"""
        print("=" * 60)
        print("TEST 3: Task with date, label, and priority")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Fwd: Tomorrow's meeting",
                   date="tomorrow",
                   labels=["work"],
                   priority="p2")
        self.request_id += 1
    
    def test_task_with_label_priority_date(self):
        """Test: Re: Office supplies @email p3 <date next Wednesday>"""
        print("=" * 60)
        print("TEST 4: Task with label, priority, and date")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Re: Office supplies",
                   labels=["email"],
                   priority="p3",
                   date="next Wednesday")
        self.request_id += 1
    
    def test_task_with_specific_date(self):
        """Test task with specific date format"""
        print("=" * 60)
        print("TEST 5: Task with specific date (12/22)")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Prepare year-end report",
                   date="12/22",
                   priority="p1")
        self.request_id += 1
    
    def test_recurring_task(self):
        """Test task with recurring date"""
        print("=" * 60)
        print("TEST 6: Recurring task (every other day)")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Check project status",
                   date="every other day",
                   labels=["work"])
        self.request_id += 1
    
    def test_recurring_monthly_task(self):
        """Test task with monthly recurring date"""
        print("=" * 60)
        print("TEST 7: Recurring monthly task (every last day)")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Submit monthly expenses",
                   date="every last day",
                   labels=["finance"],
                   priority="p2")
        self.request_id += 1
    
    def test_task_with_body(self):
        """Test task with both subject and body"""
        print("=" * 60)
        print("TEST 8: Task with detailed description")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Review quarterly report",
                   description="Check the financial summary and prepare notes for the team meeting. "
                              "Include analysis of Q3 performance and projections for Q4.",
                   date="tomorrow",
                   labels=["work"],
                   priority="p1")
        self.request_id += 1
    
    def test_multiple_labels(self):
        """Test task with multiple labels"""
        print("=" * 60)
        print("TEST 9: Task with multiple labels")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Quick response needed",
                   labels=["email", "urgent"],
                   priority="p1")
        self.request_id += 1
    
    def test_task_next_week(self):
        """Test task with 'next week' date"""
        print("=" * 60)
        print("TEST 10: Task scheduled for next week")
        print("=" * 60)
        create_task(self.proc, self.request_id,
                   title="Plan team building activity",
                   date="next Monday",
                   labels=["work"])
        self.request_id += 1

def run_tests():
    """Run all tests"""
    # Load env vars from .env file
    env = os.environ.copy()
    env_vars = load_env()
    env.update(env_vars)
    
    # Check if we have the required vars
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "TODOIST_EMAIL"]
    missing = [var for var in required if var not in env_vars]
    if missing:
        print(f"ERROR: Missing environment variables in .env file: {', '.join(missing)}")
        print("\nPlease add these to C:\\Users\\steph\\workspace\\GitHub\\ai\\.env")
        return
    
    print("Todoist MCP Server Test Suite")
    print("=" * 60)
    print(f"Testing with Todoist email: {env_vars.get('TODOIST_EMAIL', 'unknown')}")
    print("=" * 60)
    print()
    
    # Start the server
    proc = subprocess.Popen(
        ["python", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=os.path.dirname(__file__)
    )
    
    try:
        # Initialize server
        initialize_server(proc)
        print()
        
        # List available tools
        list_tools(proc)
        
        # Run all tests
        tests = TodoistMCPTests(proc)
        tests.test_basic_task()
        tests.test_task_with_date()
        tests.test_task_with_date_label_priority()
        tests.test_task_with_label_priority_date()
        tests.test_task_with_specific_date()
        tests.test_recurring_task()
        tests.test_recurring_monthly_task()
        tests.test_task_with_body()
        tests.test_multiple_labels()
        tests.test_task_next_week()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    finally:
        # Cleanup
        proc.stdin.close()
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_tests()
