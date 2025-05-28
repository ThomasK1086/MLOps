# MLOps Exercise 2

Author: Thomas Klar, 12021340

## Setup

- Make sure Docker is installed and running.
- Run using
```bash
docker-compose up --build -d
```bash
- Inspect scipt outputs/logs with (container might possibly be named differently on your machine)
```bash
docker logs exercise3-python-app-1 -f
```
(container might possibly be named differently on your machine). Since services are running in the background, the complete logs might take a while (~5min) to appear. Once the scipt finishes executing, an "All done" message appears in the logs.
- While the services are running, you should be able to inspect the running servers at [Prefect](http://0.0.0.0:4200) and [MLFlow](http://0.0.0.0:8080) in your browser. If those links do not work, you can instead try to access [Prefect](http://localhost:4200) and [MLFlow](http://localhost:8080).
- To shutdown this project once you are finished, simply run
```bash
docker-compose down
```

## Note
If your Docker DNS setup fails and containers cannot connect to each other or the internet, good luck! I have no idea how to fix that.

## Documentation
See docstrings in main.py for details.