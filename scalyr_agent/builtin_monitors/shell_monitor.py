# Copyright 2014 Scalyr Inc.
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
# ------------------------------------------------------------------------
#
# A ScalyrMonitor which executes a specified shell command and records the output.

from __future__ import absolute_import

import re
import sys
import time

from subprocess import PIPE, Popen

import six

from scalyr_agent import ScalyrMonitor, define_config_option, define_log_field

__monitor__ = __name__

define_config_option(
    __monitor__, "module", "Always ``scalyr_agent.builtin_monitors.shell_monitor``"
)
define_config_option(
    __monitor__,
    "id",
    "Included in each log message generated by this monitor, as a field named ``instance``. Allows "
    "you to distinguish between values recorded by different monitors.",
)
define_config_option(
    __monitor__, "command", "The shell command to execute.", required_option=True
)
define_config_option(
    __monitor__,
    "extract",
    "Optional: a regular expression to apply to the command output. If defined, this expression must "
    "contain a matching group (i.e. a subexpression enclosed in parentheses). The monitor will record "
    "only the content of that matching group. This allows you to discard unnecessary portions of the "
    "command output and extract the information you need.",
    default="",
)
define_config_option(
    __monitor__,
    "log_all_lines",
    "Optional (defaults to false). If true, the monitor will record the entire command output; "
    "otherwise, it only records the first line.",
    default=False,
)
define_config_option(
    __monitor__,
    "max_characters",
    "Optional (defaults to 200). At most this many characters of output are recorded. You may specify "
    "a value up to 10000, but the Scalyr server currently truncates all fields to 3500 characters.",
    default=200,
    convert_to=int,
    min_value=0,
    max_value=10000,
)

define_log_field(__monitor__, "monitor", "Always ``shell_monitor``.")
define_log_field(
    __monitor__,
    "instance",
    "The ``id`` value from the monitor configuration, e.g. ``kernel-version``.",
)
define_log_field(
    __monitor__,
    "command",
    "The shell command for this plugin instance, e.g. ``uname -r``.",
)
define_log_field(__monitor__, "metric", "Always ``output``.")
define_log_field(
    __monitor__,
    "value",
    "The output of the shell command, e.g. ``3.4.73-64.112.amzn1.x86_64``.",
)


# Pattern that matches the first line of a string
__first_line_pattern__ = re.compile("[^\r\n]+")


# ShellMonitor implementation
class ShellMonitor(ScalyrMonitor):
    # fmt: off
    """
# Shell Monitor

This agent monitor plugin periodically executes a specified shell command, and records the output.
It can be used to monitor any information that can be retrieved via a shell command. Shell commands
are run from the Scalyr Agent, and execute as the same user as the agent.

@class=bg-warning docInfoPanel: An *agent monitor plugin* is a component of the Scalyr Agent. To use a plugin,
simply add it to the ``monitors`` section of the Scalyr Agent configuration file (``/etc/scalyr/agent.json``).
For more information, see [Agent Plugins](/help/scalyr-agent#plugins).

## Sample Configuration

Here is a simple configuration fragment showing use of the shell_monitor plugin. This sample will record
the version of the Linux kernel in use on the machine where the agent is running.

    monitors: [
      {
        module:  "scalyr_agent.builtin_monitors.shell_monitor",
        id:      "kernel-version",
        command: "uname -r"
      }
    ]

To record output from more than one command, use several copies of the shell_monitor plugin in your configuration.

## Viewing Data

After adding this plugin to the agent configuration file, wait one minute for data to begin recording. Then go to
the Search page and search for [$monitor = 'shell_monitor'](/events?filter=$monitor%20%3D%20%27shell_monitor%27).
This will show all data collected by this plugin, across all servers. You can use the {{menuRef:Refine search by}}
dropdown to narrow your search to specific servers and monitors.

The [View Logs](/help/view) page describes the tools you can use to view and analyze log data.
[Query Language](/help/query-language) lists the operators you can use to select specific metrics and values.
You can also use this data in [Dashboards](/help/dashboards) and [Alerts](/help/alerts).
    """
    # fmt: on

    def _initialize(self):
        # Fetch and validate our configuration options.
        self.command = self._config.get("command")
        self.max_characters = self._config.get("max_characters")
        self.log_all_lines = self._config.get("log_all_lines")

        extract_expression = self._config.get("extract")
        if extract_expression:
            self.extractor = re.compile(extract_expression)

            # Verify that the extract expression contains a matching group, i.e. a parenthesized clause.
            # We perform a quick-and-dirty test here, which will work for most regular expressions.
            # If we miss a bad expression, it will result in a stack trace being logged when the monitor
            # executes.
            if extract_expression.find("(") < 0:
                raise Exception(
                    "extract expression [%s] must contain a matching group"
                    % extract_expression
                )
        else:
            self.extractor = None

    def gather_sample(self):

        close_fds = True
        if sys.platform == "win32":
            # on windows we can't both redirect stdin, stdout and stderr AND close_fds
            # therefore we don't close fds for windows.
            close_fds = False

        # Run the command
        # NOTE: We intentionally use shell=True to allow users to define commands which are executed
        # under a shell.
        # There is no possibility for 3rd part a shell injection here since the command is
        # controlled by the end user.
        start_ts = int(time.time())

        command = self.command
        p = Popen(  # nosec
            command,
            shell=True,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            close_fds=close_fds,
        )
        (stdout_text, stderr_text) = p.communicate()
        end_ts = int(time.time())
        duration = end_ts - start_ts

        output = stderr_text
        if len(stderr_text) > 0 and len(stdout_text) > 0:
            output += b"\n"
        output += stdout_text

        output = six.ensure_text(output)

        # Apply any extraction pattern
        if self.extractor is not None:
            match = self.extractor.search(output)
            if match is not None:
                output = match.group(1)

        # Apply log_all_lines and max_characters, and record the result.
        if self.log_all_lines:
            s = output
        else:
            first_line = __first_line_pattern__.search(output)
            s = ""
            if first_line is not None:
                s = first_line.group().strip()

        if len(s) > self.max_characters:
            s = s[: self.max_characters] + "..."

        exit_code = p.returncode
        self._logger.emit_value(
            "output",
            s,
            extra_fields={
                "command": self.command,
                "length": len(output),
                "duration": duration,
                "exit_code": exit_code,
            },
        )
