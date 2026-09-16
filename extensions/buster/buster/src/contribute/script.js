/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=script&lang=js"
/*!**********************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=script&lang=js ***!
  \**********************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var ___WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ../../ */ "./node_modules/vueton/index.js");

/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = ({
  name: 'vn-contribute',
  components: {
    [___WEBPACK_IMPORTED_MODULE_0__.Button.name]: ___WEBPACK_IMPORTED_MODULE_0__.Button,
    [___WEBPACK_IMPORTED_MODULE_0__.Icon.name]: ___WEBPACK_IMPORTED_MODULE_0__.Icon,
    [___WEBPACK_IMPORTED_MODULE_0__.LinearProgress.name]: ___WEBPACK_IMPORTED_MODULE_0__.LinearProgress
  },
  props: {
    extName: {
      type: String,
      required: true
    },
    extSlug: {
      type: String,
      required: true
    },
    notice: {
      type: String,
      default: ''
    },
    theme: {
      type: String,
      default: ''
    }
  },
  emits: ['open'],
  data: function () {
    return {
      goals: null,
      sponsors: null,
      apiHost: 'sponsors.vapps.dev',
      goHost: 'go.vapps.dev'
    };
  },
  computed: {
    appClasses: function () {
      return {
        'header-notice': this.notice
      };
    }
  },
  methods: {
    setup: async function () {
      const action = new URL(window.location.href).searchParams.get('action');
      const rsp = await fetch(`https://${this.apiHost}/api/v1/status/${this.extSlug}?action=${action}`);
      const data = await rsp.json();
      const exchangeRate = data.funding.currency.exchangeRate;
      data.funding.value = Math.trunc(data.funding.value / exchangeRate);
      data.funding.goal = Math.trunc(data.funding.goal / exchangeRate);
      this.goals = {
        items: data.goals,
        funding: data.funding
      };
      if (data.sponsors.length) {
        this.sponsors = data.sponsors;
      }
    },
    showPage: function (service) {
      const url = `https://${this.goHost}/${service}?pr=${this.extSlug}&src=app`;
      this.$emit('open', {
        url
      });
    },
    showSponsor: function (url) {
      this.$emit('open', {
        url
      });
    },
    getSponsorLogo: function (logo, {
      variant
    } = {}) {
      let logoUrl = logo[variant];
      if (!logoUrl) {
        logoUrl = logo.light;
      }
      return logoUrl;
    }
  },
  mounted: function () {
    this.setup();
  }
});

/***/ },

/***/ "./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=script&lang=js"
/*!************************************************************************************************************************************************************!*\
  !*** ./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=script&lang=js ***!
  \************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var vueton__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vueton */ "./node_modules/vueton/index.js");
/* harmony import */ var vueton_components_contribute__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! vueton/components/contribute */ "./node_modules/vueton/components/contribute/index.js");
/* harmony import */ var utils_app__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! utils/app */ "./src/utils/app.js");
/* harmony import */ var utils_common__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! utils/common */ "./src/utils/common.js");




/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = ({
  components: {
    [vueton__WEBPACK_IMPORTED_MODULE_0__.App.name]: vueton__WEBPACK_IMPORTED_MODULE_0__.App,
    [vueton_components_contribute__WEBPACK_IMPORTED_MODULE_1__.Contribute.name]: vueton_components_contribute__WEBPACK_IMPORTED_MODULE_1__.Contribute
  },
  data: function () {
    return {
      extName: (0,utils_common__WEBPACK_IMPORTED_MODULE_3__.getText)('extensionName'),
      extSlug: 'buster',
      notice: '',
      theme: ''
    };
  },
  methods: {
    setup: async function () {
      const query = new URL(window.location.href).searchParams;
      if (query.get('action') === 'auto') {
        this.notice = `This page is shown once a year while using the extension.`;
      }
      this.theme = await (0,utils_app__WEBPACK_IMPORTED_MODULE_2__.getAppTheme)();
      document.addEventListener('themeChange', ev => {
        this.theme = ev.detail;
      });
    },
    showPage: utils_app__WEBPACK_IMPORTED_MODULE_2__.showPage
  },
  created: function () {
    document.title = (0,utils_common__WEBPACK_IMPORTED_MODULE_3__.getText)('pageTitle', [(0,utils_common__WEBPACK_IMPORTED_MODULE_3__.getText)('pageTitle_contribute'), this.extName]);
    this.setup();
  }
});

/***/ },

