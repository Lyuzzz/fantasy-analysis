// The service worker only wires the toolbar icon to the side panel.
// All ESPN and service requests are made by the panel itself, and only when the
// user clicks "Analyze" - nothing runs in the background.
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});
