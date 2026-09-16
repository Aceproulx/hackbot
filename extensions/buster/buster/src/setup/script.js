/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=script&lang=js"
/*!*******************************************************************************************************************************************************!*\
  !*** ./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=script&lang=js ***!
  \*******************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var vueton__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vueton */ "./node_modules/vueton/index.js");
/* harmony import */ var utils_app__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! utils/app */ "./src/utils/app.js");
/* harmony import */ var utils_common__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! utils/common */ "./src/utils/common.js");
/* provided dependency */ var browser = __webpack_require__(/*! webextension-polyfill */ "./node_modules/webextension-polyfill/dist/browser-polyfill.js");



/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = ({
  components: {
    [vueton__WEBPACK_IMPORTED_MODULE_0__.App.name]: vueton__WEBPACK_IMPORTED_MODULE_0__.App,
    [vueton__WEBPACK_IMPORTED_MODULE_0__.Button.name]: vueton__WEBPACK_IMPORTED_MODULE_0__.Button,
    [vueton__WEBPACK_IMPORTED_MODULE_0__.TextField.name]: vueton__WEBPACK_IMPORTED_MODULE_0__.TextField
  },
  data: function () {
    const urlParams = new URL(window.location.href).searchParams;
    const apiURL = new URL('http://127.0.0.1/api/v1');
    apiURL.port = urlParams.get('port');
    return {
      dataLoaded: false,
      apiUrl: apiURL.href,
      session: urlParams.get('session'),
      browser: '',
      appDir: '',
      manifestDir: '',
      manifestDirEditable: false,
      isInstalling: false,
      isInstallSuccess: false,
      isInstallError: false
    };
  },
  methods: {
    getText: utils_common__WEBPACK_IMPORTED_MODULE_2__.getText,
    getExtensionId: function () {
      let id = browser.runtime.id;
      if (!this.$env.isFirefox) {
        const scheme = window.location.protocol;
        id = `${scheme}//${id}/`;
      }
      return id;
    },
    setLocation: async function () {
      try {
        await this.location();
      } catch (err) {
        this.isInstallError = true;
        console.log(err.toString());
      }
    },
    runInstall: async function () {
      this.isInstalling = true;
      try {
        await this.install();
      } catch (err) {
        this.isInstallError = true;
        console.log(err.toString());
      } finally {
        this.isInstalling = false;
      }
      if (this.isInstallSuccess) {
        const data = new FormData();
        data.append('session', this.session);
        await fetch(`${this.apiUrl}/setup/close`, {
          method: 'POST',
          body: data
        });
        await browser.runtime.sendMessage({
          id: 'clientAppInstall'
        });
      }
    },
    location: async function () {
      const data = new FormData();
      data.append('session', this.session);
      data.append('browser', this.browser);
      data.append('targetEnv', this.$env.targetEnv);
      const rsp = await fetch(`${this.apiUrl}/setup/location`, {
        method: 'POST',
        body: data
      });
      const results = await rsp.json();
      if (rsp.status === 200) {
        this.appDir = results.appDir;
        this.manifestDir = results.manifestDir;
      } else {
        throw new Error(results.error);
      }
    },
    install: async function () {
      const data = new FormData();
      data.append('session', this.session);
      data.append('appDir', this.appDir);
      data.append('manifestDir', this.manifestDir);
      data.append('browser', this.browser);
      data.append('targetEnv', this.$env.targetEnv);
      data.append('extension', this.getExtensionId());
      const rsp = await fetch(`${this.apiUrl}/setup/install`, {
        method: 'POST',
        body: data
      });
      if (rsp.status === 200) {
        await (0,utils_app__WEBPACK_IMPORTED_MODULE_1__.pingClientApp)();
        this.isInstallSuccess = true;
      } else {
        throw new Error((await rsp.json()).error);
      }
    }
  },
  created: async function () {
    this.browser = (await (0,utils_common__WEBPACK_IMPORTED_MODULE_2__.getBrowser)()).name;
    await this.setLocation();
    if (!this.$env.isWindows) {
      this.manifestDirEditable = true;
    }
    this.dataLoaded = true;
  }
});

/***/ },

/***/ "./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=style&index=0&id=95b38f34&lang=scss"
/*!******************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=style&index=0&id=95b38f34&lang=scss ***!
  \******************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
// extracted by mini-css-extract-plugin


/***/ },

/***/ "./src/setup/App.vue"
/*!***************************!*\
  !*** ./src/setup/App.vue ***!
  \***************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _App_vue_vue_type_template_id_95b38f34__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./App.vue?vue&type=template&id=95b38f34 */ "./src/setup/App.vue?vue&type=template&id=95b38f34");
