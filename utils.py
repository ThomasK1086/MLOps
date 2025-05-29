from pathlib import Path
import json


class Hyperparameters():
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.set_default_hyperparameters()

    def set_default_hyperparameters(self):
        if not self.filepath.parent.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
        model_hyperparameters = {
            "max_depth": 10,
            "n_estimators": 30,
            "min_samples_split": 5,
            "min_samples_leaf":2,
            "random_state": 42
        }
        self.model_hyperparameters = model_hyperparameters
        with open(self.filepath, "w+", encoding="utf-8") as f:
            f.write(json.dumps(model_hyperparameters, indent=2))

    def __str__(self):
        return str(self.model_hyperparameters)

    def change_to_new_hyperparameters(self):
        if not self.filepath.parent.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
        model_hyperparameters = {
            "max_depth": 20,
            "n_estimators": 100,
            "min_samples_split": 3,
            "min_samples_leaf": 5,
            "random_state": 42
        }
        self.model_hyperparameters = model_hyperparameters
        with open(self.filepath, "w+", encoding="utf-8") as f:
            f.write(json.dumps(model_hyperparameters, indent=2))


def pprint_dict(input: dict) -> None:
    print("{")
    for key, value in input.items():
        if isinstance(value, dict):
            print(f'  {key} :  \u007b')
            for key2, value2 in value.items():
                if isinstance(value, dict):
                    print(f'    {key} :  \u007b')
                    for key2, value2 in value.items():
                        print(f"      {key2} : {value2}")
                    print(f"    \u007d")
            else:
                print(f"    {key2} : {value2}")
            print(f"  \u007d")
        else:
            print(f"  {key} : {value}")
    print("}")