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
  # Workaround for weird build failure on Circle CI, see
  # https://github.com/docker/buildx/issues/495#issuecomment-995503425 for details
  ln -s /usr/bin/dpkg-split /usr/sbin/dpkg-split
  ln -s /usr/bin/dpkg-deb /usr/sbin/dpkg-deb
  ln -s /bin/rm /usr/sbin/rm
  ln -s /bin/tar /usr/sbin/tar

  apt-get update && apt-get install -y git tar curl
else
  apk update && apk add --virtual common curl git
fi