/* harmony import */ var _App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ./App.vue?vue&type=script&lang=js */ "./src/setup/App.vue?vue&type=script&lang=js");
/* harmony import */ var _App_vue_vue_type_style_index_0_id_95b38f34_lang_scss__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ./App.vue?vue&type=style&index=0&id=95b38f34&lang=scss */ "./src/setup/App.vue?vue&type=style&index=0&id=95b38f34&lang=scss");
/* harmony import */ var _node_modules_vue_loader_dist_exportHelper_js__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ../../node_modules/vue-loader/dist/exportHelper.js */ "./node_modules/vue-loader/dist/exportHelper.js");




;


const __exports__ = /*#__PURE__*/(0,_node_modules_vue_loader_dist_exportHelper_js__WEBPACK_IMPORTED_MODULE_3__["default"])(_App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_1__["default"], [['render',_App_vue_vue_type_template_id_95b38f34__WEBPACK_IMPORTED_MODULE_0__.render],['__file',"src/setup/App.vue"]])
/* hot reload */
if (false) // removed by dead control flow
{}


/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (__exports__);

/***/ },

/***/ "./src/setup/App.vue?vue&type=script&lang=js"
/*!***************************************************!*\
  !*** ./src/setup/App.vue?vue&type=script&lang=js ***!
  \***************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (/* reexport safe */ _node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_0__["default"])
/* harmony export */ });
/* harmony import */ var _node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../node_modules/babel-loader/lib/index.js!../../node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./App.vue?vue&type=script&lang=js */ "./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=script&lang=js");
 

/***/ },

/***/ "./src/setup/App.vue?vue&type=style&index=0&id=95b38f34&lang=scss"
/*!************************************************************************!*\
  !*** ./src/setup/App.vue?vue&type=style&index=0&id=95b38f34&lang=scss ***!
  \************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony import */ var _node_modules_mini_css_extract_plugin_dist_loader_js_node_modules_css_loader_dist_cjs_js_node_modules_vue_loader_dist_stylePostLoader_js_node_modules_postcss_loader_dist_cjs_js_node_modules_sass_loader_dist_cjs_js_clonedRuleSet_2_use_3_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_style_index_0_id_95b38f34_lang_scss__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../node_modules/mini-css-extract-plugin/dist/loader.js!../../node_modules/css-loader/dist/cjs.js!../../node_modules/vue-loader/dist/stylePostLoader.js!../../node_modules/postcss-loader/dist/cjs.js!../../node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!../../node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./App.vue?vue&type=style&index=0&id=95b38f34&lang=scss */ "./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=style&index=0&id=95b38f34&lang=scss");


/***/ },

/***/ "./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=template&id=95b38f34"
/*!************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=template&id=95b38f34 ***!
  \************************************************************************************************************************************************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   render: () => (/* binding */ render)
/* harmony export */ });
/* harmony import */ var vue__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vue */ "./node_modules/vue/dist/vue.runtime.esm-bundler.js");

const _hoisted_1 = {
  key: 0,
  class: "wrap"
};
const _hoisted_2 = {
  class: "title"
};
const _hoisted_3 = {
  class: "desc"
};
const _hoisted_4 = {
  key: 1,
  class: "manifest-desc"
};
const _hoisted_5 = {
  key: 1,
  class: "wrap"
};
const _hoisted_6 = {
  class: "title"
};
const _hoisted_7 = {
  class: "desc"
};
const _hoisted_8 = {
  key: 2,
  class: "wrap"
};
const _hoisted_9 = {
  class: "title error-title"
};
const _hoisted_10 = {
  class: "desc"
};
function render(_ctx, _cache, $props, $setup, $data, $options) {
  const _component_vn_text_field = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-text-field");
  const _component_vn_button = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-button");
  const _component_vn_app = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-app");
  return _ctx.dataLoaded ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createBlock)(_component_vn_app, {
    key: 0
  }, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [!_ctx.isInstallSuccess && !_ctx.isInstallError ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_1, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_2, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_installTitle')), 1 /* TEXT */), _cache[3] || (_cache[3] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_3, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_installDesc')), 1 /* TEXT */), _cache[4] || (_cache[4] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_text_field, {
      label: $options.getText('inputLabel_appLocation'),
      modelValue: _ctx.appDir,
      "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => _ctx.appDir = $event),
      modelModifiers: {
        trim: true
      }
    }, null, 8 /* PROPS */, ["label", "modelValue"]), _cache[5] || (_cache[5] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _ctx.manifestDirEditable ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createBlock)(_component_vn_text_field, {
      key: 0,
      class: "manifest-location",
      label: $options.getText('inputLabel_manifestLocation'),
      modelValue: _ctx.manifestDir,
      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => _ctx.manifestDir = $event),
      modelModifiers: {
        trim: true
      }
    }, null, 8 /* PROPS */, ["label", "modelValue"])) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true), _cache[6] || (_cache[6] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _ctx.manifestDirEditable ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_4, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_manifestLocationDesc')), 1 /* TEXT */)) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true), _cache[7] || (_cache[7] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_button, {
      class: "button install-button",
      disabled: _ctx.isInstalling || !_ctx.appDir || _ctx.manifestDirEditable && !_ctx.manifestDir,
      onClick: $options.runInstall,
      variant: "elevated"
    }, {
      default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)((0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('buttonLabel_installApp')), 1 /* TEXT */)]),
      _: 1 /* STABLE */
    }, 8 /* PROPS */, ["disabled", "onClick"])])) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true), _cache[13] || (_cache[13] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _ctx.isInstallSuccess ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_5, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_6, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_installSuccessTitle')), 1 /* TEXT */), _cache[8] || (_cache[8] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_7, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_installSuccessDesc')), 1 /* TEXT */), _cache[9] || (_cache[9] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _cache[10] || (_cache[10] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", {
      class: "success-icon"
    }, "🎉", -1 /* CACHED */))])) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true), _cache[14] || (_cache[14] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _ctx.isInstallError ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_8, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_9, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_installErrorTitle')), 1 /* TEXT */), _cache[11] || (_cache[11] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_10, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('pageContent_installErrorDesc')), 1 /* TEXT */), _cache[12] || (_cache[12] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_button, {
      class: "button error-button",
      onClick: _cache[2] || (_cache[2] = $event => _ctx.isInstallError = false),
      variant: "elevated"
    }, {
      default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)((0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($options.getText('buttonLabel_goBack')), 1 /* TEXT */)]),
      _: 1 /* STABLE */
    })])) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true)]),
    _: 1 /* STABLE */
  })) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true);
}

