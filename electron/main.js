const { app } = require("electron");

app.allowRendererProcessReuse = true;
app.on("ready", () => {
  const window = require("./src/window");
  mainWindow = window.createBrowserWindow(app);
  
  mainWindow.loadURL(`file://${__dirname}/index.html`, { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36' });

  require("./src/print");
});

app.on("window-all-closed", () => {
  app.quit();
});
