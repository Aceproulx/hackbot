/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	// The require scope
/******/ 	var __webpack_require__ = {};
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/make namespace object */
/******/ 	(() => {
/******/ 		// define __esModule on exports
/******/ 		__webpack_require__.r = (exports) => {
/******/ 			if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/ 				Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 			}
/******/ 			Object.defineProperty(exports, '__esModule', { value: true });
/******/ 		};
/******/ 	})();
/******/ 	
/************************************************************************/
var __webpack_exports__ = {};
/*!******************************!*\
  !*** ./src/scripts/reset.js ***!
  \******************************/
__webpack_require__.r(__webpack_exports__);
(function () {
  const reset = function (challengeUrl) {
    for (const [id, client] of Object.entries(___grecaptcha_cfg.clients)) {
      for (const [_, items] of Object.entries(client)) {
        if (items instanceof Object) {
          for (const [_, v] of Object.entries(items)) {
            if (v instanceof Element && v.src === challengeUrl) {
              (grecaptcha.reset || grecaptcha.enterprise.reset)(id);
              return;
            }
          }
        }
      }
    }
  };
  const onMessage = function (ev) {
    ev.stopImmediatePropagation();
    removeCallbacks();
    reset(ev.detail);
  };
  const removeCallbacks = function () {
    window.clearTimeout(timeoutId);
    document.removeEventListener('___resetCaptcha', onMessage, {
      capture: true,
      once: true
    });
  };
  const timeoutId = window.setTimeout(removeCallbacks, 10000); // 10 seconds

  document.addEventListener('___resetCaptcha', onMessage, {
    capture: true,
    once: true
  });
})();
/******/ })()
;