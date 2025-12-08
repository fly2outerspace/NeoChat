const { contextBridge } = require('electron');
const { ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  ping: () => 'pong'
});

contextBridge.exposeInMainWorld('backendLog', {
  onLog: (callback) => {
    const listener = (_event, payload) => {
      callback(payload);
    };
    ipcRenderer.on('backend-log', listener);
    return () => ipcRenderer.removeListener('backend-log', listener);
  },
  getHistory: () => ipcRenderer.invoke('backend-log-history'),
});

