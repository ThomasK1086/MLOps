import os
from dotenv import load_dotenv
from pathlib import Path


from autocommit import AutoCommitter, GitCredentials
from flowexecutor import FlowExecutor, Hyperparameters, pprint_dict
import hashlib


if __name__ == '__main__':
    load_dotenv()
    prefect_url = os.getenv("PREFECT_API_URL")
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    print(f"Env variables are {prefect_url=}, {mlflow_uri=}")

    # This is needed to pull/push to the remote repository that versions the flow source code
    creds = GitCredentials(
        app_id=os.getenv("APP_ID"),
        private_key_path=os.getenv("PRIVATE_KEY_PATH"),
        installation_id=os.getenv("INSTALLATION_ID"),
    )
    # Init flow repository
    gitcommitter = AutoCommitter(
        repo_path='./flows_git',
        credentials=creds,
        subfolder="training_flow"
    )
    gitcommitter.pull()
    
    hp_path = Path("./flows_git/training_flow/model_hyperparameters.txt")
    model_hyperparameters = Hyperparameters(hp_path)



    # This is the wrapper class that runs and versions flows
    executor = FlowExecutor(credentials=creds, verbose=True)



    print(f"\n\n\n--<==[  Model Training Flow  ]==>--\n")

    training_args = {
        "output_dir": './data_flow1/',
        "outfile_name": "steam_games_dataset.csv",
        "report_name": "report.html",
        "model_name": "RandomForestMulticlassifier",
        "cutoff_year": 2020
    }



    # Run first training flow (this is exercise 2 basically)
    executor.run_flow("training_flow", **training_args)




    print(f"\n\n\n--<==[  Second Model Training Flow, new hyperparameters  ]==>--\n")
    # At this point, we simulate change the model architecture directly in the code.
    # This is not an input parameter and thus can only be tracked via the source code
    # Note that this will produce a new commit hash
    model_hyperparameters.change_to_new_hyperparameters()

    # Run second training flow, with changed source code/model architecture
    #  Note that input parameters dont change, only the output directory
    training_args["output_dir"] = './data_flow2/'
    executor.run_flow("training_flow", **training_args)



    print(f"\n\n\n--<==[  Inspection of run artifacts  ]==>--\n")

    # Run artifacts are stored in the prefect server
    # I cannot return the flow_run_ids, so my best idea was to write and read them from
    #  an external text file. However, they could be easily viewed in the Prefect Server
    #  and input manually into an API etc. whenever necessary.
    with open("Flow_Ids.txt", "r", encoding="utf-8") as f:
        all_flow_run_ids = f.read().splitlines()

    # Print the complete run artifact from the first model training flow
    first_model_flow_run_id = all_flow_run_ids[-2]
    artifact_first = executor.get_artifact(first_model_flow_run_id)
    pprint_dict(artifact_first)

    # Get artifact from second training flow
    second_model_flow_run_id = all_flow_run_ids[-1]
    #artifact_second = executor.get_artifact(second_model_flow_run_id)





    #print(f"\n\n\n--<==[  Rerun first training flow (optional)  ]==>--\n")

    # If we know the flow id of a particular code, we can completely reproduce that flow,
    #  including running it with the exact same source code and input arguments as before.
    #  We pull that commit from the flow repository and the arguments from the artifact.
    #  The input dataset is assumed to be static here, but could also be versioned.
    #executor.reproduce_flow("training_flow", all_flow_run_ids[0])




    print(f"\n\n\n--<==[  Monitoring Flow  ]==>--\n")

    monitoring_args = {
        "working_dir": artifact_first["kwargs"]["output_dir"],
        "dataset_name": artifact_first["kwargs"]["outfile_name"],
        "model_name": artifact_first["kwargs"]["model_name"],
        "model_path": artifact_first["model_path_full"],
        "cutoff_year": artifact_first["kwargs"]["cutoff_year"],
        "report_name": "datadrift_results.html",
    }

    # If we know the flow id of a particular code, we can completely reproduce that flow,
    #  including running it with the exact same source code and input arguments as before.
    #  We pull that commit from the flow repository and the arguments from the artifact.
    #  The input dataset is assumed to be static here, but could also be versioned.
    executor.run_flow("monitoring_flow", **monitoring_args)




    print(f"\n\n\n--<==[  AB Test  ]==>--\n")

    # Create a function to hash inputs in a deterministic, reproducible way
    # This hash function could be reused for multiple A/B tests
    # It is serialized and passed to the A/B test flow/container
    def input_to_hash(datetime, seed=42):
        """
        Generates a hash from datetime and a seed, then returns float between 0 and 1.
        """
        data_str = f"{seed}_{datetime}"
        hash_obj = hashlib.sha256(data_str.encode('utf-8'))
        hash_int = int(hash_obj.hexdigest(), 16)
        return hash_int % 1000 / 1000.0

    # Create a function that assigns hashes to groups in an entirely custom way.
    #  Different experiments would use different assignments, and a None Class
    #  can also be defined to exclude a part of the input data.
    # Here we try to split evenly into AB, excluding 20% of unseen input data
    def hash_to_class(hash, seed=42):
        """
        Assign hash values between 0 and 1 to classes.
        :param h:
        :return: Element of [-1, 0, 1], representing classes [A, None, B].
          The None class can also be excluded entirely
        """
        if hash < 0.4:
            return -1
        elif hash < 0.8:
            return 1
        else:
            return 0

    # Functions need to be serialized
    hash_function_string = executor.serialize_function(input_to_hash)
    split_function_string = executor.serialize_function(hash_to_class)

    ab_test_args = {
        "working_dir": artifact_first["kwargs"]["output_dir"],
        "dataset_name": artifact_first["kwargs"]["outfile_name"],
        "flow_run_id_A": first_model_flow_run_id,
        "flow_run_id_B": second_model_flow_run_id,
        "hash_function_string": hash_function_string,
        "split_function_string":  split_function_string,
        "seed": 12021340,
        "cutoff_year": artifact_first["kwargs"]["cutoff_year"],
    }
    executor.run_flow("abtest_flow", **ab_test_args)




    print(f"\n\n\n--<==[  Inspection of A/B test artifact  ]==>--\n")

    # Get results from artifact
    with open("Flow_Ids.txt", "r", encoding="utf-8") as f:
        all_flow_run_ids = f.read().splitlines()

    abtest_flow_run_id = all_flow_run_ids[-1]
    artifact_abtest = executor.get_artifact(abtest_flow_run_id)
    pprint_dict(artifact_abtest)

    print(f"\n\n--<==[  Finished  ]==>--")