/***/ "./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss"
/*!*********************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss ***!
  \*********************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
// extracted by mini-css-extract-plugin


/***/ },

/***/ "./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=style&index=0&id=168b6810&lang=scss"
/*!***********************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=style&index=0&id=168b6810&lang=scss ***!
  \***********************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
// extracted by mini-css-extract-plugin


/***/ },

/***/ "./node_modules/vueton/components/contribute/Contribute.vue"
/*!******************************************************************!*\
  !*** ./node_modules/vueton/components/contribute/Contribute.vue ***!
  \******************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _Contribute_vue_vue_type_template_id_7da3d57e__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./Contribute.vue?vue&type=template&id=7da3d57e */ "./node_modules/vueton/components/contribute/Contribute.vue?vue&type=template&id=7da3d57e");
/* harmony import */ var _Contribute_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ./Contribute.vue?vue&type=script&lang=js */ "./node_modules/vueton/components/contribute/Contribute.vue?vue&type=script&lang=js");
/* harmony import */ var _Contribute_vue_vue_type_style_index_0_id_7da3d57e_lang_scss__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ./Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss */ "./node_modules/vueton/components/contribute/Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss");
/* harmony import */ var _vue_loader_dist_exportHelper_js__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ../../../vue-loader/dist/exportHelper.js */ "./node_modules/vue-loader/dist/exportHelper.js");




;


const __exports__ = /*#__PURE__*/(0,_vue_loader_dist_exportHelper_js__WEBPACK_IMPORTED_MODULE_3__["default"])(_Contribute_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_1__["default"], [['render',_Contribute_vue_vue_type_template_id_7da3d57e__WEBPACK_IMPORTED_MODULE_0__.render],['__file',"node_modules/vueton/components/contribute/Contribute.vue"]])
/* hot reload */
if (false) // removed by dead control flow
{}


/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (__exports__);

/***/ },

/***/ "./src/contribute/App.vue"
/*!********************************!*\
  !*** ./src/contribute/App.vue ***!
  \********************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _App_vue_vue_type_template_id_168b6810__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./App.vue?vue&type=template&id=168b6810 */ "./src/contribute/App.vue?vue&type=template&id=168b6810");
/* harmony import */ var _App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ./App.vue?vue&type=script&lang=js */ "./src/contribute/App.vue?vue&type=script&lang=js");
/* harmony import */ var _App_vue_vue_type_style_index_0_id_168b6810_lang_scss__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ./App.vue?vue&type=style&index=0&id=168b6810&lang=scss */ "./src/contribute/App.vue?vue&type=style&index=0&id=168b6810&lang=scss");
/* harmony import */ var _node_modules_vue_loader_dist_exportHelper_js__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ../../node_modules/vue-loader/dist/exportHelper.js */ "./node_modules/vue-loader/dist/exportHelper.js");




;


const __exports__ = /*#__PURE__*/(0,_node_modules_vue_loader_dist_exportHelper_js__WEBPACK_IMPORTED_MODULE_3__["default"])(_App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_1__["default"], [['render',_App_vue_vue_type_template_id_168b6810__WEBPACK_IMPORTED_MODULE_0__.render],['__file',"src/contribute/App.vue"]])
/* hot reload */
if (false) // removed by dead control flow
{}


/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (__exports__);

/***/ },

/***/ "./node_modules/vueton/components/contribute/Contribute.vue?vue&type=script&lang=js"
/*!******************************************************************************************!*\
  !*** ./node_modules/vueton/components/contribute/Contribute.vue?vue&type=script&lang=js ***!
  \******************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (/* reexport safe */ _babel_loader_lib_index_js_vue_loader_dist_index_js_ruleSet_0_use_0_Contribute_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_0__["default"])
/* harmony export */ });
/* harmony import */ var _babel_loader_lib_index_js_vue_loader_dist_index_js_ruleSet_0_use_0_Contribute_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../../babel-loader/lib/index.js!../../../vue-loader/dist/index.js??ruleSet[0].use[0]!./Contribute.vue?vue&type=script&lang=js */ "./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=script&lang=js");
 

/***/ },

/***/ "./src/contribute/App.vue?vue&type=script&lang=js"
/*!********************************************************!*\
  !*** ./src/contribute/App.vue?vue&type=script&lang=js ***!
  \********************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (/* reexport safe */ _node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_0__["default"])
/* harmony export */ });
/* harmony import */ var _node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_script_lang_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../node_modules/babel-loader/lib/index.js!../../node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./App.vue?vue&type=script&lang=js */ "./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=script&lang=js");
 

