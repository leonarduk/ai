import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("git-server")

def run_git_command(repo_path: str, command: list[str]) -> tuple[bool, str]:
    """Run a git command and return success status and output"""
    try:
        result = subprocess.run(
            ["git"] + command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out after 30 seconds"
    except Exception as e:
        return False, str(e)

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="git_status",
            description="Show the working tree status",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="git_add",
            description="Add file contents to the staging area",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "files": {"type": "string", "description": "Files to add (e.g., '.', '*.py', 'file.txt')"}
                },
                "required": ["repo_path", "files"]
            }
        ),
        Tool(
            name="git_commit",
            description="Record changes to the repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "message": {"type": "string", "description": "Commit message"}
                },
                "required": ["repo_path", "message"]
            }
        ),
        Tool(
            name="git_push",
            description="Update remote refs along with associated objects",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "remote": {"type": "string", "description": "Remote name (default: origin)", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name (if empty, pushes current branch)"}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="git_pull",
            description="Fetch from and integrate with another repository or local branch",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "remote": {"type": "string", "description": "Remote name (default: origin)", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name (if empty, pulls current branch)"}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="git_branch",
            description="List, create, or delete branches",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "action": {"type": "string", "description": "Action: list, create, delete", "enum": ["list", "create", "delete"]},
                    "branch_name": {"type": "string", "description": "Branch name (for create/delete)"}
                },
                "required": ["repo_path", "action"]
            }
        ),
        Tool(
            name="git_checkout",
            description="Switch branches or restore working tree files",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "branch": {"type": "string", "description": "Branch name to checkout"}
                },
                "required": ["repo_path", "branch"]
            }
        ),
        Tool(
            name="git_log",
            description="Show commit logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "max_count": {"type": "integer", "description": "Limit the number of commits", "default": 10}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="git_diff",
            description="Show changes between commits, commit and working tree, etc",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to git repository"},
                    "cached": {"type": "boolean", "description": "Show staged changes", "default": False}
                },
                "required": ["repo_path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        repo_path = arguments["repo_path"]
        
        # Verify it's a git repository
        if not Path(repo_path).is_dir():
            return [TextContent(type="text", text=f"Error: {repo_path} is not a directory")]
        
        if name == "git_status":
            success, output = run_git_command(repo_path, ["status"])
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_add":
            files = arguments["files"]
            success, output = run_git_command(repo_path, ["add", files])
            if success:
                # Show what was added
                success2, status = run_git_command(repo_path, ["status", "--short"])
                return [TextContent(type="text", text=f"Added files matching '{files}'\n\n{status}")]
            return [TextContent(type="text", text=f"Error: {output}")]
        
        elif name == "git_commit":
            message = arguments["message"]
            success, output = run_git_command(repo_path, ["commit", "-m", message])
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_push":
            remote = arguments.get("remote", "origin")
            branch = arguments.get("branch", "")
            
            if branch:
                cmd = ["push", remote, branch]
            else:
                cmd = ["push", remote]
            
            success, output = run_git_command(repo_path, cmd)
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_pull":
            remote = arguments.get("remote", "origin")
            branch = arguments.get("branch", "")
            
            if branch:
                cmd = ["pull", remote, branch]
            else:
                cmd = ["pull", remote]
            
            success, output = run_git_command(repo_path, cmd)
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_branch":
            action = arguments["action"]
            
            if action == "list":
                success, output = run_git_command(repo_path, ["branch", "-a"])
            elif action == "create":
                branch_name = arguments.get("branch_name")
                if not branch_name:
                    return [TextContent(type="text", text="Error: branch_name required for create")]
                success, output = run_git_command(repo_path, ["branch", branch_name])
            elif action == "delete":
                branch_name = arguments.get("branch_name")
                if not branch_name:
                    return [TextContent(type="text", text="Error: branch_name required for delete")]
                success, output = run_git_command(repo_path, ["branch", "-d", branch_name])
            else:
                return [TextContent(type="text", text=f"Error: unknown action {action}")]
            
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_checkout":
            branch = arguments["branch"]
            success, output = run_git_command(repo_path, ["checkout", branch])
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_log":
            max_count = arguments.get("max_count", 10)
            success, output = run_git_command(
                repo_path, 
                ["log", f"--max-count={max_count}", "--oneline", "--decorate"]
            )
            return [TextContent(type="text", text=output if success else f"Error: {output}")]
        
        elif name == "git_diff":
            cached = arguments.get("cached", False)
            cmd = ["diff", "--cached"] if cached else ["diff"]
            success, output = run_git_command(repo_path, cmd)
            
            if not output:
                output = "No changes" if not cached else "No staged changes"
            
            return [TextContent(type="text", text=output)]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
