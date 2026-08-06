; (function () {
  // 5022b4
  var script = document.createElement('script');
  var isPreview = window.name === 'kimi-website-preview';
  script.src = isPreview
    ? 'https://statics.moonshot.cn/sdk/preview.1XL1Ndry.min.js'
    : 'https://statics.moonshot.cn/sdk/publish.DQfKjRRp.min.js'
  script.async = true;
  document.head.appendChild(script);
})()
