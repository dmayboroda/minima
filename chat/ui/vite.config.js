import { resolve } from "path";
import { defineConfig } from "vite";

// import strip from "@rollup/plugin-strip";

export default defineConfig({
  root: "./src",
  base: "./",

  server: {
    open: "./src/index.html",
    host: true,
  },

  css: {
    devSourcemap: true,
    preprocessorOptions: {
      scss: {
        charset: false,
      },
    },
  },

  build: {
    outDir: "../dist",
    assetsDir: "./",
    assetsInlineLimit: 4096,
    emptyOutDir: true,
    target: "es2015",

    // css: {
    //   preprocessorOptions: {
    //     scss: {
    //       additionalData: `
    //         @import "./src/styles/variables";
    //         @import "./src/styles/mixins";
    //         @import "./src/styles/general";
    //         @import "./src/styles/header";
    //         @import "./src/styles/blocks";
    //         @import "./src/styles/footer";
    //         @import "./src/styles/modal";
    //       `
    //     }
    //   }
    // },

    rollupOptions: {
      input: {
        main: resolve(__dirname, "./src/index.html"),
      },
      output: {
        manualChunks: undefined,

        /* https://stackoverflow.com/questions/71180561/vite-change-ouput-directory-of-assets
        *****************************************************************************************/

        // assetFileNames: (assetInfo) => {
        //   let extType = assetInfo.name.split('.').at(1);
        //   if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
        //     extType = 'img';
        //   }
        //   return `assets/${extType}/[name]-[hash][extname]`;
        // },

        assetFileNames: ({ name }) => {
          if (/\.(gif|jpe?g|png|svg)$/.test(name ?? "")) {
            return `[name][extname]`;
          }

          // if (/\.css$/.test(name ?? "")) {
          //   //return "assets/css/[name]-[hash][extname]";
          //   return `css/[name]-[hash][extname]`;
          // }

          // // default value
          // // ref: https://rollupjs.org/guide/en/#outputassetfilenames
          return "[name]-[hash][extname]";
        },
      },
    //   plugins: [strip()],
    },
  },
});
