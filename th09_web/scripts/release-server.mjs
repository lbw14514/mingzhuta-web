// Public server: only manifest-listed game assets are reachable. Never serve
// the development tree, original executable, local saves, logs or credentials.
// Manifest and files are re-validated per request: a rebuilt release on disk
// takes effect without a restart, and a mismatching file is refused with 503
// instead of being truncated to a stale Content-Length.
import http from 'node:http';
import {createHash} from 'node:crypto';
import {createReadStream,readFileSync,statSync} from 'node:fs';
import {resolve,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {attachNetplay} from './netplay-relay.mjs';
const mime={'.html':'text/html; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.wasm':'application/wasm','.ogg':'audio/ogg','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.woff2':'font/woff2','.webmanifest':'application/manifest+json'};
export async function releaseServer({root=resolve(fileURLToPath(new URL('../site/',import.meta.url))),port=3007,host='127.0.0.1'}={}){
 const manifestPath=resolve(root,'manifest.json');
 function loadRelease(){
  const manifest=JSON.parse(readFileSync(manifestPath,'utf8')),files=new Map();
  for(const [url,entry] of Object.entries(manifest.files)){
   const file=resolve(root,entry.path);if(!url.startsWith('/')||url.includes('..')||!file.startsWith(root+sep)||!Number.isSafeInteger(entry.bytes)||entry.bytes<0||!/^[a-f0-9]{64}$/.test(entry.sha256))throw Error('Invalid release manifest');
   if(statSync(file).size!==entry.bytes)throw Error('Incomplete release: '+entry.path);files.set(url,{...entry,file});
  }
  const html=readFileSync(files.get('/').file,'utf8'),inlineHashes=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>"'sha256-"+createHash('sha256').update(m[1].replaceAll('\r\n','\n').replaceAll('\r','\n')).digest('base64')+"'").join(' ');
  const st=statSync(manifestPath);
  return {manifest,files,inlineHashes,mtimeMs:st.mtimeMs,size:st.size};
 }
 let release=null;
 try{release=loadRelease();}catch(e){console.error(new Date().toISOString()+' RELEASE LOAD FAILED: '+e.message);}
 let lastRefresh=0;
 function refresh(force=false){
  const now=Date.now();if(!force&&now-lastRefresh<1000)return;lastRefresh=now;
  try{
   if(!release){release=loadRelease();return;}
   const st=statSync(manifestPath);
   if(!force&&st.mtimeMs===release.mtimeMs&&st.size===release.size)return;
   release=loadRelease();
  }catch(e){if(force)console.error(new Date().toISOString()+' RELEASE RELOAD FAILED: '+e.message);}
 }
 const refuse=(res,entry,actual)=>{console.error(new Date().toISOString()+' REFUSE '+entry.path+' manifest='+entry.bytes+' actual='+actual);res.writeHead(503,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'resource size mismatch with release manifest',path:entry.path,manifestBytes:entry.bytes,actualBytes:actual}));};
 const server=http.createServer((req,res)=>{
  const t0=Date.now();
  res.on('finish',()=>{const quiet=req.method==='GET'&&(req.url.startsWith('/packages/th15/th15.data')||req.url.startsWith('/packages/th15/music/'))&&res.statusCode<400;if(!quiet)console.error(new Date().toISOString()+' '+req.method+' '+req.url.slice(0,70)+' -> '+res.statusCode+' '+(Date.now()-t0)+'ms');});
  res.setHeader('Cross-Origin-Opener-Policy','same-origin');res.setHeader('Cross-Origin-Embedder-Policy','require-corp');res.setHeader('Cross-Origin-Resource-Policy','same-origin');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Cache-Control','no-store');
  if(!release){
   refresh(true);
   if(!release){res.writeHead(503,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'release incomplete: manifest and files do not match yet',retry:true}));return;}
  }
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self' 'wasm-unsafe-eval' "+release.inlineHashes+"; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' ws: wss:; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'");
  if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405,{'Allow':'GET, HEAD'}).end();return;}
  let url;try{url=new URL(req.url,'http://localhost');}catch{res.writeHead(400).end();return;}
  refresh(false);
  if(!release){res.writeHead(503,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'release incomplete: manifest and files do not match yet',retry:true}));return;}
  if(url.pathname==='/manifest.json'){const body=Buffer.from(JSON.stringify(release.manifest));res.setHeader('Content-Type',mime['.json']);res.setHeader('Content-Length',body.length);res.end(req.method==='HEAD'?undefined:body);return;}
  let entry=release.files.get(url.pathname);
  if(!entry){res.writeHead(404).end();return;}
  let actual=0;try{actual=statSync(entry.file).size;}catch{actual=-1;}
  if(actual!==entry.bytes){
   refresh(true);
   entry=release.files.get(url.pathname);
   if(!entry){res.writeHead(404).end();return;}
   try{actual=statSync(entry.file).size;}catch{actual=-1;}
   if(actual!==entry.bytes){refuse(res,entry,actual);return;}
  }
  const type=Object.keys(mime).find(e=>entry.path.endsWith(e));res.setHeader('Content-Type',mime[type]??'application/octet-stream');
  const tag='"'+entry.sha256+'"';res.setHeader('ETag',tag);res.setHeader('Accept-Ranges','bytes');
  if(entry.immutable||url.searchParams.get('v')===entry.sha256)res.setHeader('Cache-Control','public, max-age=31536000, immutable');else res.setHeader('Cache-Control','no-cache');
  if(url.pathname==='/app-shell-sw.js'){res.setHeader('Service-Worker-Allowed','/');res.setHeader('Cache-Control','no-store');}
  if(req.headers['if-none-match']===tag){res.writeHead(304).end();return;}
  let start=0,end=entry.bytes-1,code=200;
  if(req.headers.range&&(!req.headers['if-range']||req.headers['if-range']===tag)){
   const range=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range);if(!range||(!range[1]&&!range[2])){res.writeHead(416,{'Content-Range':'bytes */'+entry.bytes}).end();return;}
   if(range[1]){start=Number(range[1]);if(range[2])end=Math.min(end,Number(range[2]));}else start=Math.max(0,entry.bytes-Number(range[2]));
   if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start>end||start<0||start>=entry.bytes){res.writeHead(416,{'Content-Range':'bytes */'+entry.bytes}).end();return;}
   code=206;res.setHeader('Content-Range',`bytes ${start}-${end}/${entry.bytes}`);
  }
  res.setHeader('Content-Length',Math.max(0,end-start+1));res.writeHead(code);if(req.method==='HEAD'||entry.bytes===0){res.end();return;}
  const stream=createReadStream(entry.file,{start,end});stream.on('error',()=>res.destroy());res.on('close',()=>stream.destroy());stream.pipe(res);
 });
 server.requestTimeout=30000;server.headersTimeout=15000;server.maxHeadersCount=80;
 const netplay=attachNetplay(server,{build:release?release.manifest.version:'incomplete'});
 await new Promise((yes,no)=>{server.once('error',no);server.listen(port,host,yes);});return {server,netplay,url:'http://'+host+':'+server.address().port,manifest:release?release.manifest:{version:'incomplete',game:'unknown',files:{}}};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const at=process.argv.indexOf('--port'),port=at>=0?Number(process.argv[at+1]):3007;if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid port');
 const hi=process.argv.indexOf('--host'),host=hi>=0?process.argv[hi+1]:'127.0.0.1';
 const {url,manifest}=await releaseServer({port,host});console.log(`${manifest.game} ${manifest.version} ${url}`);
}