/***/ },

/***/ "./node_modules/vueton/components/contribute/Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss"
/*!***************************************************************************************************************!*\
  !*** ./node_modules/vueton/components/contribute/Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss ***!
  \***************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony import */ var _mini_css_extract_plugin_dist_loader_js_css_loader_dist_cjs_js_vue_loader_dist_stylePostLoader_js_postcss_loader_dist_cjs_js_sass_loader_dist_cjs_js_clonedRuleSet_2_use_3_vue_loader_dist_index_js_ruleSet_0_use_0_Contribute_vue_vue_type_style_index_0_id_7da3d57e_lang_scss__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../../mini-css-extract-plugin/dist/loader.js!../../../css-loader/dist/cjs.js!../../../vue-loader/dist/stylePostLoader.js!../../../postcss-loader/dist/cjs.js!../../../sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!../../../vue-loader/dist/index.js??ruleSet[0].use[0]!./Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss */ "./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=style&index=0&id=7da3d57e&lang=scss");


/***/ },

/***/ "./src/contribute/App.vue?vue&type=style&index=0&id=168b6810&lang=scss"
/*!*****************************************************************************!*\
  !*** ./src/contribute/App.vue?vue&type=style&index=0&id=168b6810&lang=scss ***!
  \*****************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony import */ var _node_modules_mini_css_extract_plugin_dist_loader_js_node_modules_css_loader_dist_cjs_js_node_modules_vue_loader_dist_stylePostLoader_js_node_modules_postcss_loader_dist_cjs_js_node_modules_sass_loader_dist_cjs_js_clonedRuleSet_2_use_3_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_style_index_0_id_168b6810_lang_scss__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../node_modules/mini-css-extract-plugin/dist/loader.js!../../node_modules/css-loader/dist/cjs.js!../../node_modules/vue-loader/dist/stylePostLoader.js!../../node_modules/postcss-loader/dist/cjs.js!../../node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!../../node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./App.vue?vue&type=style&index=0&id=168b6810&lang=scss */ "./node_modules/mini-css-extract-plugin/dist/loader.js!./node_modules/css-loader/dist/cjs.js!./node_modules/vue-loader/dist/stylePostLoader.js!./node_modules/postcss-loader/dist/cjs.js!./node_modules/sass-loader/dist/cjs.js??clonedRuleSet-2.use[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=style&index=0&id=168b6810&lang=scss");


/***/ },

/***/ "./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=template&id=7da3d57e"
/*!***************************************************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=template&id=7da3d57e ***!
  \***************************************************************************************************************************************************************************************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   render: () => (/* binding */ render)
/* harmony export */ });
/* harmony import */ var vue__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vue */ "./node_modules/vue/dist/vue.runtime.esm-bundler.js");

