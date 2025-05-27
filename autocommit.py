from dataclasses import dataclass
import time
import jwt
import requests
from pathlib import Path
from git import Repo
from typing import Optional


@dataclass
class GitCredentials:
    app_id: str
    private_key_path: Path
    installation_id: str

    _token: str = None
    _token_expiry: float = 0

    def __post_init__(self):
        self.private_key_path = Path(self.private_key_path).resolve()

    @property
    def token(self) -> str:
        """Returns a valid access token, refreshing it if expired."""
        if self._token and time.time() <= self._token_expiry - 5:
            return self._token
        self._refresh_token()
        return self._token

    def _refresh_token(self):
        print("🔐 Refreshing GitHub App access token...")
        now = int(time.time())

        private_key = self.private_key_path.read_text()
        payload = {
            'iat': now,
            'exp': now + 540,
            'iss': self.app_id
        }

        jwt_token = jwt.encode(payload, private_key, algorithm='RS256')

        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github+json'
        }
        url = f'https://api.github.com/app/installations/{self.installation_id}/access_tokens'
        response = requests.post(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        self._token = data['token']
        self._token_expiry = time.mktime(time.strptime(data['expires_at'], "%Y-%m-%dT%H:%M:%SZ"))

    def get_header(self):
        """Return Authorization header for GitHub API."""
        return {'Authorization': f'token {self.token}'}



class AutoCommitter:
    def __init__(self, repo_path: str | Path, subfolder: str | Path,
                 credentials: GitCredentials):

        self.repo_path = Path(repo_path).resolve()
        self.subfolder_path = self.repo_path / subfolder
        self.credentials = credentials
        self.remote_name = 'origin'
        self.repo = Repo(self.repo_path)

        self._set_remote_token_auth()

    def _set_remote_token_auth(self):
        origin = self.repo.remotes[self.remote_name]
        origin.set_url(f"https://x-access-token:{self.credentials.token}@github.com/ThomasK1086/MLOps-FlowRepo.git")

    def pull(self, branch: Optional[str] = 'main'):
        print(f"📥 Pulling latest changes from {self.remote_name}/{branch}")
        self.repo.remotes[self.remote_name].pull(branch)

    def push(self, branch: Optional[str] = 'main', commit_message: Optional[str] = "Auto-commit") -> Optional[str]:
        print(f"📦 Staging changes in: {self.subfolder_path}")

        if not self.subfolder_path.exists():
            print(f"❌ Subfolder does not exist: {self.subfolder_path}")
            return None

        # Git status --porcelain returns concise output; filter to subfolder only
        changed_files = self.repo.git.status('--porcelain', str(self.subfolder_path)).strip().splitlines()

        if not changed_files:
            print("✅ No changes to commit.")
            return self.repo.head.commit.hexsha

        # Stage only changed files in subfolder
        self.repo.git.add(str(self.subfolder_path))
        print("📝 Committing changes...")
        commit = self.repo.index.commit(commit_message)
        print(f"🚀 Pushing to {self.remote_name}/{branch}...")
        self.repo.remotes[self.remote_name].push(branch)
        return commit.hexsha

    def checkout_subfolder_version(self, commit_hexsha: str, subfolder: str | Path):
        """
        Checkout a specific version of a subfolder from the given commit without changing the entire working directory.
        """
        subfolder_path = Path(subfolder) if not isinstance(subfolder, Path) else subfolder
        relative_path = str(subfolder_path)

        try:
            print(f"📦 Checking out subfolder '{relative_path}' at commit {commit_hexsha}")
            self.repo.git.checkout(commit_hexsha, '--', relative_path)
            print(f"✅ Subfolder restored to state from commit {commit_hexsha}")
        except Exception as e:
            print(f"❌ Failed to checkout subfolder: {e}")

