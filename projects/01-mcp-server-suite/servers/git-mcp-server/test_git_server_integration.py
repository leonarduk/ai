import subprocess
import tempfile
import unittest
from pathlib import Path

from server import call_tool, list_tools


class TestGitReadOnlyIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests that exercise server.py against a real, isolated git repo.

    Each test runs against a throwaway temp directory (git-initialized with one
    commit) rather than a real developer checkout, so the suite is safe to run
    anywhere, including CI.
    """

    async def asyncSetUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self._temp_dir.name

        subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path, check=True)

        readme = Path(self.repo_path) / "README.md"
        readme.write_text("initial commit\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True
        )

    async def asyncTearDown(self):
        self._temp_dir.cleanup()

    async def test_list_tools(self):
        tools = await list_tools()
        self.assertTrue(any(tool.name == "git_status" for tool in tools))

    async def test_git_status(self):
        result = await call_tool("git_status", {"repo_path": self.repo_path})
        print("\n[git_status output]\n", result[0].text)
        self.assertIn("On branch", result[0].text)

    async def test_git_log(self):
        result = await call_tool("git_log", {"repo_path": self.repo_path, "max_count": 5})
        print("\n[git_log output]\n", result[0].text)
        self.assertTrue(len(result[0].text.strip()) > 0)

    async def test_git_diff(self):
        result = await call_tool("git_diff", {"repo_path": self.repo_path, "cached": False})
        print("\n[git_diff output]\n", result[0].text)
        self.assertIsInstance(result[0].text, str)

    async def test_git_branch_list(self):
        result = await call_tool("git_branch", {"repo_path": self.repo_path, "action": "list"})
        print("\n[git_branch list output]\n", result[0].text)
        self.assertTrue("main" in result[0].text or "master" in result[0].text or len(result[0].text.strip()) > 0)

    async def test_real_git_lifecycle(self):
        """Lifecycle test: create -> add -> commit -> delete -> commit deletion"""
        file_path = Path(self.repo_path) / "lifecycle_real.txt"

        # Step 1: Create file
        file_path.write_text("Hello Git Lifecycle in real repo")
        self.assertTrue(file_path.exists())

        # Step 2: Add file
        add_result = await call_tool("git_add", {"repo_path": self.repo_path, "files": "lifecycle_real.txt"})
        print("\n[git_add output]\n", add_result[0].text)
        self.assertIn("Added files", add_result[0].text)

        # Step 3: Commit file
        commit_result = await call_tool(
            "git_commit", {"repo_path": self.repo_path, "message": "Add lifecycle_real.txt"}
        )
        print("\n[git_commit output]\n", commit_result[0].text)
        self.assertNotIn("Error", commit_result[0].text)

        # Step 4: Delete file
        file_path.unlink()
        self.assertFalse(file_path.exists())

        # Step 5: Commit deletion
        add_delete_result = await call_tool("git_add", {"repo_path": self.repo_path, "files": "lifecycle_real.txt"})
        print("\n[git_add deletion output]\n", add_delete_result[0].text)

        commit_delete_result = await call_tool(
            "git_commit", {"repo_path": self.repo_path, "message": "Remove lifecycle_real.txt"}
        )
        print("\n[git_commit deletion output]\n", commit_delete_result[0].text)
        self.assertNotIn("Error", commit_delete_result[0].text)

        # Step 6: Verify log
        log_result = await call_tool("git_log", {"repo_path": self.repo_path, "max_count": 10})
        print("\n[git_log after lifecycle]\n", log_result[0].text)
        self.assertIn("Add lifecycle_real.txt", log_result[0].text)
        self.assertIn("Remove lifecycle_real.txt", log_result[0].text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
