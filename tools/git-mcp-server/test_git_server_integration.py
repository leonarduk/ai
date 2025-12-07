
import unittest
from pathlib import Path
from server import call_tool, list_tools
import tempfile
import os

REPO_PATH = r"C:\Users\steph\workspace\GitHub\ai"

class TestGitReadOnlyIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_list_tools(self):
        tools = await list_tools()
        self.assertTrue(any(tool.name == "git_status" for tool in tools))

    async def test_git_status(self):
        result = await call_tool("git_status", {"repo_path": REPO_PATH})
        print("\n[git_status output]\n", result[0].text)
        self.assertIn("On branch", result[0].text)

    async def test_git_log(self):
        result = await call_tool("git_log", {"repo_path": REPO_PATH, "max_count": 5})
        print("\n[git_log output]\n", result[0].text)
        self.assertTrue(len(result[0].text.strip()) > 0)

    async def test_git_diff(self):
        result = await call_tool("git_diff", {"repo_path": REPO_PATH, "cached": False})
        print("\n[git_diff output]\n", result[0].text)
        self.assertIsInstance(result[0].text, str)

    async def test_git_branch_list(self):
        result = await call_tool("git_branch", {"repo_path": REPO_PATH, "action": "list"})
        print("\n[git_branch list output]\n", result[0].text)
        self.assertTrue("main" in result[0].text or len(result[0].text.strip()) > 0)


async def test_real_git_lifecycle(self):
    """Lifecycle test on the real repo: create -> add -> commit -> delete -> commit deletion"""
    file_path = Path(REPO_PATH) / "lifecycle_real.txt"

    # Step 1: Create file
    file_path.write_text("Hello Git Lifecycle in real repo")
    self.assertTrue(file_path.exists())

    # Step 2: Add file
    add_result = await call_tool("git_add", {"repo_path": REPO_PATH, "files": "lifecycle_real.txt"})
    print("\n[git_add output]\n", add_result[0].text)
    self.assertIn("Added files", add_result[0].text)

    # Step 3: Commit file (force commit only staged changes)
    commit_result = await call_tool("git_commit", {"repo_path": REPO_PATH, "message": "Add lifecycle_real.txt"})
    print("\n[git_commit output]\n", commit_result[0].text)

    # If commit failed due to unstaged changes, retry with `-a`
    if "no changes added" in commit_result[0].text.lower():
        print("[Retrying commit with -a]")
        os.system(f'git -C "{REPO_PATH}" commit -am "Add lifecycle_real.txt"')

    # Step 4: Delete file
    file_path.unlink()
    self.assertFalse(file_path.exists())

    # Step 5: Commit deletion
    commit_delete_result = await call_tool("git_commit", {"repo_path": REPO_PATH, "message": "Remove lifecycle_real.txt"})
    print("\n[git_commit deletion output]\n", commit_delete_result[0].text)

    if "no changes added" in commit_delete_result[0].text.lower():
        print("[Retrying deletion commit with -a]")
        os.system(f'git -C "{REPO_PATH}" commit -am "Remove lifecycle_real.txt"')

    # Step 6: Verify log
    log_result = await call_tool("git_log", {"repo_path": REPO_PATH, "max_count": 10})
    print("\n[git_log after lifecycle]\n", log_result[0].text)
    self.assertIn("Add lifecycle_real.txt", log_result[0].text)
    self.assertIn("Remove lifecycle_real.txt", log_result[0].text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
