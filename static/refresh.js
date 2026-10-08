(() => {
  const indicator=document.createElement('div');
  indicator.className='pull-refresh';indicator.hidden=true;indicator.setAttribute('role','status');indicator.setAttribute('aria-live','polite');
  indicator.innerHTML='<span class="pull-refresh-spinner" aria-hidden="true"></span><span class="pull-refresh-label"></span>';
  document.body.append(indicator);
  const label=indicator.querySelector('.pull-refresh-label');
  let start=null,distance=0,busy=false,hideTimer;
  function begin(x,y,target){
    if(!user||busy||window.scrollY>0||$('#admin-dialog').open||target.closest('button,a,input,select,textarea,dialog,.real-map,.promo-track,[contenteditable]'))return;
    clearTimeout(hideTimer);start={x,y};distance=0;
  }
  function move(x,y,event){
    if(!start||busy)return;
    const delta=y-start.y;
    if(delta<=0||Math.abs(x-start.x)>Math.abs(delta)){cancel();return;}
    if(window.scrollY>0){cancel();return;}
    distance=Math.min(delta,160);
    if(distance<10)return;
    if(event.cancelable)event.preventDefault();
    indicator.hidden=false;indicator.classList.remove('loading');
    indicator.style.setProperty('--pull-offset',Math.min(distance*.45,60)+'px');
    label.textContent=distance>=90?'Thả tay để tải lại':'Kéo xuống để tải lại';
  }
  function cancel(){start=null;distance=0;if(!busy)indicator.hidden=true;}
  async function end(){
    if(!start)return;start=null;
    if(distance<90){cancel();return;}
    busy=true;indicator.hidden=false;indicator.classList.add('loading');label.textContent='Đang tải lại dữ liệu...';
    try{await load();label.textContent='Đã cập nhật dữ liệu';}
    catch(error){label.textContent='Không tải lại được dữ liệu';message(error.message,true);}
    finally{busy=false;distance=0;indicator.classList.remove('loading');hideTimer=setTimeout(()=>indicator.hidden=true,1500);}
  }
  document.addEventListener('touchstart',event=>{if(event.touches.length===1){const point=event.touches[0];begin(point.clientX,point.clientY,event.target);}else cancel();},{passive:true});
  document.addEventListener('touchmove',event=>{if(event.touches.length!==1){cancel();return;}const point=event.touches[0];move(point.clientX,point.clientY,event);},{passive:false});
  document.addEventListener('touchend',end);document.addEventListener('touchcancel',cancel);
  document.addEventListener('pointerdown',event=>{if(event.pointerType==='mouse'&&event.button===0)begin(event.clientX,event.clientY,event.target);});
  document.addEventListener('pointermove',event=>{if(event.pointerType==='mouse'&&event.buttons===1)move(event.clientX,event.clientY,event);});
  document.addEventListener('pointerup',event=>{if(event.pointerType==='mouse')end();});
  window.addEventListener('blur',cancel);
})();
