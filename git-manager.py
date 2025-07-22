import argparse
import requests
import sys
import json
import os
import dotenv
from datetime import datetime
from typing import List, Optional

dotenv.load_dotenv()

github_token = os.getenv("TOKEN")
if not github_token:
    print("GITHUB_TOKEN environment variable is not set.")
    sys.exit(1)

class GitHubAPIManager:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Manager-Script"
        }

    def make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request to GitHub API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code not in [200, 201, 204]:
                error_msg = response.json().get('message', 'Unknown error') if response.text else 'No response'
                print(f"❌ API Error ({response.status_code}): {error_msg} for {endpoint}")
                return None
            
            return response.json() if response.text else {}
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {str(e)}")
            return None
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response from {endpoint}")
            return None

    def list_orgs(self) -> List[str]:
        """List organizations user is a member of"""
        response = self.make_request("GET", "/user/memberships/orgs")
        if response is None:
            return []
        return [org['organization']['login'] for org in response]

    def list_teams(self, org: str) -> List[dict]:
        """List teams in an organization"""
        all_teams = []
        page = 1
        while True:
            response = self.make_request("GET", f"/orgs/{org}/teams?page={page}&per_page=100")
            if response is None:
                break
            if not response: # No more teams
                break
            all_teams.extend(response)
            page += 1
        return all_teams

    def list_repos(self, org: str) -> List[dict]:
        """List repositories in an organization"""
        all_repos = []
        page = 1
        while True:
            response = self.make_request("GET", f"/orgs/{org}/repos?page={page}&per_page=100")
            if response is None:
                break
            if not response: # No more repos
                break
            all_repos.extend(response)
            page += 1
        return all_repos

    def create_team(self, org: str, team_name: str, description: str = "") -> bool:
        """Create a team in an organization"""
        data = {
            "name": team_name,
            "description": description,
            "privacy": "closed"  # Can be 'secret' or 'closed'
        }
        response = self.make_request("POST", f"/orgs/{org}/teams", data)
        if response:
            print(f"✅ Created team '{team_name}' in '{org}'")
            return True
        return False

    def delete_team(self, org: str, team_slug: str) -> bool:
        """Delete a team from an organization"""
        response = self.make_request("DELETE", f"/orgs/{org}/teams/{team_slug}")
        if response is not None:
            print(f"✅ Deleted team '{team_slug}' in '{org}'")
            return True
        return False

    def add_team_to_repo(self, org: str, team_slug: str, repo: str, permission: str) -> bool:
        """Add team to repository with specific permission"""
        data = {"permission": permission}
        response = self.make_request("PUT", f"/orgs/{org}/teams/{team_slug}/repos/{org}/{repo}", data)
        if response is not None:
            print(f"✅ Added team '{team_slug}' to repo '{repo}' with permission '{permission}'")
            return True
        return False

    def remove_team_from_repo(self, org: str, team_slug: str, repo: str) -> bool:
        """Remove team from repository"""
        response = self.make_request("DELETE", f"/orgs/{org}/teams/{team_slug}/repos/{org}/{repo}")
        if response is not None:
            print(f"✅ Removed team '{team_slug}' from repo '{repo}'")
            return True
        return False

    def add_user_to_team(self, org: str, team_slug: str, username: str) -> bool:
        """Add user to team"""
        response = self.make_request("PUT", f"/orgs/{org}/teams/{team_slug}/memberships/{username}")
        if response:
            print(f"✅ Added user '{username}' to team '{team_slug}' in '{org}'")
            return True
        return False

    def remove_user_from_team(self, org: str, team_slug: str, username: str) -> bool:
        """Remove user from team"""
        response = self.make_request("DELETE", f"/orgs/{org}/teams/{team_slug}/memberships/{username}")
        if response is not None:
            print(f"✅ Removed user '{username}' from team '{team_slug}' in '{org}'")
            return True
        return False

    def create_repo(self, org: str, repo_name: str, private: bool = False, description: str = "") -> bool:
        """Create repository in organization"""
        data = {
            "name": repo_name,
            "description": description,
            "private": private,
            "has_issues": True,
            "has_projects": True,
            "has_wiki": True
        }
        response = self.make_request("POST", f"/orgs/{org}/repos", data)
        if response:
            visibility = "private" if private else "public"
            print(f"✅ Created {visibility} repo '{repo_name}' in '{org}'")
            return True
        return False

    def get_user_from_email(self, email: str, org: str = None) -> Optional[str]:
        """
        Attempt to get a GitHub username (login) from an email address.
        This is challenging due to GitHub API limitations for privacy.
        For users in an organization, it tries to list members and find public emails.
        A PAT with 'read:org' scope is often required for listing org members.
        """
        if not email:
            return None

        print(f"Attempting to resolve GitHub username for email: {email}")

        # Option 1: Search public users (less reliable, only if email is public on GitHub profile)
        # GitHub's public /search/users API might not always expose email directly for search.
        # This is not a direct email lookup API.
        # Try to find a user whose public profile has this email.
        # This isn't a robust solution for private emails.
        # response = self.make_request("GET", f"/search/users?q={email}+in:email")
        # if response and response.get('items'):
        #     # Take the first match, assuming it's the right one (risk of false positives)
        #     print(f"Found user '{response['items'][0]['login']}' via public search.")
        #     return response['items'][0]['login']

        # Option 2: List organization members and check their emails (more reliable for org members)
        # This requires 'read:org' scope for the PAT.
        if org:
            print(f"Searching for user with email '{email}' within organization '{org}'...")
            all_members = []
            page = 1
            while True:
                members_response = self.make_request("GET", f"/orgs/{org}/members?page={page}&per_page=100")
                if members_response is None or not members_response:
                    break
                all_members.extend(members_response)
                page += 1

            for member in all_members:
                # To get email for an org member, you might need to fetch their individual profile
                # or rely on the email being part of the org membership payload (often not).
                # A more direct way is if the email is PUBLIC on their profile.
                user_profile = self.make_request("GET", f"/users/{member['login']}")
                if user_profile and user_profile.get('email') and user_profile['email'].lower() == email.lower():
                    print(f"Found organization member '{member['login']}' with matching public email.")
                    return member['login']

        print(f"❌ Could not resolve GitHub username for email: {email}. "
              "User may not exist, email is private, or not an organization member (if org specified).")
        return None


    def validate_user_input(self, user_input: str, org: str = None) -> Optional[str]:
        """
        Validate if GitHub user exists or resolve email to username.
        Returns the GitHub username (login) or None if invalid/unresolvable.
        """
        if "@" in user_input:
            print(f"Email detected: '{user_input}'. Attempting to find GitHub username...")
            resolved_username = self.get_user_from_email(user_input, org)
            if resolved_username:
                print(f"✅ Email '{user_input}' resolved to username '{resolved_username}'.")
                return resolved_username
            else:
                print(f"❌ Could not resolve email '{user_input}' to a GitHub username.")
                return None
        else:
            # Assume it's already a username, validate it directly
            response = self.make_request("GET", f"/users/{user_input}")
            if response is not None:
                print(f"✅ GitHub username '{user_input}' is valid.")
                return user_input
            else:
                print(f"❌ GitHub username '{user_input}' is invalid or does not exist.")
                return None

    def get_user_repo_access(self, org: str, username: str) -> List[str]:
        """Get list of repositories user has access to in organization"""
        repos = self.list_repos(org)
        access_repos = []

        print(f"📆 Checking access for user '{username}' in organization '{org}'...")
        for repo in repos:
            # Check if user is a collaborator or has team access
            # Direct collaborator check
            collaborator_response = self.make_request("GET", f"/repos/{org}/{repo['name']}/collaborators/{username}/permission")
            if collaborator_response and 'permission' in collaborator_response:
                access_repos.append(f"{repo['name']} (Direct: {collaborator_response['permission']})")
                continue # Already found direct access, move to next repo

            # Check team access for this user on this repo
            # First, get teams the user belongs to in the org
            user_teams = self.make_request("GET", f"/orgs/{org}/memberships/{username}/teams")
            if user_teams:
                for team_membership in user_teams:
                    team_slug = team_membership['team']['slug']
                    # Get team's repo permissions
                    team_repo_permission = self.make_request("GET", f"/orgs/{org}/teams/{team_slug}/repos/{org}/{repo['name']}")
                    if team_repo_permission and 'permission' in team_repo_permission:
                        access_repos.append(f"{repo['name']} (Via team '{team_membership['team']['name']}': {team_repo_permission['permission']})")
                        break # Found access via a team, move to next repo

        print(f"\n📆 User '{username}' has access to {len(access_repos)} repositories in '{org}':")
        for repo_access_info in access_repos:
            print(f"  - {repo_access_info}")
        
        return access_repos

    def get_team_by_name(self, org: str, team_name: str) -> Optional[dict]:
        """Find team by name and return team info"""
        teams = self.list_teams(org)
        for team in teams:
            if team['name'].lower() == team_name.lower():
                return team
        return None
    
    def list_users(self, org: str) -> List[dict]:
        """List users (members) in an organization with their public email if available."""
        all_members = []
        page = 1
        while True:
            response = self.make_request("GET", f"/orgs/{org}/members?page={page}&per_page=100")
            if response is None:
                break
            if not response:
                break
            all_members.extend(response)
            page += 1
        
        users_with_emails = []
        print(f"📋 Members in organization '{org}' (fetching public emails):")
        for member in all_members:
            user_info = self.make_request("GET", f"/users/{member['login']}")
            if user_info:
                email = user_info.get('email', 'N/A (Private/No Public Email)')
                print(f"  - {member['login']} (Email: {email})")
                users_with_emails.append({'login': member['login'], 'email': email})
        return users_with_emails

    def list_users_with_access(self, org: str) -> None:
        """List users in an organization with their repo access levels"""
        users_info = self.list_users(org) # This now lists users with their emails
        repos = self.list_repos(org)
        print(f"\n📋 Users and their repository access in '{org}':")
        for user_data in users_info:
            user = user_data['login']
            email = user_data['email']
            print(f"\nUser: {user} (Email: {email})")
            for repo in repos:
                # Get permission level for user on repo
                endpoint = f"/repos/{org}/{repo['name']}/collaborators/{user}/permission"
                resp = self.make_request("GET", endpoint)
                if resp and 'permission' in resp:
                    print(f"  - {repo['name']}: {resp['permission']}")
                else:
                    # If not a direct collaborator, check if they have access via a team
                    # This is more complex and would involve iterating through the user's teams
                    # and then checking each team's access to the repo.
                    # For simplicity, if no direct collaboration, we'll mark as 'No Direct Access'
                    # A comprehensive check requires more API calls.
                    print(f"  - {repo['name']}: No Direct Access (may have team access)") # Improved message


