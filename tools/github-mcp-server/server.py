import asyncio
import os
import json
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent
import requests
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

# Load .env file - try multiple locations
script_dir = Path(__file__).parent
env_locations = [
    script_dir.parent.parent / '.env',  # C:\Users\steph\workspace\GitHub\ai\.env
    Path.cwd() / '.env',
]

for env_path in env_locations:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

# GitHub Personal Access Token - set this in your environment
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

app = Server("github-server")

def get_headers():
    """Get headers for GitHub API requests"""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def parse_repo(repo_url_or_name: str) -> tuple[str, str]:
    """Parse repository into owner and repo name"""
    # Handle both URLs and owner/repo format
    if repo_url_or_name.startswith("http"):
        parsed = urlparse(repo_url_or_name)
        parts = parsed.path.strip("/").split("/")
        return parts[0], parts[1]
    else:
        parts = repo_url_or_name.split("/")
        return parts[0], parts[1]

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_repo_info",
            description="Get information about a GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="list_branches",
            description="List all branches in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="list_pull_requests",
            description="List pull requests in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "state": {"type": "string", "description": "State: open, closed, or all", "default": "open"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="create_pull_request",
            description="Create a new pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description"},
                    "head": {"type": "string", "description": "Branch with changes"},
                    "base": {"type": "string", "description": "Target branch (default: main)"}
                },
                "required": ["repo", "title", "head"]
            }
        ),
        Tool(
            name="get_pull_request",
            description="Get details of a specific pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "pr_number": {"type": "integer", "description": "Pull request number"}
                },
                "required": ["repo", "pr_number"]
            }
        ),
        Tool(
            name="list_issues",
            description="List issues in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "state": {"type": "string", "description": "State: open, closed, or all", "default": "open"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="create_issue",
            description="Create a new issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue description"},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Issue labels"}
                },
                "required": ["repo", "title"]
            }
        ),
        Tool(
            name="get_file_content",
            description="Get the content of a file from a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "path": {"type": "string", "description": "File path in repo"},
                    "ref": {"type": "string", "description": "Branch, tag, or commit (default: default branch)"}
                },
                "required": ["repo", "path"]
            }
        ),
        Tool(
            name="list_commits",
            description="List commits in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "sha": {"type": "string", "description": "Branch or commit to start from"},
                    "per_page": {"type": "integer", "description": "Results per page (max 100)", "default": 30}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="search_repositories",
            description="Search for GitHub repositories",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "sort": {"type": "string", "description": "Sort by: stars, forks, updated"},
                    "per_page": {"type": "integer", "description": "Results per page (max 100)", "default": 30}
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_repo_info":
            owner, repo = parse_repo(arguments["repo"])
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            info = {
                "name": data["name"],
                "full_name": data["full_name"],
                "description": data.get("description"),
                "url": data["html_url"],
                "stars": data["stargazers_count"],
                "forks": data["forks_count"],
                "open_issues": data["open_issues_count"],
                "default_branch": data["default_branch"],
                "created_at": data["created_at"],
                "updated_at": data["updated_at"]
            }
            return [TextContent(type="text", text=json.dumps(info, indent=2))]
        
        elif name == "list_branches":
            owner, repo = parse_repo(arguments["repo"])
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/branches",
                headers=get_headers()
            )
            response.raise_for_status()
            branches = [b["name"] for b in response.json()]
            return [TextContent(type="text", text="\n".join(branches))]
        
        elif name == "list_pull_requests":
            owner, repo = parse_repo(arguments["repo"])
            state = arguments.get("state", "open")
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                params={"state": state},
                headers=get_headers()
            )
            response.raise_for_status()
            
            prs = []
            for pr in response.json():
                prs.append(f"#{pr['number']} - {pr['title']} ({pr['state']}) by {pr['user']['login']}")
            
            result = "\n".join(prs) if prs else f"No {state} pull requests found"
            return [TextContent(type="text", text=result)]
        
        elif name == "create_pull_request":
            owner, repo = parse_repo(arguments["repo"])
            data = {
                "title": arguments["title"],
                "body": arguments.get("body", ""),
                "head": arguments["head"],
                "base": arguments.get("base", "main")
            }
            
            response = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                json=data,
                headers=get_headers()
            )
            response.raise_for_status()
            pr = response.json()
            
            result = f"Created PR #{pr['number']}: {pr['title']}\nURL: {pr['html_url']}"
            return [TextContent(type="text", text=result)]
        
        elif name == "get_pull_request":
            owner, repo = parse_repo(arguments["repo"])
            pr_number = arguments["pr_number"]
            
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=get_headers()
            )
            response.raise_for_status()
            pr = response.json()
            
            info = {
                "number": pr["number"],
                "title": pr["title"],
                "body": pr["body"],
                "state": pr["state"],
                "author": pr["user"]["login"],
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "url": pr["html_url"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "mergeable": pr.get("mergeable"),
                "merged": pr.get("merged", False)
            }
            return [TextContent(type="text", text=json.dumps(info, indent=2))]
        
        elif name == "list_issues":
            owner, repo = parse_repo(arguments["repo"])
            state = arguments.get("state", "open")
            
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/issues",
                params={"state": state},
                headers=get_headers()
            )
            response.raise_for_status()
            
            issues = []
            for issue in response.json():
                if "pull_request" not in issue:  # Skip PRs
                    issues.append(f"#{issue['number']} - {issue['title']} ({issue['state']}) by {issue['user']['login']}")
            
            result = "\n".join(issues) if issues else f"No {state} issues found"
            return [TextContent(type="text", text=result)]
        
        elif name == "create_issue":
            owner, repo = parse_repo(arguments["repo"])
            data = {
                "title": arguments["title"],
                "body": arguments.get("body", "")
            }
            if "labels" in arguments:
                data["labels"] = arguments["labels"]
            
            response = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/issues",
                json=data,
                headers=get_headers()
            )
            response.raise_for_status()
            issue = response.json()
            
            result = f"Created issue #{issue['number']}: {issue['title']}\nURL: {issue['html_url']}"
            return [TextContent(type="text", text=result)]
        
        elif name == "get_file_content":
            owner, repo = parse_repo(arguments["repo"])
            path = arguments["path"]
            ref = arguments.get("ref")
            
            params = {}
            if ref:
                params["ref"] = ref
            
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                params=params,
                headers=get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            import base64
            content = base64.b64decode(data["content"]).decode("utf-8")
            return [TextContent(type="text", text=content)]
        
        elif name == "list_commits":
            owner, repo = parse_repo(arguments["repo"])
            params = {"per_page": arguments.get("per_page", 30)}
            if "sha" in arguments:
                params["sha"] = arguments["sha"]
            
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                params=params,
                headers=get_headers()
            )
            response.raise_for_status()
            
            commits = []
            for commit in response.json():
                commits.append(
                    f"{commit['sha'][:7]} - {commit['commit']['message'].split(chr(10))[0]} "
                    f"by {commit['commit']['author']['name']}"
                )
            
            return [TextContent(type="text", text="\n".join(commits))]
        
        elif name == "search_repositories":
            params = {
                "q": arguments["query"],
                "per_page": arguments.get("per_page", 30)
            }
            if "sort" in arguments:
                params["sort"] = arguments["sort"]
            
            response = requests.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=get_headers()
            )
            response.raise_for_status()
            
            repos = []
            for repo in response.json()["items"]:
                repos.append(
                    f"{repo['full_name']} - {repo.get('description', 'No description')} "
                    f"(⭐ {repo['stargazers_count']})"
                )
            
            return [TextContent(type="text", text="\n".join(repos))]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except requests.exceptions.HTTPError as e:
        error_msg = f"GitHub API error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_msg += f" - {error_data.get('message', '')}"
        except:
            pass
        return [TextContent(type="text", text=error_msg)]
    
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
