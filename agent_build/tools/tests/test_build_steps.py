# Copyright 2014-2021 Scalyr Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import collections
import dataclasses
import shutil
import subprocess
import pathlib as pl
import tempfile
import textwrap
from typing import List, Optional, Union

import mock
import pytest

from agent_build.tools import constants
from agent_build.tools import common
from agent_build.tools import build_step
from agent_build.tools.build_step import DockerImageSpec

common.init_logging()

_PARENT_DIR = pl.Path(__file__).parent
_BUILD_STEPS_DIR = _PARENT_DIR / "fixtures/build_step_scripts"


def _get_docker_image_spec_or_none(
        docker_image: str = None
):
    if not docker_image:
        return None

    return DockerImageSpec(
        name=docker_image,
        architecture=constants.Architecture.X86_64
    )


_BASE_STEP_SCRIPTS={
    "shell": _BUILD_STEPS_DIR / "base_step.sh",
    "python": _BUILD_STEPS_DIR / "base_step.py"
}

_FINAL_STEP_SCRIPTS={
    "shell": _BUILD_STEPS_DIR / "final_step.sh",
    "python": _BUILD_STEPS_DIR / "final_step.py"
}

_DEPENDENCY_STEP_SCRIPTS={
    "shell": _BUILD_STEPS_DIR / "dependency_step.sh",
    "python": _BUILD_STEPS_DIR / "dependency_step.py"
}

_DOCKER_IMAGES_TO_SCRIPT_TYPES = {
    "shell": "debian:bullseye",
    "python": "python:3.8-bullseye"
}
@pytest.mark.parametrize(
    ["dependency_script_type", "dependency_in_docker"],
    [
        ("shell", True),
        ("shell", False),
        ("python", True),
        ("python", False)
    ]
)
@pytest.mark.parametrize(
    ["in_docker"], [(False,), (True,)]
)
@pytest.mark.parametrize(
    ["script_type"], [("shell",), ("python",)]
)
def test_base_step(
        script_type,
        in_docker,
        dependency_script_type,
        dependency_in_docker,
        tmp_path
):
    # Set path to a file that has to be created during the run of the base step.
    if in_docker:
        base_step_result_file_path = pl.Path("/tmp/base.txt")
        docker_image = _get_docker_image_spec_or_none(
            _DOCKER_IMAGES_TO_SCRIPT_TYPES[script_type]
        )
    else:
        base_step_result_file_path = tmp_path / "base.txt"
        docker_image = None

    build_root = pl.Path("/Users/arthur/work/agents/scalyr-agent-2/build_test")
    #build_root = tmp_path / "build_root"

    class TestBaseStep(build_step.ScriptBuildStep):
        CACHEABLE = True

    base_step = TestBaseStep(
        name="BaseTestStep",
        script_path=_BASE_STEP_SCRIPTS[script_type],
        is_dependency_step=False,
        base_step=docker_image,
        additional_settings={
            "INPUT": "BASE",
            "BASE_RESULT_FILE_PATH": str(base_step_result_file_path)
        },
    )

    # Check ids of all steps that are used by base step.
    # That has to be only the id of the base step itself.
    assert base_step.all_used_cacheable_steps_ids == [base_step.id]

    if dependency_in_docker:
        dependency_docker_image = _get_docker_image_spec_or_none(
            _DOCKER_IMAGES_TO_SCRIPT_TYPES[dependency_script_type]
        )
    else:
        dependency_docker_image = None

    class TestDependencyStep(build_step.ScriptBuildStep):
        CACHEABLE = True

    # Create a dependency step. It has to produce a file that has to be used in the final step.
    dependency_step = TestDependencyStep(
        name="DependencyStep",
        script_path=_DEPENDENCY_STEP_SCRIPTS[dependency_script_type],
        is_dependency_step=True,
        base_step=dependency_docker_image,
        additional_settings={
            "INPUT": "DEPENDENCY",
        }
    )
    # Check all used ids for the dependency step.
    # It does not have any previous steps, so it contain only its own id.
    assert dependency_step.all_used_cacheable_steps_ids == [dependency_step.id]

    class FinalStep(build_step.ScriptBuildStep):
        CACHEABLE = True

    final_step = FinalStep(
        name="FinalStep",
        script_path=_FINAL_STEP_SCRIPTS[script_type],
        base_step=base_step,
        is_dependency_step=True,
        dependency_steps=[dependency_step],
        additional_settings={
            "INPUT": "FINAL",
            "BASE_RESULT_FILE_PATH": str(base_step_result_file_path)
        }
    )

    # Check all ids. For now, the result also has to contain ids of all previous steps.
    assert final_step.all_used_cacheable_steps_ids == [
        *dependency_step.all_used_cacheable_steps_ids,
        *base_step.all_used_cacheable_steps_ids,
        final_step.id
    ]

    final_step.run(
        build_root=build_root
    )

    if in_docker:
        # If base step run in docker we check its result file within the result image.
        result_file_content = subprocess.check_output([
            "docker",
            "run", "-i", "--rm",
            base_step.result_image.name,
            "cat",
            str(base_step_result_file_path)
        ]).decode()
    else:
        assert base_step_result_file_path.exists()
        result_file_content = base_step_result_file_path.read_text()

    base_step_expected_result = f"BASE_{script_type}"
    if in_docker:
        base_step_expected_result = f"{base_step_expected_result}_in_docker"
    assert result_file_content.strip() == base_step_expected_result

    # Check dependency step result
    dependency_step_result_file = dependency_step.output_directory / "result.txt"
    assert dependency_step_result_file.exists()
    assert dependency_step_result_file.read_text().strip() == f"DEPENDENCY_{dependency_script_type}"

    # Check final step's result file. It has to contain also text from the base step.
    final_step_result_file = final_step.output_directory / "result.txt"
    assert final_step_result_file.exists()
    assert final_step_result_file.read_text().strip() == textwrap.dedent(
        f"""
        {base_step_expected_result}
        DEPENDENCY_{dependency_script_type}
        FINAL_{script_type}
        """
    ).strip()


