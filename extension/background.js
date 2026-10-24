// The service worker only connects the toolbar icon to the side panel.
// The panel itself makes all ESPN and service requests.
// It makes them only when the user clicks "Analyze". Nothing runs in the background.
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});
