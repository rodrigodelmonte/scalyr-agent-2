import argparse
import json
import pathlib as pl
import sys
from typing import Type, Dict

_SOURCE_ROOT = pl.Path(__file__).parent.parent.parent.parent
# This file can be executed as script. Add source root to the PYTHONPATH in order to be able to import
# local packages. All such imports also have to be done after that.
sys.path.append(str(_SOURCE_ROOT))

from agent_build.tools.build_step import StepsRunner
from agent_build.package_build_steps import IMAGE_BUILDS
from tests.package_tests.all_package_tests import DOCKER_IMAGE_TESTS

if __name__ == '__main__':

    all_runners: Dict[str, Type[StepsRunner]] = {
        **IMAGE_BUILDS,
        **DOCKER_IMAGE_TESTS
    }

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "name",
        choices=all_runners.keys()
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    get_runner_step_ids_parser = subparsers.add_parser(
        "get-steps-ids"
    )

    execute_runner_parser = subparsers.add_parser(
        "execute"
    )

    execute_runner_parser.add_argument(
        "--build-root-dir",
        dest="build_root_dir",
        required=True
    )

    args = parser.parse_args()

    runner = all_runners[args.name]

    if args.command == "get-steps-ids":
        print(json.dumps(
            runner.all_used_cacheable_steps_ids()
        ))
        exit(0)

    if args.command == "execute":
        for step in runner.all_used_cacheable_steps():
            step.run(
                build_root=pl.Path(args.build_root_dir)
            )