def test_steps_id_consistency(tmp_path):
    """
    Test that essential input step information such as additional_settings,
    docker_image and used_files will be reflected in an id of a step,
    and the same step with the same inputs always produces the same id.
    """
    # Create temporary file and write there one of the scripts.
    script_path = _BUILD_STEPS_DIR / "base_step.sh"
    modifiable_script_path = tmp_path / "base_step.sh"
    modifiable_script_path.write_text(
        script_path.read_text()
    )
    base_step = build_step.PrepareEnvironmentStep(
        script_path=_BUILD_STEPS_DIR / "base_step.sh",
        build_root=tmp_path,
        base_step=None,
        additional_settings={
            "NAME": "VALUE"
        }
    )

    same_step = build_step.PrepareEnvironmentStep(
            script_path=_BUILD_STEPS_DIR / "base_step.sh",
            build_root=tmp_path,
            base_step=None,
            additional_settings={
                "NAME": "VALUE"
            }
        )

    assert base_step.id == same_step.id

    # Change additional settings
    changed_base = build_step.PrepareEnvironmentStep(
            script_path=_BUILD_STEPS_DIR / "base_step.sh",
            build_root=tmp_path,
            base_step=None,
            additional_settings={
                "NAME": "VALUE1",
            }
        )

    assert base_step.id != changed_base.id

    # Change script file. The id also has to change.
    changed_script_step = build_step.PrepareEnvironmentStep(
            script_path=_BUILD_STEPS_DIR / "base_step.py",
            build_root=tmp_path,
            base_step=None,
            additional_settings={
                "NAME": "VALUE",
            }
        )

    assert base_step.id != changed_script_step.id

    # Add docker image.
    step_with_docker_image = build_step.PrepareEnvironmentStep(
            script_path=_BUILD_STEPS_DIR / "base_step.sh",
            build_root=tmp_path,
            base_step=_get_docker_image_spec_or_none("ubuntu"),
            additional_settings={
                "NAME": "VALUE",
            }
        )

    assert base_step.id != step_with_docker_image.id