const _hoisted_1 = {
  key: 0,
  class: "notice"
};
const _hoisted_2 = {
  class: "desc"
};
const _hoisted_3 = {
  class: "desc-text"
};
const _hoisted_4 = {
  class: "ext-name"
};
const _hoisted_5 = {
  class: "image-container"
};
const _hoisted_6 = ["src"];
const _hoisted_7 = {
  key: 0,
  class: "goals-wrap"
};
const _hoisted_8 = {
  class: "goals"
};
const _hoisted_9 = {
  class: "goal"
};
const _hoisted_10 = {
  class: "progress-details"
};
const _hoisted_11 = {
  class: "progress-value"
};
const _hoisted_12 = {
  class: "progress-value"
};
const _hoisted_13 = {
  class: "progress-value"
};
const _hoisted_14 = {
  class: "cta-buttons"
};
const _hoisted_15 = {
  class: "image-container"
};
const _hoisted_16 = ["src"];
const _hoisted_17 = {
  class: "image-container"
};
const _hoisted_18 = ["src"];
const _hoisted_19 = {
  key: 0,
  class: "sponsors-wrap"
};
const _hoisted_20 = {
  class: "sponsors"
};
const _hoisted_21 = {
  class: "sponsor-logo"
};
const _hoisted_22 = ["href", "onClick", "onKeyup"];
const _hoisted_23 = ["src"];
function render(_ctx, _cache, $props, $setup, $data, $options) {
  const _component_vn_icon = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-icon");
  const _component_vn_linear_progress = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-linear-progress");
  const _component_vn_button = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-button");
  return (0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", {
    class: (0,vue__WEBPACK_IMPORTED_MODULE_0__.normalizeClass)(["vn-contribute", $options.appClasses])
  }, [$props.notice ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_1, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($props.notice), 1 /* TEXT */)) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true), _cache[32] || (_cache[32] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _cache[33] || (_cache[33] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", {
    class: "title"
  }, "Help us make some avocado toast!", -1 /* CACHED */)), _cache[34] || (_cache[34] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_2, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_3, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("p", null, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("span", _hoisted_4, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)($props.extName), 1 /* TEXT */), _cache[3] || (_cache[3] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)(" is a project fueled by\n          love and crunchy toast, created for everyone to freely use and\n          improve.\n        ", -1 /* CACHED */))]), _cache[4] || (_cache[4] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _cache[5] || (_cache[5] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("p", null, "\n          You can support our goals and make a difference by sharing some\n          avocados with us! Every ounce will help add new features and keep\n          things afloat.\n        ", -1 /* CACHED */))]), _cache[8] || (_cache[8] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("picture", _hoisted_5, [_cache[6] || (_cache[6] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("source", {
    srcset: `./assets/illustration.webp`,
    type: "image/webp"
  }, null, -1 /* CACHED */)), _cache[7] || (_cache[7] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
    class: "desc-image",
    src: `https://${_ctx.apiHost}/static/images/illustration.png`,
    alt: "avocado and toast"
  }, null, 8 /* PROPS */, _hoisted_6)])]), _cache[35] || (_cache[35] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(vue__WEBPACK_IMPORTED_MODULE_0__.Transition, {
    name: "goals"
  }, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [_ctx.goals ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_7, [_cache[19] || (_cache[19] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", {
      class: "cta"
    }, "Support our current goals", -1 /* CACHED */)), _cache[20] || (_cache[20] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_8, [((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(true), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)(vue__WEBPACK_IMPORTED_MODULE_0__.Fragment, null, (0,vue__WEBPACK_IMPORTED_MODULE_0__.renderList)(_ctx.goals.items, goal => {
      return (0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_9, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_icon, {
        class: "goal-bullet",
        src: `./assets/circle.svg`
      }), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)(" " + (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)(goal), 1 /* TEXT */)]);
    }), 256 /* UNKEYED_FRAGMENT */))]), _cache[21] || (_cache[21] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_linear_progress, {
      class: "progress",
      "model-value": _ctx.goals.funding.value / _ctx.goals.funding.goal
    }, null, 8 /* PROPS */, ["model-value"]), _cache[22] || (_cache[22] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_10, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", null, [_cache[9] || (_cache[9] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)("\n            Raised\n            ", -1 /* CACHED */)), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("span", _hoisted_11, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)(_ctx.goals.funding.value), 1 /* TEXT */), _cache[10] || (_cache[10] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _cache[11] || (_cache[11] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
      class: "progress-token",
      src: `./assets/avocado.svg`
    }, null, -1 /* CACHED */)), _cache[12] || (_cache[12] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)("\n            of\n            ", -1 /* CACHED */)), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("span", _hoisted_12, (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)(_ctx.goals.funding.goal), 1 /* TEXT */), _cache[13] || (_cache[13] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), _cache[14] || (_cache[14] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
      class: "progress-token",
      src: `./assets/avocado.svg`
    }, null, -1 /* CACHED */)), _cache[15] || (_cache[15] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)("\n            goal\n          ", -1 /* CACHED */))]), _cache[18] || (_cache[18] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_13, [_cache[16] || (_cache[16] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)("\n            1\n            ", -1 /* CACHED */)), _cache[17] || (_cache[17] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
      class: "progress-token",
      src: `./assets/avocado.svg`
    }, null, -1 /* CACHED */)), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)("\n            =\n            " + (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)(_ctx.goals.funding.currency.symbol) + (0,vue__WEBPACK_IMPORTED_MODULE_0__.toDisplayString)(_ctx.goals.funding.currency.exchangeRate), 1 /* TEXT */)])])])) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true)]),
    _: 1 /* STABLE */
  }), _cache[36] || (_cache[36] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_14, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_button, {
    onClick: _cache[0] || (_cache[0] = $event => $options.showPage('patreon')),
    variant: "elevated"
  }, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("picture", _hoisted_15, [_cache[23] || (_cache[23] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("source", {
      srcset: `./assets/patreon.webp`,
      type: "image/webp"
    }, null, -1 /* CACHED */)), _cache[24] || (_cache[24] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
      src: `https://${_ctx.apiHost}/static/images/patreon.png`
    }, null, 8 /* PROPS */, _hoisted_16)])]),
    _: 1 /* STABLE */
  }), _cache[28] || (_cache[28] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_button, {
    class: "cta-coin",
    onClick: _cache[1] || (_cache[1] = $event => $options.showPage('crypto')),
    variant: "tonal"
  }, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [...(_cache[25] || (_cache[25] = [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
      src: `./assets/bitcoin.svg`
    }, null, -1 /* CACHED */)]))]),
    _: 1 /* STABLE */
  }), _cache[29] || (_cache[29] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_button, {
    onClick: _cache[2] || (_cache[2] = $event => $options.showPage('paypal')),
    variant: "elevated"
  }, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("picture", _hoisted_17, [_cache[26] || (_cache[26] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("source", {
      srcset: `./assets/paypal.webp`,
      type: "image/webp"
    }, null, -1 /* CACHED */)), _cache[27] || (_cache[27] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
      src: `https://${_ctx.apiHost}/static/images/paypal.png`
    }, null, 8 /* PROPS */, _hoisted_18)])]),
    _: 1 /* STABLE */
  })]), _cache[37] || (_cache[37] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(vue__WEBPACK_IMPORTED_MODULE_0__.Transition, {
    name: "sponsors"
  }, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [_ctx.sponsors ? ((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_19, [_cache[30] || (_cache[30] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", {
      class: "sponsors-title"
    }, "Sponsors", -1 /* CACHED */)), _cache[31] || (_cache[31] = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createTextVNode)()), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("div", _hoisted_20, [((0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(true), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)(vue__WEBPACK_IMPORTED_MODULE_0__.Fragment, null, (0,vue__WEBPACK_IMPORTED_MODULE_0__.renderList)(_ctx.sponsors, sponsor => {
      return (0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementBlock)("div", _hoisted_21, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("a", {
        href: sponsor.url,
        onClick: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withModifiers)($event => $options.showSponsor(sponsor.url), ["prevent"]),
        onKeyup: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withKeys)((0,vue__WEBPACK_IMPORTED_MODULE_0__.withModifiers)($event => $options.showSponsor(sponsor.url), ["prevent"]), ["enter"])
      }, [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createElementVNode)("img", {
        src: $options.getSponsorLogo(sponsor.logo, {
          variant: $props.theme
        })
      }, null, 8 /* PROPS */, _hoisted_23)], 40 /* PROPS, NEED_HYDRATION */, _hoisted_22)]);
    }), 256 /* UNKEYED_FRAGMENT */))])])) : (0,vue__WEBPACK_IMPORTED_MODULE_0__.createCommentVNode)("v-if", true)]),
    _: 1 /* STABLE */
  })], 2 /* CLASS */);
}

