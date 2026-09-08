import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('dist/client');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.woff2':'font/woff2','.png':'image/png','.ico':'image/x-icon','.rsc':'text/x-component'};
const server=http.createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');
 if(url.pathname.startsWith('/api/')||url.pathname.startsWith('/health/')){
  const upstream=http.request({host:'127.0.0.1',port:Number(process.env.GRETA_API_PORT||8000),method:req.method,path:req.url,headers:req.headers},r=>{res.writeHead(r.statusCode||502,r.headers);r.pipe(res)});
  upstream.on('error',()=>{if(!res.headersSent)res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({detail:'Greta API is unavailable. Start the backend service.'}))});
  req.pipe(upstream);return;
 }
 try{
  let filename=path.resolve(root,'.'+decodeURIComponent(url.pathname));
  if(filename!==root&&!filename.startsWith(root+path.sep)){res.writeHead(403);res.end();return}
  const info=await stat(filename).catch(()=>null);
  if(info?.isDirectory())filename=path.join(filename,'index.html');
  else if(!info)filename=path.join(root,'index.html');
  const body=await readFile(filename);
  res.writeHead(200,{'Content-Type':mime[path.extname(filename)]||'application/octet-stream','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'});res.end(body);
 }catch{res.writeHead(404);res.end('Not found')}
});
server.listen(Number(process.env.GRETA_WEB_PORT||3000),'127.0.0.1',()=>process.stdout.write('Greta available at http://127.0.0.1:'+(process.env.GRETA_WEB_PORT||3000)+'\n'));
