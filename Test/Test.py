import os
import io
from FlightCollector import *
from Planner import *
from Data import *
from ruamel.yaml import YAML
from datetime import datetime

yaml = YAML(typ="safe")
yaml.allow_unicode = True
yaml.default_flow_style = False
yaml.indent(mapping=2, sequence=2, offset=4)

DATA_DIR = "../data"
D_FORMAT = "%a %d %b, %Y (%H:%M)"
TODAY = datetime.today()

def main():
    with open(os.path.join(DATA_DIR, "plan.yaml"), "r", encoding="utf-8") as f:
        plan = SearchPlan.from_json(yaml.load(f))

    f_name = f"results_{TODAY.strftime('%Y-%m-%d')}"
    results = list(plan.search())
    with open(os.path.join(DATA_DIR, f"{f_name}.yaml"), "w", encoding="utf-8") as f:
        out = {"results": [r.to_json() for r in results]}
        yaml.dump(out, f)

    with open(os.path.join(DATA_DIR, f"{f_name}.txt"), "w", encoding="utf-8") as f:
        for result in results:
            print(f"Results for plan \"{result.name}\":\n---------------------------------")

            for i, sqr in enumerate(result.results):
                # if i > 100:
                #     break
                s = str(sqr)
                if i < 30:
                    print(s)
                f.write(s + "\n")

            print("\n" + "-"*40 + "\n")



#


#


if __name__ == '__main__':
    main()
