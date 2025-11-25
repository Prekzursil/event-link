// Karma configuration for Angular tests
module.exports = function (config) {
  config.set({
    browsers: ['ChromeHeadlessCustom'],
    customLaunchers: {
      ChromeHeadlessCustom: {
        base: 'ChromeHeadless',
        flags: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
      },
    },
    singleRun: true,
    reporters: ['progress'],
    restartOnFileChange: true,
    logLevel: config.LOG_INFO,
    plugins: [
      require('karma-jasmine'),
      require('karma-chrome-launcher'),
      require('@angular-devkit/build-angular/plugins/karma'),
    ],
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
    client: {
      clearContext: false,
    },
  });
};