def run_action(args):
    github = GitHubAPIManager(github_token)

    # Resolve user input (which could be email or username) to a username
    resolved_username = None
    if args.user:
        resolved_username = github.validate_user_input(args.user, args.org)
        if not resolved_username and args.action in ["add-user", "remove-user", "user-access"]:
            print(f"❌ Action '{args.action}' requires a valid GitHub username, "
                  f"but '{args.user}' could not be resolved.")
            sys.exit(1)

    if args.action == "list-orgs":
        orgs = github.list_orgs()
        print("📋 Organizations:")
        for org in orgs:
            print(f"  - {org}")

    elif args.action == "list-teams":
        teams = github.list_teams(args.org)
        print(f"📋 Teams in organization '{args.org}':")
        if teams:
            for i, team in enumerate(teams, 1):
                print(f"  {i}. {team['name']} (ID: {team['id']}, Slug: {team['slug']})")
        else:
            print("  No teams found.")

    elif args.action == "list-repos":
        repos = github.list_repos(args.org)
        print(f"📋 Repositories in organization '{args.org}':")
        if repos:
            for i, repo in enumerate(repos, 1):
                visibility = "🔒 Private" if repo['private'] else "🌐 Public"
                print(f"  {i}. {repo['name']} ({visibility})")
        else:
            print("  No repositories found.")

    elif args.action == "create-team":
        if not args.team:
            print("--team is required for create-team")
            sys.exit(1)
        github.create_team(args.org, args.team)

    elif args.action == "delete-team":
        if not args.team:
            print("--team is required for delete-team")
            sys.exit(1)
        team_info = github.get_team_by_name(args.org, args.team)
        if team_info:
            github.delete_team(args.org, team_info['slug'])
        else:
            print(f"❌ Team '{args.team}' not found in '{args.org}'")

    elif args.action == "add-repo":
        if not all([args.team, args.repo, args.permission]):
            print("--team, --repo, and --permission are required for add-repo")
            sys.exit(1)
        team_info = github.get_team_by_name(args.org, args.team)
        if team_info:
            github.add_team_to_repo(args.org, team_info['slug'], args.repo, args.permission)
        else:
            print(f"❌ Team '{args.team}' not found in '{args.org}'")

    elif args.action == "remove-repo":
        if not all([args.team, args.repo]):
            print("--team and --repo are required for remove-repo")
            sys.exit(1)
        team_info = github.get_team_by_name(args.org, args.team)
        if team_info:
            github.remove_team_from_repo(args.org, team_info['slug'], args.repo)
        else:
            print(f"❌ Team '{args.team}' not found in '{args.org}'")

    elif args.action in ["add-user", "remove-user"]:
        if not all([args.team, resolved_username]): # Use resolved_username
            print("--team and a valid user/email are required for user management")
            sys.exit(1)

        team_info = github.get_team_by_name(args.org, args.team)
        if not team_info:
            print(f"❌ Team '{args.team}' not found in '{args.org}'")
            sys.exit(1)

        if args.action == "add-user":
            github.add_user_to_team(args.org, team_info['slug'], resolved_username)
        else:
            github.remove_user_from_team(args.org, team_info['slug'], resolved_username)

    elif args.action == "create-repo":
        if not args.repo_name:
            print("--repo-name is required for create-repo")
            sys.exit(1)
        github.create_repo(args.org, args.repo_name, args.repo_private)

    elif args.action == "user-access":
        if not resolved_username: # Use resolved_username
            print("--user (email or username) is required for user-access")
            sys.exit(1)
        github.get_user_repo_access(args.org, resolved_username)

    elif args.action == "list-users": # New action to list users and their emails
        github.list_users(args.org)
    
    elif args.action == "list-users-access": # New action to list users and their repo access
        github.list_users_with_access(args.org)

def main():
    parser = argparse.ArgumentParser(description="GitHub Team and Repo Manager (Direct API)")
    
    parser.add_argument("--action",
                        choices=[
                            "create-team", "delete-team", "add-repo", "remove-repo",
                            "add-user", "remove-user", "create-repo", "user-access",
                            "list-teams", "list-repos", "list-orgs", "list-users", # Added list-users
                            "list-users-access" # Added list-users-access
                        ],
                        required=True,
                        help="Action to perform")
    
    parser.add_argument("--org", help="GitHub organization name")
    parser.add_argument("--team", help="Team name")
    parser.add_argument("--repo", help="Repository name")
    parser.add_argument("--user", help="GitHub username or email address") # Changed help text
    parser.add_argument("--permission",
                        choices=["pull", "triage", "push", "maintain", "admin"],
                        help="Permission level for team access to repository")
    parser.add_argument("--repo-private", action="store_true",
                        help="Create repository as private (default is public)")
    parser.add_argument("--repo-name", help="Name for new repository")

    args = parser.parse_args()
    
    # Check if org is required for the action
    if args.action not in ["list-orgs"] and not args.org:
        print(f"--org is required for {args.action}")
        sys.exit(1)
    
    run_action(args)

if __name__ == "__main__":
    main()