/***/ },

/***/ "./src/setup/App.vue?vue&type=template&id=95b38f34"
/*!*********************************************************!*\
  !*** ./src/setup/App.vue?vue&type=template&id=95b38f34 ***!
  \*********************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   render: () => (/* reexport safe */ _node_modules_webpack_plugin_vuetify_dist_scriptLoader_cjs_ruleSet_1_rules_0_use_node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_templateLoader_js_ruleSet_1_rules_3_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_template_id_95b38f34__WEBPACK_IMPORTED_MODULE_0__.render)
/* harmony export */ });
/* harmony import */ var _node_modules_webpack_plugin_vuetify_dist_scriptLoader_cjs_ruleSet_1_rules_0_use_node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_templateLoader_js_ruleSet_1_rules_3_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_template_id_95b38f34__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!../../node_modules/babel-loader/lib/index.js!../../node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!../../node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./App.vue?vue&type=template&id=95b38f34 */ "./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/setup/App.vue?vue&type=template&id=95b38f34");


/***/ },

/***/ "./src/setup/main.js"
/*!***************************!*\
  !*** ./src/setup/main.js ***!
  \***************************/
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony import */ var vue__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vue */ "./node_modules/vue/dist/vue.runtime.esm-bundler.js");
/* harmony import */ var utils_app__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! utils/app */ "./src/utils/app.js");
/* harmony import */ var utils_vuetify__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! utils/vuetify */ "./src/utils/vuetify.js");
/* harmony import */ var _App__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ./App */ "./src/setup/App.vue");




async function init() {
  await (0,utils_app__WEBPACK_IMPORTED_MODULE_1__.loadFonts)(['400 14px Roboto', '500 14px Roboto']);
  const app = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createApp)(_App__WEBPACK_IMPORTED_MODULE_3__["default"]);
  await (0,utils_app__WEBPACK_IMPORTED_MODULE_1__.configApp)(app);
  await (0,utils_vuetify__WEBPACK_IMPORTED_MODULE_2__.configVuetify)(app);
  app.mount('body');
}

// only run in a frame
if (window.top !== window) {
  init();
}

