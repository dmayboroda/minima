const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  print: (arg) => ipcRenderer.invoke("print", arg),
});
