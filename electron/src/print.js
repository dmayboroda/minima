const { ipcMain, BrowserWindow } = require("electron");

ipcMain.handle("print", async (event, arg) => {
  let printWindow = new BrowserWindow({ "auto-hide-menu-bar": true });
  printWindow.loadURL(arg);

  printWindow.webContents.on("did-finish-load", () => {
    printWindow.webContents.print();
  });
});
