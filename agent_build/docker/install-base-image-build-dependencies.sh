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



set -e

if [ "$PYTHON_BASE_IMAGE_TYPE" = "debian" ]; then
  apt-get update && apt-get install -y build-essential
else
  apk update && apk add --virtual build-dependencies \
    binutils \
    build-base \
    gcc \
    g++ \
    make \
    python3-dev \
    patchelf
fi