/***/ }

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
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
/******/ 		if (!(moduleId in __webpack_modules__)) {
/******/ 			delete __webpack_module_cache__[moduleId];
/******/ 			var e = new Error("Cannot find module '" + moduleId + "'");
/******/ 			e.code = 'MODULE_NOT_FOUND';
/******/ 			throw e;
/******/ 		}
/******/ 		__webpack_modules__[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = __webpack_modules__;
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/chunk loaded */
/******/ 	(() => {
/******/ 		var deferred = [];
/******/ 		__webpack_require__.O = (result, chunkIds, fn, priority) => {
/******/ 			if(chunkIds) {
/******/ 				priority = priority || 0;
/******/ 				for(var i = deferred.length; i > 0 && deferred[i - 1][2] > priority; i--) deferred[i] = deferred[i - 1];
/******/ 				deferred[i] = [chunkIds, fn, priority];
/******/ 				return;
/******/ 			}
/******/ 			var notFulfilled = Infinity;
/******/ 			for (var i = 0; i < deferred.length; i++) {
/******/ 				var [chunkIds, fn, priority] = deferred[i];
/******/ 				var fulfilled = true;
/******/ 				for (var j = 0; j < chunkIds.length; j++) {
/******/ 					if ((priority & 1 === 0 || notFulfilled >= priority) && Object.keys(__webpack_require__.O).every((key) => (__webpack_require__.O[key](chunkIds[j])))) {
/******/ 						chunkIds.splice(j--, 1);
/******/ 					} else {
/******/ 						fulfilled = false;
/******/ 						if(priority < notFulfilled) notFulfilled = priority;
/******/ 					}
/******/ 				}
/******/ 				if(fulfilled) {
/******/ 					deferred.splice(i--, 1)
/******/ 					var r = fn();
/******/ 					if (r !== undefined) result = r;
/******/ 				}
/******/ 			}
/******/ 			return result;
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			for(var key in definition) {
/******/ 				if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 					Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.prototype.hasOwnProperty.call(obj, prop))
/******/ 	})();
/******/ 	
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
/******/ 	/* webpack/runtime/set anonymous default export name */
/******/ 	(() => {
/******/ 		// set .name for anonymous default exports per ES spec
/******/ 		__webpack_require__.dn = (x) => {
/******/ 			(Object.getOwnPropertyDescriptor(x, "name") || {}).writable || Object.defineProperty(x, "name", { value: "default", configurable: true });
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/jsonp chunk loading */
/******/ 	(() => {
/******/ 		// no baseURI
/******/ 		
/******/ 		// object to store loaded and loading chunks
/******/ 		// undefined = chunk not loaded, null = chunk preloaded/prefetched
/******/ 		// [resolve, reject, Promise] = chunk loading, 0 = chunk loaded
/******/ 		var installedChunks = {
/******/ 			"setup": 0
/******/ 		};
/******/ 		
/******/ 		// no chunk on demand loading
/******/ 		
/******/ 		// no prefetching
/******/ 		
/******/ 		// no preloaded
/******/ 		
/******/ 		// no HMR
/******/ 		
/******/ 		// no HMR manifest
/******/ 		
/******/ 		__webpack_require__.O.j = (chunkId) => (installedChunks[chunkId] === 0);
/******/ 		
/******/ 		// install a JSONP callback for chunk loading
/******/ 		var webpackJsonpCallback = (parentChunkLoadingFunction, data) => {
/******/ 			var [chunkIds, moreModules, runtime] = data;
/******/ 			// add "moreModules" to the modules object,
/******/ 			// then flag all "chunkIds" as loaded and fire callback
/******/ 			var moduleId, chunkId, i = 0;
/******/ 			if(chunkIds.some((id) => (installedChunks[id] !== 0))) {
/******/ 				for(moduleId in moreModules) {
/******/ 					if(__webpack_require__.o(moreModules, moduleId)) {
/******/ 						__webpack_require__.m[moduleId] = moreModules[moduleId];
/******/ 					}
/******/ 				}
/******/ 				if(runtime) var result = runtime(__webpack_require__);
/******/ 			}
/******/ 			if(parentChunkLoadingFunction) parentChunkLoadingFunction(data);
/******/ 			for(;i < chunkIds.length; i++) {
/******/ 				chunkId = chunkIds[i];
/******/ 				if(__webpack_require__.o(installedChunks, chunkId) && installedChunks[chunkId]) {
/******/ 					installedChunks[chunkId][0]();
/******/ 				}
/******/ 				installedChunks[chunkId] = 0;
/******/ 			}
/******/ 			return __webpack_require__.O(result);
/******/ 		}
/******/ 		
/******/ 		var chunkLoadingGlobal = globalThis["webpackChunkcaptcha_automation"] = globalThis["webpackChunkcaptcha_automation"] || [];
/******/ 		chunkLoadingGlobal.forEach(webpackJsonpCallback.bind(null, 0));
/******/ 		chunkLoadingGlobal.push = webpackJsonpCallback.bind(null, chunkLoadingGlobal.push.bind(chunkLoadingGlobal));
/******/ 	})();
/******/ 	
/************************************************************************/
/******/ 	
/******/ 	// startup
/******/ 	// Load entry module and return exports
/******/ 	// This entry module depends on other loaded chunks and execution need to be delayed
/******/ 	var __webpack_exports__ = __webpack_require__.O(undefined, ["commons-ui"], () => (__webpack_require__("./src/setup/main.js")))
/******/ 	__webpack_exports__ = __webpack_require__.O(__webpack_exports__);
/******/ 	
/******/ })()
;