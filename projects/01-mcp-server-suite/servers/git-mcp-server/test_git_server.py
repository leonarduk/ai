
import unittest
import sys
from unittest.mock import patch
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import actual server code
from server import run_git_command, list_tools, call_tool
from mcp.types import TextContent


class TestRunGitCommand(unittest.TestCase):
    """Unit tests for run_git_command"""

    @patch("subprocess.run")
    def test_run_git_command_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Success"
        mock_run.return_value.stderr = ""
        success, output = run_git_command("/fake/repo", ["status"])
        self.assertTrue(success)
        self.assertIn("Success", output)

    @patch("subprocess.run", side_effect=Exception("Unexpected error"))
    def test_run_git_command_exception(self, mock_run):
        success, output = run_git_command("/fake/repo", ["status"])
        self.assertFalse(success)
        self.assertIn("Unexpected error", output)

    @patch("subprocess.run", side_effect=TimeoutError("Command timed out"))
    def test_run_git_command_timeout(self, mock_run):
        success, output = run_git_command("/fake/repo", ["status"])
        self.assertFalse(success)
        self.assertIn("timed out", output.lower())


class TestListTools(unittest.IsolatedAsyncioTestCase):
    """Async tests for list_tools"""

    async def test_list_tools_returns_tools(self):
        tools = await list_tools()
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        self.assertTrue(any(tool.name == "git_status" for tool in tools))


class TestCallTool(unittest.IsolatedAsyncioTestCase):
    """Async tests for call_tool covering all Git operations"""

    @patch("server.Path.is_dir", return_value=False)
    async def test_invalid_directory(self, mock_path):
        result = await call_tool("git_status", {"repo_path": "/invalid/path"})
        self.assertIn("is not a directory", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    async def test_unknown_tool(self, mock_path):
        result = await call_tool("unknown_tool", {"repo_path": "/fake/repo"})
        self.assertIn("Unknown tool", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Git status OK"))
    async def test_git_status(self, mock_run, mock_path):
        result = await call_tool("git_status", {"repo_path": "/fake/repo"})
        self.assertIn("Git status OK", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Files added"))
    async def test_git_add(self, mock_run, mock_path):
        result = await call_tool("git_add", {"repo_path": "/fake/repo", "files": "."})
        self.assertIn("Added files", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Commit successful"))
    async def test_git_commit(self, mock_run, mock_path):
        result = await call_tool("git_commit", {"repo_path": "/fake/repo", "message": "Test commit"})
        self.assertIn("Commit successful", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Push successful"))
    async def test_git_push(self, mock_run, mock_path):
        result = await call_tool("git_push", {"repo_path": "/fake/repo", "remote": "origin", "branch": "main"})
        self.assertIn("Push successful", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Pull successful"))
    async def test_git_pull(self, mock_run, mock_path):
        result = await call_tool("git_pull", {"repo_path": "/fake/repo", "remote": "origin", "branch": "main"})
        self.assertIn("Pull successful", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Branch list"))
    async def test_git_branch_list(self, mock_run, mock_path):
        result = await call_tool("git_branch", {"repo_path": "/fake/repo", "action": "list"})
        self.assertIn("Branch list", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Branch created"))
    async def test_git_branch_create(self, mock_run, mock_path):
        result = await call_tool("git_branch", {"repo_path": "/fake/repo", "action": "create", "branch_name": "feature"})
        self.assertIn("Branch created", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Branch deleted"))
    async def test_git_branch_delete(self, mock_run, mock_path):
        result = await call_tool("git_branch", {"repo_path": "/fake/repo", "action": "delete", "branch_name": "feature"})
        self.assertIn("Branch deleted", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Checked out"))
    async def test_git_checkout(self, mock_run, mock_path):
        result = await call_tool("git_checkout", {"repo_path": "/fake/repo", "branch": "main"})
        self.assertIn("Checked out", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Log output"))
    async def test_git_log(self, mock_run, mock_path):
        result = await call_tool("git_log", {"repo_path": "/fake/repo", "max_count": 5})
        self.assertIn("Log output", result[0].text)

    @patch("server.Path.is_dir", return_value=True)
    @patch("server.run_git_command", return_value=(True, "Diff output"))
    async def test_git_diff(self, mock_run, mock_path):
        result = await call_tool("git_diff", {"repo_path": "/fake/repo", "cached": False})
        self.assertIn("Diff output", result[0].text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
