import { readFileSync, writeFileSync } from 'node:fs';
import { WASI } from 'node:wasi';
const wasm = readFileSync('C:/touhou15-web-port/dl/lzbuild/lz.wasm');
const wasi = new WASI({ version: 'preview1', args: ['lz'], env: {}, preopens: {} });
const { instance } = await WebAssembly.instantiate(wasm, { wasi_snapshot_preview1: wasi.wasiImport });
const code = wasi.start(instance);
console.error('exit', code);
