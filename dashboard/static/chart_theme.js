// Shared Nord defaults for every Chart.js chart on the dashboard.
// Must be loaded AFTER Chart.js and BEFORE the scripts that create charts.
(function () {
  if (typeof Chart === "undefined") return;
  Chart.defaults.color = "#d8dee9";
  Chart.defaults.borderColor = "#3b4252";
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.tooltip.backgroundColor = "#2e3440";
  Chart.defaults.plugins.tooltip.borderColor = "#4c566a";
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = "#eceff4";
  Chart.defaults.plugins.tooltip.bodyColor = "#d8dee9";
})();
