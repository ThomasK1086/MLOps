import os
from dotenv import load_dotenv
from pathlib import Path
import json




from autocommit import AutoCommitter, GitCredentials
from flowexecutor import FlowExecutor, Hyperparameters







"""
def test_connections():
    "Test if we can connect to Prefect and mlflow server"
    status = True
    try:
        with get_client(sync_client=True) as client:
            response = client.hello()
        print(f"✅ Connected to Prefect server at")
    except Exception as e:
        status = False
        print(f"❌ Failed to connect to Prefect: {e}")

    try:
        # Try to list experiments to test connection
        experiments = mlflow.search_experiments()
        print(f"✅ Connected to MLflow server")
    except Exception as e:
        status = False
        print(f"❌ Failed to connect to MLflow: {e}")
    return status
"""


if __name__ == '__main__':
    load_dotenv()
    prefect_url = os.getenv("PREFECT_API_URL")
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not prefect_url:
        os.environ["PREFECT_API_URL"] = "http://host.docker.internal:4200/api"
        prefect_url = os.getenv("PREFECT_API_URL")
    if not mlflow_uri:
        os.environ["MLFLOW_TRACKING_URI"] = "http://host.docker.internal:8080/"
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    print(f"Env variables are {prefect_url} and {mlflow_uri}")

    # This is needed to pull/push to the remote repository that versions the flow source code
    creds = GitCredentials(
        app_id=os.getenv("APP_ID"),
        private_key_path=os.getenv("PRIVATE_KEY_PATH"),
        installation_id=os.getenv("INSTALLATION_ID"),
    )
    hp_path = Path("./flows_git/training_flow/model_hyperparameters.txt")
    model_hyperparameters = Hyperparameters(hp_path)


    training_args = {
        "output_dir": './data_flow1',
        "outfile_name": "steam_games_dataset.csv",
        "report_name": "report.html",
        "model_name": "RandomForestMulticlassifier",
        "cutoff_year": 2020
    }

    # This is the wrapper class that runs an versions flows
    executor = FlowExecutor(credentials=creds)

    # Run first training flow (this is exercise 2 basically)
    #executor.run_flow("training_flow", **training_args)

    print(f"\n\n\n-=-----------------------=-\n")
    # At this point, we simulate change the model architecture directly in the code.
    # This is not an input parameter and thus can only be tracked via the source code
    # Note that this will produce a new commit hash
    model_hyperparameters.change_to_new_hyperparameters()

    # Run second training flow, with changed source code/model architecture
    training_args["output_dir"] = './data_flow2',
    #executor.run_flow("training_flow", **training_args)



    print(f"\n\n\n-=-----------------------=-\n")

    # Run artifacts are stored with the prefect server
    # I cannot return the flow_run_ids, so my best idea was to write and read them from
    #  an external text file. However, they could be easily viewed in the Prefect Server
    #  and input manually into an API etc. whenever necessary.
    with open("Flow_Ids.txt", "r", encoding="utf-8") as f:
        all_flow_run_ids = f.read().splitlines()

    # Print the complete run artifact from the first model training flow
    first_model_flow_run_id = all_flow_run_ids[-2]
    artifact = executor.get_artifact("training_flow", first_model_flow_run_id)
    print(artifact)



    print(f"\n\n\n-=-----------------------=-\n")

    # If we know the flow id of a particular code, we can completely reproduce that flow,
    #  including running it with the exact same source code and input arguments as before.
    #  We pull that commit from the flow repository and the arguments from the artifact.
    #  The input dataset is assumed to be static here, but could also be versioned.
    #executor.reproduce_flow("training_flow", all_flow_run_ids[0])




    print(f"\n\n\n-=-----------------------=-\n")

    monitoring_args = {
        "working_dir": artifact["kwargs"]["output_dir"],
        "dataset_name": artifact["kwargs"]["outfile_name"],
        "model_name": artifact["kwargs"]["model_name"],
        "model_path": artifact["model_path_full"],
        "cutoff_year": artifact["kwargs"]["cutoff_year"],
        "report_name": "datadrift_results.html",
    }

    # If we know the flow id of a particular code, we can completely reproduce that flow,
    #  including running it with the exact same source code and input arguments as before.
    #  We pull that commit from the flow repository and the arguments from the artifact.
    #  The input dataset is assumed to be static here, but could also be versioned.
    executor.run_flow("monitoring_flow", **monitoring_args)


    """
    client = MlflowClient()
    client.set_registered_model_alias(
        "RandomForestMulticlassifier",
        "Backup",
        model_info.registered_model_version
    )


    model_info, metrics = myflow_runner(
        output_dir = Path('../../data_flow2'),
        outfile_name = "steam_games_dataset.csv",
        report_name = "report.html",
        model_name = "RandomForestMulticlassifier",
        cutoff_year = 2010
    )

    accuracy, balanced_accuracy, f1 = metrics
    print(accuracy, balanced_accuracy, f1)
    print(model_info)

    "fizzbuzz_flow_docker", arg1="fizz", arg2="buzz")
    """