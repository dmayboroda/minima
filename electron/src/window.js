const path = require("path");
const { BrowserWindow } = require("electron");

exports.createBrowserWindow = () => {
  return new BrowserWindow({
    width: 1024,
    height: 768,
    minWidth: 400, 
    minHeight: 600,
    icon: path.join(__dirname, "assets/icons/png/favicon.png"),
    backgroundColor: "#fff",
    autoHideMenuBar: true,
    webPreferences: {
      devTools: false,
      contextIsolation: true,
      webviewTag: true,
      preload: path.join(__dirname, "../preload.js"),
      enableRemoteModule: true,
      nodeIntegration: false,
      nativeWindowOpen: true,
      webSecurity: true,
      allowRunningInsecureContent: true
    },
  });
};
