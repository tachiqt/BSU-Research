const JavaScriptObfuscator = require('javascript-obfuscator');
const fs = require('fs');
const path = require('path');

const FILES = ['script.js', 'reports.js', 'faculty.js'];
const DIR = __dirname;

const options = {
  compact: true,
  controlFlowFlattening: true,
  controlFlowFlatteningThreshold: 0.5,
  deadCodeInjection: true,
  deadCodeInjectionThreshold: 0.2,
  debugProtection: false,
  disableConsoleOutput: false,
  identifierNamesGenerator: 'hexadecimal',
  log: false,
  numbersToExpressions: true,
  renameGlobals: false,
  selfDefending: false,
  simplify: true,
  splitStrings: true,
  splitStringsChunkLength: 5,
  stringArray: true,
  stringArrayCallsTransform: true,
  stringArrayEncoding: ['base64'],
  stringArrayIndexShift: true,
  stringArrayRotate: true,
  stringArrayShuffle: true,
  stringArrayWrappersCount: 2,
  stringArrayWrappersChainedCalls: true,
  stringArrayWrappersParametersMaxCount: 4,
  stringArrayWrappersType: 'function',
  stringArrayThreshold: 0.75,
  transformObjectKeys: true,
  unicodeEscapeSequence: false
};

FILES.forEach((file) => {
  const srcPath = path.join(DIR, file);
  const outPath = path.join(DIR, file.replace('.js', '.obf.js'));
  if (!fs.existsSync(srcPath)) {
    console.warn('Skip (not found):', file);
    return;
  }
  const code = fs.readFileSync(srcPath, 'utf8');
  const obfuscated = JavaScriptObfuscator.obfuscate(code, options).getObfuscatedCode();
  fs.writeFileSync(outPath, obfuscated, 'utf8');
  console.log('Obfuscated:', file, '->', path.basename(outPath));
});

console.log('Done. Serve the .obf.js files in production.');
