#!/usr/bin/env python3
"""Direct test of GitHub API calls to debug the issue"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env - try multiple locations
script_dir = Path(__file__).parent
env_locations = [
    script_dir.parent.parent / '.env',  # C:\Users\steph\workspace\GitHub\ai\.env
    Path.cwd() / '.env',
    Path.home() / '.env'
]

env_loaded = False
for env_path in env_locations:
    if env_path.exists():
        print(f"Found .env at: {env_path}")
        load_dotenv(env_path)
        env_loaded = True
        break

if not env_loaded:
    print("WARNING: No .env file found, trying to load from current directory")
    load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

print("=" * 60)
print("GitHub API Direct Test")
print("=" * 60)

# Check token
if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN not found in environment")
    sys.exit(1)

print(f"Token found: {GITHUB_TOKEN[:10]}...")
print()

# Test API connection
headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

print("TEST 1: Get repo info for leonarduk/allotmint")
print("-" * 60)
try:
    response = requests.get(
        "https://api.github.com/repos/leonarduk/allotmint",
        headers=headers,
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Repo Name: {data['name']}")
        print(f"Full Name: {data['full_name']}")
        print(f"Description: {data.get('description', 'N/A')}")
        print(f"Default Branch: {data['default_branch']}")
        print(f"Stars: {data['stargazers_count']}")
        print("✓ SUCCESS")
    else:
        print(f"ERROR: {response.text}")
except Exception as e:
    print(f"EXCEPTION: {e}")

print()
print("TEST 2: List pull requests")
print("-" * 60)
try:
    response = requests.get(
        "https://api.github.com/repos/leonarduk/allotmint/pulls",
        headers=headers,
        params={"state": "all"},
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        prs = response.json()
        print(f"Total PRs found: {len(prs)}")
        if prs:
            for pr in prs[:5]:  # Show first 5
                print(f"  #{pr['number']}: {pr['title']} ({pr['state']})")
        else:
            print("  No pull requests found")
        print("✓ SUCCESS")
    else:
        print(f"ERROR: {response.text}")
except Exception as e:
    print(f"EXCEPTION: {e}")

print()
print("TEST 3: List branches")
print("-" * 60)
try:
    response = requests.get(
        "https://api.github.com/repos/leonarduk/allotmint/branches",
        headers=headers,
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        branches = response.json()
        print(f"Total branches: {len(branches)}")
        for branch in branches[:10]:  # Show first 10
            print(f"  - {branch['name']}")
        print("✓ SUCCESS")
    else:
        print(f"ERROR: {response.text}")
except Exception as e:
    print(f"EXCEPTION: {e}")

print()
print("TEST 4: Check rate limit")
print("-" * 60)
try:
    response = requests.get(
        "https://api.github.com/rate_limit",
        headers=headers,
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        core = data['resources']['core']
        print(f"Rate Limit: {core['remaining']}/{core['limit']}")
        print(f"Resets at: {core['reset']}")
        print("✓ SUCCESS")
    else:
        print(f"ERROR: {response.text}")
except Exception as e:
    print(f"EXCEPTION: {e}")

print()
print("=" * 60)
print("Testing complete!")
print("=" * 60)
