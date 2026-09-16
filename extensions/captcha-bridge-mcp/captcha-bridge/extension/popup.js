const toggle = document.getElementById('toggle');

const { enabled } = await chrome.storage.local.get({ enabled: true });
toggle.checked = enabled;

toggle.addEventListener('change', async () => {
  await chrome.storage.local.set({ enabled: toggle.checked });
  chrome.runtime.sendMessage({ toggle: true });
});