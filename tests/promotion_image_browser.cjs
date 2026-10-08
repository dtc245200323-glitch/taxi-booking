let testPromoId;
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const config=Object.fromEntries(fs.readFileSync('.env','utf8').split(/\r?\n/).filter(x=>x.includes('=')&&!x.startsWith('#')).map(x=>{const i=x.indexOf('=');return[x.slice(0,i),x.slice(i+1)];}));
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'taxi-admin-browser-'));
const browser=spawn(process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--remote-debugging-port=9383','--remote-debugging-address=127.0.0.1','--user-data-dir='+folder,'--no-first-run','--no-default-browser-check','about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));let ws;
const keepalive=setInterval(()=>{},1000),deadline=setTimeout(()=>{console.error('Browser test timed out');browser.kill();process.exit(1);},120000);
(async()=>{
 let targets;for(let i=0;i<50;i++){try{targets=await(await fetch('http://127.0.0.1:9383/json/list')).json();break;}catch{await sleep(200);}}assert(targets,'Chrome debugger did not start');
 ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
 const pending=new Map(),exceptions=[];let seq=0;
 ws.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.id){const p=pending.get(data.id);pending.delete(data.id);if(p)data.error?p.reject(new Error(data.error.message)):p.resolve(data.result);}else if(data.method==='Runtime.exceptionThrown'){const error=data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text;exceptions.push(error);console.error('Browser JS error:',error);}});
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 const wait=async expression=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await sleep(150);}throw new Error('UI condition failed: '+expression);};
 const fill=(selector,value)=>evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('input',{bubbles:true}));})()`);
 const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const screenshot=async name=>{await evaluate("window.scrollTo(0,0);document.querySelector('#message').textContent=''");await sleep(250);const shot=await send('Page.captureScreenshot',{format:'png'});fs.mkdirSync('docs/screenshots',{recursive:true});fs.writeFileSync('docs/screenshots/'+name+'.png',Buffer.from(shot.data,'base64'));};
 const login=async(username,password,role)=>{await fill('#login-form [name=username]',username);await fill('#login-form [name=password]',password);await evaluate("document.querySelector('#login-form').requestSubmit()");await wait(`user?.role===${JSON.stringify(role)} && loadingPromise===null && document.querySelector('#message').textContent.includes('Đã đăng nhập')`);};
 const nav=async page=>{await click(`[data-view="${page}"]`);await wait(`currentPage===${JSON.stringify(page)}`);};
 await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:'http://127.0.0.1:8080/'});await wait("document.querySelector('#login-form') && typeof Features !== 'undefined'");await evaluate('initialSession');



 console.log('Logging in');await login(config.ADMIN_USERNAME||'admin',config.ADMIN_PASSWORD,'admin');console.log('Creating image test');
 testPromoId=await evaluate(`(async()=>{const p=await api('admin/promotions','POST',{code:'IMGUI'+Date.now(),title:'Image upload test',kind:'fixed',value:1000,max_discount:1000,min_fare:0,usage_limit:10,per_customer_limit:1,days:1});await Promotions.load();return p.id;})()`);
 await nav('promotion-settings');
 const selector='[data-promo-image="'+testPromoId+'"]';

 let chooser;ws.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.method==='Page.fileChooserOpened')chooser=data.params;});
 await send('Page.setInterceptFileChooserDialog',{enabled:true});
 const point=await evaluate(`(()=>{const button=document.querySelector('[data-choose-promo-image="${testPromoId}"]');button.scrollIntoView({block:'center'});const rect=button.getBoundingClientRect();return {x:rect.x+rect.width/2,y:rect.y+rect.height/2};})()`);
 await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
 for(let i=0;i<50&&!chooser;i++)await sleep(100);assert(chooser,'Choose image must open the native file chooser');
 assert(await evaluate('Promotions.pickingImage'));await evaluate(`window.testFileInput=document.querySelector('${selector}');Promotions.load()`);assert(await evaluate(`testFileInput===document.querySelector('${selector}')`));
 console.log('Native chooser opened; uploading image');await send('DOM.setFileInputFiles',{backendNodeId:chooser.backendNodeId,files:[path.resolve('static/assets/taxi-hero.png')]});
 await wait(`!Promotions.uploadingImages.size && document.querySelector('${selector}').closest('article').querySelector('img').src.includes('/api/promotions/')`);
 let savedUrl=await evaluate(`document.querySelector('${selector}').closest('article').querySelector('img').src`);
 await wait(`document.querySelector('${selector}').closest('article').querySelector('img').naturalWidth>0`);
 console.log('Checking reload');await send('Page.reload',{ignoreCache:true});await wait("typeof initialSession!=='undefined'");await evaluate('initialSession');await wait("user?.role==='admin' && loadingPromise===null");
 await wait(`document.querySelector('${selector}')?.closest('article').querySelector('img').naturalWidth>0`);
 assert.equal(await evaluate(`document.querySelector('${selector}').closest('article').querySelector('img').src`),savedUrl);

 await evaluate(`(async()=>{const blob=await (await fetch('/assets/taxi-services.png')).blob();const transfer=new DataTransfer();transfer.items.add(new File([blob],'drop-test.png',{type:'image/png'}));document.querySelector('[data-promo-drop="${testPromoId}"]').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));})()`);
 await wait('!Promotions.uploadingImages.size');const replacedUrl=await evaluate(`document.querySelector('${selector}').closest('article').querySelector('img').src`);assert.notEqual(replacedUrl,savedUrl,'A different file must replace the saved image');savedUrl=replacedUrl;
 console.log('Drag-and-drop upload passed');
 console.log('Checking customer image');await click('#logout');await wait("!user");await login('khach',config.CUSTOMER_PASSWORD,'customer');
 await wait(`document.querySelector('[data-offer="${testPromoId}"] img')?.naturalWidth>0`);
 assert.equal(await evaluate(`document.querySelector('[data-offer="${testPromoId}"] img').src`),savedUrl);
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('[data-offer="${testPromoId}"]'),'::after').content`),'none');
 assert.equal(await evaluate(`getComputedStyle(document.querySelector('[data-offer="${testPromoId}"]')).backgroundImage`),'none');
 assert.deepEqual(exceptions,[]);console.log('PASS: actual file upload, saved preview after reload, customer banner image loads without blue overlay');
})().catch(error=>{console.error(error.message);process.exitCode=1;}).finally(async()=>{if(testPromoId){const cleanup=require('node:child_process').spawnSync('docker',['compose','exec','-T','app','python','-c','from app import db; import sys; conn=db(); conn.execute("DELETE FROM promotions WHERE id=%s",(int(sys.argv[1]),)); conn.commit(); conn.close()',String(testPromoId)],{windowsHide:true,encoding:'utf8'});if(cleanup.status!==0){console.error('Test cleanup failed');process.exitCode=1;}}if(ws)ws.close();browser.kill();await sleep(500);clearInterval(keepalive);clearTimeout(deadline);});
