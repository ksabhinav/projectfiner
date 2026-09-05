import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(repositoryRoot, 'node_modules/plotly.js-dist-min/plotly.min.js');
const destination = resolve(repositoryRoot, 'public/vendor/plotly.min.js');

mkdirSync(dirname(destination), { recursive: true });
copyFileSync(source, destination);
console.log('Prepared public/vendor/plotly.min.js from the locked npm dependency.');
