# Copyright 2014-2022 Scalyr Inc.
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

# Install rust and cargo. It is needed to build some of the Python dependencies of the agent.
# NOTE: We don't use "-" at the end since context names which end just with "-" don't appear to
# be valid anymore with new Docker / buildx versions. See https://github.com/scalyr/scalyr-agent-2/pull/845
# for details

set -e

if [ "$TARGETVARIANT" != "v7" ]; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  PATH="/root/.cargo/bin:${PATH}"
  rustup toolchain install nightly
  rustup default nightly
fi