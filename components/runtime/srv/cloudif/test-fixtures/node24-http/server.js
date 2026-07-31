import http from 'node:http';
const port=Number(process.env.PORT||8080);
http.createServer((req,res)=>{
  res.setHeader('content-type','application/json');
  if(req.url==='/health') return res.end(JSON.stringify({ok:true,service:'cloudif-node24-fixture'}));
  res.end(JSON.stringify({ok:true,path:req.url,node:process.versions.node}));
}).listen(port,'0.0.0.0');
