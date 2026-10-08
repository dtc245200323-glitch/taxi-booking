const driverSupportPage=document.createElement('section');driverSupportPage.id='driver-support-page';driverSupportPage.dataset.page='driver-support';driverSupportPage.hidden=true;$('#workspace').append(driverSupportPage);
const DriverSupportChat=window.DriverSupportChat={
  selected:null,rows:[],busy:false,refreshing:null,signature:'',drafts:new Map(),
  allowed(){return user&&['admin','driver'].includes(user.role);},
  updateVisibility(){
    const parent=document.body;if($('#driver-support-panel').parentElement!==parent)parent.append($('#driver-support-panel'));
    document.querySelectorAll('[data-driver-support-open]').forEach(button=>button.hidden=!this.allowed());
    if(!this.allowed())$('#driver-support-panel').hidden=true;
    $('#driver-support-launcher').hidden=user?.role!=='driver';
  },
  reset(){this.selected=null;this.rows=[];this.signature='';this.drafts.clear();$('#driver-support-panel').hidden=true;$('#driver-support-form').reset();$('#driver-support-messages').replaceChildren();$('#driver-support-list').replaceChildren();$('#driver-support-error').textContent='';},
  async open(){
    if(!this.allowed())return;$('#chat-panel').hidden=true;$('#support-panel').hidden=true;$('#driver-support-panel').hidden=false;
    $('#driver-support-list').hidden=user.role!=='admin';
    await this.refresh();$('#driver-support-form input').focus();
  },
  async refresh(){
    if(!this.allowed())return;if(this.refreshing)return this.refreshing;
    this.refreshing=this.fetchData().finally(()=>this.refreshing=null);return this.refreshing;
  },
  async fetchData(){
    const owner=user.id,rows=await api('driver-support/conversations');if(user?.id!==owner)return;
    this.rows=rows;const unread=rows.reduce((sum,row)=>sum+Number(row.unread),0);
    document.querySelectorAll('[data-driver-support-count]').forEach(el=>{el.textContent=unread>99?'99+':unread;el.hidden=!unread;});
    if($('#driver-support-panel').hidden)return;
    if(user.role==='driver')this.selected=rows[0]?.id||null;
    const list=$('#driver-support-list'),listKey=JSON.stringify(rows.map(row=>[row.id,row.last_message,row.unread]));
    if(list.dataset.key!==listKey){list.dataset.key=listKey;list.innerHTML=rows.map(row=>`<button type="button" class="driver-support-conversation" data-driver-support-thread="${row.id}"><b>${escape(row.name)}</b><small>${escape(row.last_message||'Chưa có tin nhắn')}</small>${Number(row.unread)?`<span class="driver-support-count">${row.unread}</span>`:''}</button>`).join('')||'<p class="hint">Chưa có tài xế nhắn tin.</p>';}
    list.querySelectorAll('[data-driver-support-thread]').forEach(button=>button.classList.toggle('active',Number(button.dataset.driverSupportThread)===this.selected));
    const selected=this.rows.find(row=>row.id===this.selected);
    $('#driver-support-title').textContent=user.role==='admin'?(selected?'Hỗ trợ · '+selected.name:'Hỗ trợ tài xế'):'Nhắn tin với Admin';
    $('#driver-support-form input').disabled=user.role==='admin'&&!this.selected;
    $('#driver-support-form button').disabled=this.busy||(user.role==='admin'&&!this.selected);
    if(!this.selected){$('#driver-support-messages').innerHTML='<p class="driver-support-empty">'+(user.role==='admin'?'Chọn tài xế để xem và trả lời tin nhắn.':'Gửi tin nhắn cho Admin. Nội dung sẽ được lưu và Admin có thể trả lời tại trung tâm hỗ trợ.')+'</p>';return;}
    const thread=this.selected,messages=await api('driver-support/conversations/'+thread+'/messages');
    if(user?.id!==owner||this.selected!==thread||$('#driver-support-panel').hidden)return;
    const key=JSON.stringify([thread,messages]);
    if(key!==this.signature){
      const box=$('#driver-support-messages'),atBottom=box.scrollHeight-box.scrollTop-box.clientHeight<70||!this.signature;
      box.innerHTML=messages.map(item=>`<article class="driver-support-message ${item.sender_role===user.role?'mine':''}"><small>${escape(item.sender_name)} · ${new Date(item.created_at).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'})}</small><p>${escape(item.content)}</p></article>`).join('');
      this.signature=key;if(atBottom)box.scrollTop=box.scrollHeight;
    }
    if(messages.length&&Number(selected?.unread)>0){await api('driver-support/conversations/'+thread+'/read','POST',{last_id:messages.at(-1).id});}
  },
  async select(id){
    if(this.busy)return;this.drafts.set(this.selected,$('#driver-support-form input').value);this.selected=id;this.signature='';
    $('#driver-support-form input').value=this.drafts.get(id)||'';$('#driver-support-error').textContent='';await this.refresh();
  },
  async send(){
    if(this.busy||!this.allowed())return;
    const input=$('#driver-support-form input'),content=input.value.trim();if(!content)return;
    const owner=user.id,thread=this.selected;this.busy=true;$('#driver-support-form button').disabled=true;$('#driver-support-error').textContent='';
    try{
      const result=await api('driver-support/messages','POST',{content,conversation_id:thread});
      if(user?.id!==owner)return;this.selected=result.conversation_id;input.value='';this.drafts.delete(thread);this.signature='';
      if(this.refreshing)await this.refreshing;await this.refresh();$('#driver-support-messages').scrollTop=$('#driver-support-messages').scrollHeight;
    }catch(error){if(user?.id===owner)$('#driver-support-error').textContent=error.message;}
    finally{this.busy=false;$('#driver-support-form button').disabled=!this.allowed()||(user?.role==='admin'&&!this.selected);}
  }
};
document.addEventListener('click',event=>{
  if(event.target.closest('[data-driver-support-open]'))DriverSupportChat.open().catch(error=>$('#driver-support-error').textContent=error.message);
  const thread=event.target.closest('[data-driver-support-thread]');if(thread)DriverSupportChat.select(Number(thread.dataset.driverSupportThread)).catch(error=>$('#driver-support-error').textContent=error.message);
});
$('#driver-support-close').onclick=()=>$('#driver-support-panel').hidden=true;
$('#driver-support-form').onsubmit=event=>{event.preventDefault();DriverSupportChat.send();};
document.addEventListener('keydown',event=>{if(event.key==='Escape')$('#driver-support-panel').hidden=true;});
setInterval(()=>DriverSupportChat.refresh().catch(error=>{if(!$('#driver-support-panel').hidden)$('#driver-support-error').textContent=error.message;}),5000);
DriverSupportChat.updateVisibility();
