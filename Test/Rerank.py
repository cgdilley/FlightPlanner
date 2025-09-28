from __future__ import annotations
from FlightCollector import *
from Planner import *
from ruamel.yaml import YAML

yaml = YAML(typ="safe")
yaml.allow_unicode = True
yaml.default_flow_style = False
yaml.indent(mapping=2, sequence=2, offset=4)

FILE = "../data/results_2025-09-27_combined.yaml"
OUT = "../data/results_2025-09-27_revised.yaml"
TXT = "../data/results_2025-09-27_revised.txt"
PLAN = "../data/plan.yaml"


def main():
    with open(PLAN, "r", encoding="utf-8") as f:
        plan = SearchPlan.from_json(yaml.load(f))

    with open(FILE, "r", encoding="utf-8") as f:
        results = yaml.load(f)["results"]

    plan_results = [PlanResult.from_json(group) for group in results]
    for i, result in enumerate(plan_results):
        revised = plan.ranker.rank(sqr.query for sqr in result.results)
        plan_results[i].results = revised

    with open(OUT, "w", encoding="utf-8") as f:
        yaml.dump({"results": [pr.to_json() for pr in plan_results]}, f)
    with open(TXT, "w", encoding="utf-8") as f:
        for result in plan_results:
            f.write(f"Results for plan \"{result.name}\":\n---------------------------------\n\n")
            for i, sqr in enumerate(result.results):
                if i > 50:
                    break
                s = str(sqr)
                f.write(s + "\n")
            f.write("\n" + "-"*40 + "\n\n")



#


#


if __name__ == '__main__':
    main()

