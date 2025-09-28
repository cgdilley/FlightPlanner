
from FlightCollector import *
from Planner import *
from ruamel.yaml import YAML

yaml = YAML(typ="safe")
yaml.allow_unicode = True
yaml.default_flow_style = False
yaml.indent(mapping=2, sequence=2, offset=4)

F1 = "../data/results_2025-09-27.yaml"
F2 = "../data/results_2025-09-27_copy.yaml"
OUT = "../data/results_2025-09-27_combined.yaml"

def main():
    with open(F1, "r", encoding="utf-8") as f:
        f1 = [PlanResult.from_json(group) for group in yaml.load(f)["results"]]

    with open(F2, "r", encoding="utf-8") as f:
        f2 = [PlanResult.from_json(group) for group in yaml.load(f)["results"]]

    combined: list[PlanResult] = []
    for pr1, pr2 in zip(f1, f2):
        klm = [r for r in pr2.results if r.provider == KLMSearchCollector]
        google = pr1.results
        revised = klm + google
        combined.append(PlanResult(name=pr1.name, results=revised))

    with open(OUT, "w", encoding="utf-8") as f:
        yaml.dump({"results": [pr.to_json() for pr in combined]}, f)



#


#


if __name__ == '__main__':
    main()