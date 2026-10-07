const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const config=Object.fromEntries(fs.readFileSync('.env','utf8').split(/\r?\n/).filter(x=>x.includes('=')&&!x.startsWith('#')).map(x=>{const i=x.indexOf('=');return[x.slice(0,i),x.slice(i+1)];}));
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'taxi-admin-browser-'));
const browser=spawn(process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--remote-debugging-port=9242','--remote-debugging-address=127.0.0.1','--user-data-dir='+folder,'--no-first-run','--no-default-browser-check','about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));let ws;
const keepalive=setInterval(()=>{},1000),deadline=setTimeout(()=>{console.error('Browser test timed out');browser.kill();process.exit(1);},180000);
(async()=>{
 let targets;for(let i=0;i<50;i++){try{targets=await(await fetch('http://127.0.0.1:9242/json/list')).json();break;}catch{await sleep(200);}}assert(targets,'Chrome debugger did not start');
 ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
 const pending=new Map(),exceptions=[];let seq=0;
 ws.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.id){const p=pending.get(data.id);pending.delete(data.id);if(p)data.error?p.reject(new Error(data.error.message)):p.resolve(data.result);}else if(data.method==='Runtime.exceptionThrown'){const error=data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text;exceptions.push(error);console.error('Browser JS error:',error);}});
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 const wait=async expression=>{for(let i=0;i<100;i++){if(await evaluate('Boolean('+expression+')'))return;await sleep(150);}console.error('UI diagnostics:',await evaluate("({role:typeof user!=='undefined'?user?.role:null,message:document.querySelector('#message')?.textContent,loading:typeof loadingPromise!=='undefined'?!!loadingPromise:null})"));throw new Error('UI condition failed: '+expression);};
 const fill=(selector,value)=>evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('input',{bubbles:true}));})()`);
 const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const screenshot=async name=>{await evaluate("window.scrollTo(0,0);document.querySelector('#message').textContent=''");await sleep(250);const shot=await send('Page.captureScreenshot',{format:'png'});fs.mkdirSync('docs/screenshots',{recursive:true});fs.writeFileSync('docs/screenshots/'+name+'.png',Buffer.from(shot.data,'base64'));};
 const login=async(username,password,role)=>{await fill('#login-form [name=username]',username);await fill('#login-form [name=password]',password);await evaluate("document.querySelector('#login-form').requestSubmit()");await wait(`user?.role===${JSON.stringify(role)} && loadingPromise===null && document.querySelector('#message').textContent.includes('Đã đăng nhập')`);};
 const nav=async page=>{await click(`[data-view="${page}"]`);await wait(`currentPage===${JSON.stringify(page)}`);};
 await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 const tileBody=Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#edf2f5"/><path d="M0 80H256M80 0V256" stroke="#d7e1e8" stroke-width="3"/></svg>').toString('base64');
 ws.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.method==='Fetch.requestPaused')send('Fetch.fulfillRequest',{requestId:data.params.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'image/svg+xml'},{name:'Cache-Control',value:'max-age=3600'}],body:tileBody}).catch(()=>{});});
 await send('Fetch.enable',{patterns:[{urlPattern:'https://tile.openstreetmap.org/*',requestStage:'Request'}]});
 await send('Page.navigate',{url:'http://127.0.0.1:8080/'});await wait("document.querySelector('#login-form') && typeof Features !== 'undefined'");await evaluate('initialSession');



 await login(config.ADMIN_USERNAME||'admin',config.ADMIN_PASSWORD,'admin');
 const suffix=Date.now().toString(36),name='profileui'+suffix,password='Test-'+suffix;
 await evaluate(`api('drivers','POST',${JSON.stringify({name:'Profile UI test',phone:name,plate:name,username:name,password,model:'Vios',seats:4,license:name})})`);
 await click('#logout');await wait("document.querySelector('#workspace').hidden");await login(name,password,'driver');
 await nav('profile');await wait("document.querySelector('#edit-profile')&&!document.querySelector('#edit-profile').hidden");
 assert(await evaluate("document.querySelector('#profile-form [name=name]').disabled && document.querySelector('#save-profile').hidden && document.querySelector('#password-page').hidden && document.querySelector('#vehicle-request-page').hidden"));
 await click('#edit-profile');assert(await evaluate("!document.querySelector('#profile-form [name=name]').disabled && !document.querySelector('#save-profile').hidden"));
 await fill('#profile-form [name=age]','24');await fill('#profile-form [name=gender]','female');await fill('#profile-form [name=hometown]','UI test hometown');await fill('#profile-form [name=experience_years]','3');
 await evaluate("document.querySelector('#profile-form').requestSubmit()");await wait("!Features.editingProfile && loadingPromise===null && document.querySelector('#message').textContent.includes('Đã cập nhật hồ sơ')");
 assert(await evaluate("document.querySelector('#save-profile').hidden && !document.querySelector('#edit-profile').hidden && document.querySelector('#profile-form [name=age]').disabled && profileData.age===24 && profileData.gender==='female'"));
 await click('#edit-profile');await fill('#profile-form [name=hometown]','Unsaved');await click('#cancel-profile');assert(await evaluate("document.querySelector('#profile-form [name=hometown]').value==='UI test hometown'"));
 await nav('password');assert(await evaluate("document.querySelector('#profile-panel').hidden && !document.querySelector('#password-page').hidden && document.querySelector('#vehicle-request-page').hidden"));
 await nav('vehicle-request');assert(await evaluate("document.querySelector('#profile-panel').hidden && document.querySelector('#password-page').hidden && !document.querySelector('#vehicle-request-page').hidden && !document.querySelector('#vehicle-request-panel').hidden"));
 assert.deepEqual(exceptions,[]);console.log('PASS: separate profile/password/vehicle pages; read-only profile, edit/save/return to read-only, cancel restores persisted values');
})().catch(error=>{console.error(error.stack);process.exitCode=1;}).finally(async()=>{if(ws)ws.close();browser.kill();await sleep(500);clearInterval(keepalive);clearTimeout(deadline);});