/***/ },

/***/ "./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=template&id=168b6810"
/*!*****************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=template&id=168b6810 ***!
  \*****************************************************************************************************************************************************************************************************************************************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   render: () => (/* binding */ render)
/* harmony export */ });
/* harmony import */ var vue__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vue */ "./node_modules/vue/dist/vue.runtime.esm-bundler.js");

function render(_ctx, _cache, $props, $setup, $data, $options) {
  const _component_vn_contribute = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-contribute");
  const _component_vn_app = (0,vue__WEBPACK_IMPORTED_MODULE_0__.resolveComponent)("vn-app");
  return (0,vue__WEBPACK_IMPORTED_MODULE_0__.openBlock)(), (0,vue__WEBPACK_IMPORTED_MODULE_0__.createBlock)(_component_vn_app, null, {
    default: (0,vue__WEBPACK_IMPORTED_MODULE_0__.withCtx)(() => [(0,vue__WEBPACK_IMPORTED_MODULE_0__.createVNode)(_component_vn_contribute, {
      extName: _ctx.extName,
      extSlug: _ctx.extSlug,
      notice: _ctx.notice,
      theme: _ctx.theme,
      onOpen: $options.showPage
    }, null, 8 /* PROPS */, ["extName", "extSlug", "notice", "theme", "onOpen"])]),
    _: 1 /* STABLE */
  });
}

/***/ },

/***/ "./node_modules/vueton/components/contribute/Contribute.vue?vue&type=template&id=7da3d57e"
/*!************************************************************************************************!*\
  !*** ./node_modules/vueton/components/contribute/Contribute.vue?vue&type=template&id=7da3d57e ***!
  \************************************************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   render: () => (/* reexport safe */ _webpack_plugin_vuetify_dist_scriptLoader_cjs_ruleSet_1_rules_0_use_babel_loader_lib_index_js_vue_loader_dist_templateLoader_js_ruleSet_1_rules_3_vue_loader_dist_index_js_ruleSet_0_use_0_Contribute_vue_vue_type_template_id_7da3d57e__WEBPACK_IMPORTED_MODULE_0__.render)
