from pathlib import Path
import importlib.util
from types import ModuleType
from typing import Optional
from datetime import datetime
import sys
import json
from mlflow import MlflowClient
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
import asyncio
import re
import os

from autocommit import GitCredentials, AutoCommitter

class FlowExecutor:
    def __init__(self, credentials: GitCredentials):
        self.repo_path = Path("./flows_git").resolve()
        self.credentials = credentials

    def run_flow(self, flow_name: str, *args, **kwargs):
        subfolder_path = self.repo_path / flow_name

        committer = AutoCommitter(
            repo_path=self.repo_path,
            subfolder=flow_name,
            credentials=self.credentials,
        )

        commit_id = committer.push(commit_message=f"Auto-push before running flow '{flow_name}' at {datetime.now().isoformat()}")
        print(f"📌 Flow pushed with commit ID: {commit_id}")
        self._execute_flow(subfolder_path, flow_name, commit_id, *args, **kwargs)


    def rerun_flow(self, flow_name: str, hexsha: str, *args, **kwargs):
        subfolder_path = self.repo_path / flow_name
        committer = AutoCommitter(
            repo_path=self.repo_path,
            subfolder=flow_name,
            credentials=self.credentials,
        )

        # Step 1 — Save current state before rerun
        print(f"💾 Saving current flow state before rerun...")
        commit_now = committer.push(commit_message=f"Pre-replay autosave of flow '{flow_name}' at {datetime.now().isoformat()}")
        print(f"✅ Saved as commit {commit_now}")

        # Step 2 — Pull and checkout the requested version
        print(f"🔁 Checking out flow '{flow_name}' at commit {hexsha}")
        committer.pull()
        committer.checkout_subfolder_version(hexsha, subfolder_path)

        # Step 3 — Run historical version
        self._execute_flow(subfolder_path, flow_name, hexsha, *args, **kwargs)

        # Step 4 — Restore the latest version
        print(f"⏪ Restoring original flow state from commit {commit_now}")
        committer.pull()
        committer.checkout_subfolder_version(commit_now, subfolder_path)
        print("✅ Restoration complete.")


    def reproduce_flow(self, flow_name: str, flow_run_id: str) -> None:
        flow_artifact = self.get_artifact(flow_name, flow_run_id)
        original_args = flow_artifact['kwargs']
        hexsha = flow_artifact['git_commit_hexsha']
        self.rerun_flow(flow_name, **original_args, hexsha=hexsha)

    def _load_flow_module(self, subfolder: Path) -> ModuleType:
        """Dynamically import the flow.py module from a given subfolder."""
        flow_file = subfolder / "flow.py"
        if not flow_file.exists():
            raise FileNotFoundError(f"No flow.py found in {subfolder}")

        sys.path.insert(0, str(subfolder.resolve()))

        spec = importlib.util.spec_from_file_location("flow", str(flow_file))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


    @staticmethod
    def get_artifact(flow_name: str, flow_run_id: str) -> dict:
        async def _read_json_from_artifact():
            result = None
            async with get_client() as client:
                artifacts = await client.read_artifacts(
                    flow_run_filter=FlowRunFilter(
                        id=FlowRunFilterId(any_=[flow_run_id])
                    )
                )
                print(f"[DEBUG] Found {len(artifacts)} artifacts")
                for artifact in artifacts:
                    print(f"[DEBUG] Artifact key: {artifact.key}")
                    if artifact.key == flow_name.replace("_", "-"):
                        print(f"[DEBUG] Found matching artifact for {flow_name}")
                        print(f"[DEBUG] Artifact content:\n{artifact.data}")
                        # Extract JSON from markdown code block
                        match = re.search(r"```json\s*\n(.*?)\n```", artifact.data, re.DOTALL)
                        if match:
                            try:
                                result = json.loads(match.group(1))
                            except json.JSONDecodeError as e:
                                print(f"[ERROR] JSON decode error: {e}")
                        else:
                            print("[ERROR] No JSON code block found")
            return result

        artifact = asyncio.run(_read_json_from_artifact())

        if not artifact:
            raise FileNotFoundError(f"Could not load artifact for flow '{flow_name}' and run ID '{flow_run_id}'")

        return artifact

    def _execute_flow(self, subfolder_path: Path, flow_name: str, commit_id: str, *args, **kwargs):
        dockerfile = subfolder_path / "Dockerfile"

        # If Dockerfile exists, run in container
        if dockerfile.exists():
            print("🐳 Dockerfile found — running flow in container...")
            self._execute_flow_in_container(subfolder_path, flow_name, commit_id,*args, **kwargs)

        else:
            print("⚙️ No Dockerfile found — running flow locally.")
            self._execute_flow_locally(subfolder_path, flow_name, commit_id, *args, **kwargs)

    def _execute_flow_locally(self, subfolder_path: Path, flow_name: str, commit_id: str, *args, **kwargs):
        module = self._load_flow_module(subfolder_path)
        if not hasattr(module, "main"):
            raise AttributeError(f"'main' function not found in {subfolder_path}/flow.py")

        print(f"🚀 Executing flow '{flow_name}'...")
        module.main(*args, **kwargs, commit_id=commit_id)

    def _execute_flow_in_container(self, subfolder_path: Path, flow_name: str, commit_id: str, *args, **kwargs):
        import docker
        client = docker.from_env()
        tag = f"{flow_name.lower()}_flow:latest"

        # Build image
        print("🔧 Building Docker image...")
        image, _ = client.images.build(path=str(subfolder_path), tag=tag)

        # Prepare args and kwargs as JSON
        args_json = json.dumps({"args": args, "kwargs": kwargs, "commit_id": commit_id})

        prefect_url = os.getenv("PREFECT_API_URL")
        if "127.0.0.1" in prefect_url or "localhost" in prefect_url or prefect_url is None:
            prefect_url = "http://host.docker.internal:4200/api"

        mlflow_url = os.getenv("MLFLOW_TRACKING_URI")
        if "127.0.0.1" in mlflow_url or "localhost" in mlflow_url or mlflow_url is None:
            mlflow_url = "http://host.docker.internal:8080/"


        env_vars = {
            "PREFECT_API_URL": prefect_url,
            "MLFLOW_TRACKING_URI": mlflow_url,
            "GIT_PYTHON_REFRESH": 'quiet'
        }

        # Start container asynchronously
        print("🚀 Launching Docker container...")
        container = client.containers.run(
            image=tag,
            command=f"python flows_git/{flow_name}/flow.py '{args_json}'",
            working_dir="/project",
            volumes={
                str(Path.cwd().resolve()): {"bind": "/project", "mode": "rw"}
            },
            network_mode="bridge",  # enable networking for Prefect server
            environment=env_vars,
            detach=True,
            mem_limit="8g",
            nano_cpus=2_000_000_000,  # 2 CPUs
            stdout=True,
            stderr=True,
            remove=True
        )

        logs = container.logs(stream=True)
        for line in logs:
            print(line.decode().strip())

class Hyperparameters():
    def __init__(self, filepath):
        self.filepath = filepath
        self.set_default_hyperparameters()

    def set_default_hyperparameters(self):
        model_hyperparameters = {
            "max_depth": 10,
            "n_estimators": 30,
            "min_samples_split": 5,
            "min_samples_leaf":2,
            "random_state": 42
        }
        self.model_hyperparameters = model_hyperparameters
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(model_hyperparameters, indent=2))

    def __str__(self):
        return str(self.model_hyperparameters)

    def change_to_new_hyperparameters(self):
        model_hyperparameters = {
            "max_depth": 20,
            "n_estimators": 100,
            "min_samples_split": 3,
            "min_samples_leaf": 5,
            "random_state": 42
        }
        self.model_hyperparameters = model_hyperparameters
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(model_hyperparameters, indent=2))