/******/ (() => { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({

/***/ 580:
/***/ ((module) => {

module.exports = eval("require")("@actions/cache");


/***/ }),

/***/ 406:
/***/ ((module) => {

module.exports = eval("require")("@actions/core");


/***/ }),

/***/ 293:
/***/ ((module) => {

"use strict";
module.exports = require("buffer");;

/***/ }),

/***/ 129:
/***/ ((module) => {

"use strict";
module.exports = require("child_process");;

/***/ }),

/***/ 747:
/***/ ((module) => {

"use strict";
module.exports = require("fs");;

/***/ }),

/***/ 622:
/***/ ((module) => {

"use strict";
module.exports = require("path");;

/***/ }),

/***/ 58:
/***/ ((module) => {

"use strict";
module.exports = require("readline");;

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __nccwpck_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		var threw = true;
/******/ 		try {
/******/ 			__webpack_modules__[moduleId](module, module.exports, __nccwpck_require__);
/******/ 			threw = false;
/******/ 		} finally {
/******/ 			if(threw) delete __webpack_module_cache__[moduleId];
/******/ 		}
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/compat */
/******/ 	
/******/ 	if (typeof __nccwpck_require__ !== 'undefined') __nccwpck_require__.ab = __dirname + "/";/************************************************************************/
var __webpack_exports__ = {};
// This entry need to be wrapped in an IIFE because it need to be isolated against other modules in the chunk.
(() => {
// Copyright 2014-2021 Scalyr Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

const core = __nccwpck_require__(406);
const cache = __nccwpck_require__(580);
const fs = __nccwpck_require__(747);
const path = __nccwpck_require__(622);
const child_process = __nccwpck_require__(129);
const buffer = __nccwpck_require__(293);
const readline = __nccwpck_require__(58);


async function checkAndGetCache(
    name,
    cacheDir,
    cacheVersionSuffix
) {
    //
    // Check if there is an existing cache for the given step name.
    //
    const cachePath = path.join(cacheDir, name);
    const key = `${name}-${cacheVersionSuffix}`;

    // try to restore the cache.
    const result = await cache.restoreCache([cachePath], key);

    if (typeof result !== "undefined") {
        console.log(`Cache for the step with key ${key} is found.`);
    } else {
        console.log(`Cache for the step with key ${key} is not found.`);
    }

    // Return whether it is a hit or not.
    return result;
}

async function checkAndSaveCache(
    name,
    cacheDir,
    isHit,
    cacheVersionSuffix
) {
    //
    // Save the cache directory for a particular step if it hasn't been saved yet.
    //

    const fullPath = path.join(cacheDir, name);
    const cacheKey = `${name}-${cacheVersionSuffix}`;

    // Skip files. Step cache can be only the directory.
    if (!fs.lstatSync(fullPath).isDirectory()) {
        return;
    }

    // If there's no cache hit, then save directory to the cache now.
    if (isHit) {
        console.log(`Cache for the step with key ${cacheKey} has been hit. Skip saving.`);
    }
    else {
        console.log(`Save cache for the step with key ${cacheKey}.`);

        try {
            await cache.saveCache([fullPath], cacheKey);
        } catch (error) {
            console.warn(
                `Can not save step cache by key ${cacheKey}. 
                It seems that seems that it has been saved somewhere else.\nOriginal message: ${error}`
            );
        }
    }

    // When completed, step can leave a special file 'paths.txt'.
    // This file contains paths of the tools that are needed to be added to the system's PATH.
    const pathsFilePath = path.join(fullPath, "paths.txt");
    if (fs.existsSync(pathsFilePath)) {

        const lineReader = readline.createInterface({
            input: fs.createReadStream(pathsFilePath)
        });

        lineReader.on('line', function (line) {
            console.log(`Add path ${line}.`);
            core.addPath(line);
        });
    }
}

async function executeRunner() {
    // The main action function. It does the following:
    // 1. Get all ids of the steps of the given runner and then try to load their caches by using that ids.
    // 2. Execute the runner. If there are cache hits that have been done previously, reuse them.
    // 3. If there are steps, which results haven't been found during the step 1, then the results of those
    //    steps will be cached using their ids.

    const stepsRunnerName = core.getInput("runner-name");
    const cacheVersionSuffix = core.getInput("cache-version-suffix");
    const cacheDir = core.getInput("cache-dir");

    if (!fs.existsSync(cacheDir)) {
        fs.mkdirSync(cacheDir,{recursive: true});
    }

    // Get json list with names of all steps which are needed for this runner.
    const executeStepsRunnerScriptPath = path.join(".github", "actions", "helper.py");
    // Run special github-related helper command which returns names for ids of all steps, which are used in the current
    // runner.
    const output = child_process.execFileSync(
        "python3",
        [executeStepsRunnerScriptPath, stepsRunnerName, "get-steps-ids"]
    );

    // Read and decode names from json.
    const json_encoded_step_ids = buffer.Buffer.from(output, 'utf8').toString();
    const steps_ids = JSON.parse(json_encoded_step_ids);

    const cacheHits = {};

    // Run through steps ids and look if the is any existing cache for them.
    for (let name of steps_ids) {
        cacheHits[name] = await checkAndGetCache(
            name,
            cacheDir,
            cacheVersionSuffix
        );
    }

    // Run the step. Also provide cache directory, if there are some found caches, then the step
    // has to reuse them.
    child_process.execFileSync(
        "python3",
        [executeStepsRunnerScriptPath, stepsRunnerName, "execute"],
        {stdio: 'inherit'}
    );

    // Run through the cache folder and save any cached directory within, that is not yet cached.
    const filenames = fs.readdirSync(cacheDir);
    for (const name of filenames) {
        await checkAndSaveCache(
            name,
            cacheDir,
            cacheHits[name],
            cacheVersionSuffix,
        );
    }
}


async function run() {
    // Entry function. Just catch any error and pass it to GH Actions.
  try {
      await executeRunner();
  } catch (error) {
    core.setFailed(error.message);
  }
}

run()


})();

module.exports = __webpack_exports__;
/******/ })()
;