/* harmony export */ });
/* harmony import */ var _webpack_plugin_vuetify_dist_scriptLoader_cjs_ruleSet_1_rules_0_use_babel_loader_lib_index_js_vue_loader_dist_templateLoader_js_ruleSet_1_rules_3_vue_loader_dist_index_js_ruleSet_0_use_0_Contribute_vue_vue_type_template_id_7da3d57e__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../../webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!../../../babel-loader/lib/index.js!../../../vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!../../../vue-loader/dist/index.js??ruleSet[0].use[0]!./Contribute.vue?vue&type=template&id=7da3d57e */ "./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./node_modules/vueton/components/contribute/Contribute.vue?vue&type=template&id=7da3d57e");


/***/ },

/***/ "./src/contribute/App.vue?vue&type=template&id=168b6810"
/*!**************************************************************!*\
  !*** ./src/contribute/App.vue?vue&type=template&id=168b6810 ***!
  \**************************************************************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   render: () => (/* reexport safe */ _node_modules_webpack_plugin_vuetify_dist_scriptLoader_cjs_ruleSet_1_rules_0_use_node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_templateLoader_js_ruleSet_1_rules_3_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_template_id_168b6810__WEBPACK_IMPORTED_MODULE_0__.render)
/* harmony export */ });
/* harmony import */ var _node_modules_webpack_plugin_vuetify_dist_scriptLoader_cjs_ruleSet_1_rules_0_use_node_modules_babel_loader_lib_index_js_node_modules_vue_loader_dist_templateLoader_js_ruleSet_1_rules_3_node_modules_vue_loader_dist_index_js_ruleSet_0_use_0_App_vue_vue_type_template_id_168b6810__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! -!../../node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!../../node_modules/babel-loader/lib/index.js!../../node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!../../node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./App.vue?vue&type=template&id=168b6810 */ "./node_modules/webpack-plugin-vuetify/dist/scriptLoader.cjs??ruleSet[1].rules[0].use!./node_modules/babel-loader/lib/index.js!./node_modules/vue-loader/dist/templateLoader.js??ruleSet[1].rules[3]!./node_modules/vue-loader/dist/index.js??ruleSet[0].use[0]!./src/contribute/App.vue?vue&type=template&id=168b6810");


/***/ },

/***/ "./node_modules/vueton/components/contribute/index.js"
/*!************************************************************!*\
  !*** ./node_modules/vueton/components/contribute/index.js ***!
  \************************************************************/
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   Contribute: () => (/* reexport safe */ _Contribute__WEBPACK_IMPORTED_MODULE_0__["default"])
/* harmony export */ });
/* harmony import */ var _Contribute__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./Contribute */ "./node_modules/vueton/components/contribute/Contribute.vue");



/***/ },

/***/ "./src/contribute/main.js"
/*!********************************!*\
  !*** ./src/contribute/main.js ***!
  \********************************/
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony import */ var vue__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! vue */ "./node_modules/vue/dist/vue.runtime.esm-bundler.js");
/* harmony import */ var utils_app__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! utils/app */ "./src/utils/app.js");
/* harmony import */ var utils_vuetify__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! utils/vuetify */ "./src/utils/vuetify.js");
/* harmony import */ var _App__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ./App */ "./src/contribute/App.vue");




async function init() {
  await (0,utils_app__WEBPACK_IMPORTED_MODULE_1__.loadFonts)(['400 14px Roboto', '500 14px Roboto', '700 14px Roboto']);
  const app = (0,vue__WEBPACK_IMPORTED_MODULE_0__.createApp)(_App__WEBPACK_IMPORTED_MODULE_3__["default"]);
  await (0,utils_app__WEBPACK_IMPORTED_MODULE_1__.configApp)(app);
  await (0,utils_vuetify__WEBPACK_IMPORTED_MODULE_2__.configVuetify)(app);
  app.mount('body');
}
init();

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
/******/ 			"contribute": 0
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
/******/ 	var __webpack_exports__ = __webpack_require__.O(undefined, ["commons-ui"], () => (__webpack_require__("./src/contribute/main.js")))
/******/ 	__webpack_exports__ = __webpack_require__.O(__webpack_exports__);
/******/ 	
/******/ })()
;