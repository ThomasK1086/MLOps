# MLOps Exercise 3

Author: Thomas Klar, 12021340

## Setup

- Make sure Docker is installed and running.
- Run using
```bash
docker-compose up --build -d
```
- Inspect scipt outputs/logs with 
```bash
docker logs mlopsex3-python-app-1 -f
```
The container might possibly be named differently on your machine. Since services are running in the background, the complete logs might take a while (~5min) to appear. Once the scipt finishes executing, a "Finished" message appears in the logs.
- While the services are running, you should be able to inspect the running servers at [Prefect](http://0.0.0.0:4200) and [MLFlow](http://0.0.0.0:8080) in your browser. If those links do not work, you can instead try to access [Prefect](http://localhost:4200) and [MLFlow](http://localhost:8080).
- To shutdown this project once you are finished, simply run
```bash
docker-compose down
```

## Note
If your Docker DNS setup fails and containers cannot connect to each other or the internet, good luck! I have no idea how to fix that.

## Project Structure
The main entry point is the file `main.py`. It runs everything except the prefect and mlflow servers.
I have split up various parts of the code into several `utils-XY.py` files, for clarity and modularity.
- `utils_flowexecutor.py` is probably the most interesting. It contains the class FlowExecutor that actually executes a flow, including versioning, logging, and the setup of a docker (Sub-)container.
- `utils_autocommit.py` contains a class AutoCommiter that can push and pull flow source code to and from a remote git repository. This also includes a credential manager to generate access tokens.
- `utils_docker.py` contains various functions that are needed for docker container management, and
- `utils.py` provides various other functionalities.

For a visualization of how the flow versioning works conceptually, see the diagram in `FlowVersioningSetup.png`. In short, all flow source code and dependancies are in `flows_git/`, which is a separate Git repository. Each flow has its own subfolder inside that folder. This folder includes everything needed to run this particular flow, including but not limited to a main `flow.py` file, separate `taskXY.py` files containing steps, and a `Dockerfile` to build a (Sub-)Container that the flow is executed in. 

Each time a flow is run, this entire subfolder is commited to the git flow repository and the commit hash is archived. This enables tracking and reproducability. Tracking of actual runs/executions is done via Prefect and extended with Artifacts. Those are visible in the (local) prefect server and additionally logged in `Flow_Artifacts_Local.txt`. They can be accessed via Flow Run Ids, which can either be taken from the prefect server or locally from `Flow_Ids.txt`.

## Flow Descriptions

### Training flow
This flow, in the directory `flows_git/training_flow/`, consists of three steps
1. The first step loads the input data and performs several data tests on it (this is exercise 1). A report is generated in `data_flow1/report.html`, and some data preprocessing happens 
2. A Random Forest Classifier is trained on the data.
3. Validation tests are performed on the trained model to infer its quality. A report is generated in `data_flow1/classifier_results.html`

### Monitoring flow
Defined in `flows_git/monitoring_flow/`. It performs a drift test on previously unseen data with the trained model form the previous flow. The data is split according to dates, with 2020 being the cutoff year and everything newer being unseen data not used for model training. A test report is generated in `data_flow1/datadrift_report.html`

### A/B Test flow
This flow performs an A/B test. It compares the model to another model trained with different hyperparameters. Both models are tested on the same previously unseen data that was already used in the monitoring flow. This data is split randomly into a test group, control group and some data points are excluded. The splitting is done via hashing of the release date, which is assumed to be an immutable attribute. Thus, the test is random but reproducable. The performance is measured by comparing accuracy, and one of the models would be preferred if it achieved a significantly higher accuracy than the other.

## Documentation
See docstrings and comments in main.py for details.