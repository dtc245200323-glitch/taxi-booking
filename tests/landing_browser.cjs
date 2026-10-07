const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const config=Object.fromEntries(fs.readFileSync('.env','utf8').split(/\r?\n/).filter(x=>x.includes('=')&&!x.startsWith('#')).map(x=>{const i=x.indexOf('=');return[x.slice(0,i),x.slice(i+1)];}));
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'taxi-admin-browser-'));
const browser=spawn(process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--remote-debugging-port=9244','--remote-debugging-address=127.0.0.1','--user-data-dir='+folder,'--no-first-run','--no-default-browser-check','about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));let ws;
const keepalive=setInterval(()=>{},1000),deadline=setTimeout(()=>{console.error('Browser test timed out');browser.kill();process.exit(1);},180000);
(async()=>{
 let targets;for(let i=0;i<50;i++){try{targets=await(await fetch('http://127.0.0.1:9244/json/list')).json();break;}catch{await sleep(200);}}assert(targets,'Chrome debugger did not start');
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



 await wait("typeof Landing !== 'undefined' && Landing.promotions.length>0");
 await sleep(700);const metrics=await send('Page.getLayoutMetrics');const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:1440,height:metrics.cssContentSize.height,scale:1}});fs.writeFileSync('docs/screenshots/landing-desktop.png',Buffer.from(shot.data,'base64'));
 assert(await evaluate("document.querySelectorAll('.landing-service').length===3 && !document.querySelector('#login-panel').hidden"));
 assert(await evaluate("document.querySelector('#auth-page').hidden"));await click('[data-auth-login]');assert(await evaluate("location.hash==='#login' && document.querySelector('#login-panel').hidden && !document.querySelector('#auth-page').hidden"));
 await click('#toggle-login-password');assert(await evaluate("document.querySelector('#landing-password').type==='text'"));await click('#toggle-login-password');
 await click('#landing-register');assert(await evaluate("!document.querySelector('#register-form').hidden && document.querySelector('#login-form').hidden"));await screenshot('login-page');await click('#back-login');
 await click('#show-forgot');assert(await evaluate("!document.querySelector('#forgot-form').hidden"));await click('#forgot-form [data-login]');
 await click('[data-landing-home]');await click('[data-landing-info=support]');assert(await evaluate("!document.querySelector('#chat-panel').hidden"));await click('[data-chat-question]');await wait("TaxiChat.history.length===2");assert(await evaluate("document.querySelector('#chat-messages').textContent.includes('điểm đón')"));await screenshot('support-chat');await click('#chat-close');
 await click('#landing-view-promo');await wait("document.querySelector('[data-landing-use-code]')");const code=await evaluate("document.querySelector('[data-landing-use-code]').dataset.landingUseCode");await click('[data-landing-use-code]');assert(await evaluate("sessionStorage.getItem('landing-promo')==="+JSON.stringify(code)));
 await click('[data-landing-home]');await click('[data-landing-service=family]');await click('[data-landing-select-seats=\"7\"]');assert(await evaluate("sessionStorage.getItem('landing-seats')==='7'"));
 await login(config.ADMIN_USERNAME||'admin',config.ADMIN_PASSWORD,'admin');
 const suffix=Date.now().toString(36),name='landingui'+suffix,password='Test-'+suffix;
 await evaluate(`api('customers','POST',${JSON.stringify({name:'Landing browser test',phone:name,username:name,password})})`);
 await click('#logout');await wait("document.querySelector('#workspace').hidden");await login(name,password,'customer');
 assert(await evaluate("document.querySelector('#trip-form [name=seats][value=\"7\"]').checked && document.querySelector('#promo-code').value==="+JSON.stringify(code)));
 await click('[data-chat-open]');assert(await evaluate("!document.querySelector('#chat-panel').hidden"));await click('#chat-close');await click('#logout');await wait("document.querySelector('#workspace').hidden");await click('[data-landing-home]');
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await evaluate('window.scrollTo(0,0)');await sleep(300);assert(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"));await screenshot('landing-mobile');await click('[data-auth-login]');assert(await evaluate("document.documentElement.scrollWidth<=window.innerWidth && !document.querySelector('#auth-page').hidden"));await screenshot('login-mobile');await click('[data-chat-open]');await sleep(100);assert(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"));await click('#chat-close');
 await send('Page.navigate',{url:'http://127.0.0.1:8080/#register'});await wait("typeof Landing !== 'undefined'");await evaluate('initialSession');assert(await evaluate("!document.querySelector('#register-form').hidden && !document.querySelector('#auth-page').hidden && document.querySelector('#login-panel').hidden"));
 assert.deepEqual(exceptions,[]);console.log('PASS: landing layout, registration/reset links, password toggle, separate authentication pages, support chatbot, offers/service dialogs, booking preferences and mobile');
})().catch(error=>{console.error(error.stack);process.exitCode=1;}).finally(async()=>{if(ws)ws.close();browser.kill();await sleep(500);clearInterval(keepalive);clearTimeout(deadline);});
