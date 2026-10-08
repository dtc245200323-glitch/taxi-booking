const SupportChat=window.SupportChat={
  selected:null,rows:[],busy:false,refreshing:null,signature:'',drafts:new Map(),
  allowed(){return user&&['admin','customer'].includes(user.role);},
  updateVisibility(){
    const label=user?.role==='admin'?'Nh\u1eadn tin nh\u1eafn':'Nh\u1eafn chatbot';$('#support-launcher .support-launcher-label').textContent=label;$('#support-launcher').title=label;$('#support-launcher').setAttribute('aria-label',label);
    document.querySelectorAll('.support-admin-tabs').forEach(el=>el.hidden=user?.role!=='admin');
    document.querySelectorAll('[data-support-open]').forEach(button=>button.hidden=!this.allowed());
    if(!this.allowed())$('#support-panel').hidden=true;
    $('#support-launcher').hidden=!this.allowed()||(user?.role==='customer'&&!window.TaxiChat?.choicesOpen);$('#support-launcher').classList.toggle('customer-support',user?.role==='customer');
  },
  reset(){this.selected=null;this.rows=[];this.signature='';this.drafts.clear();$('#support-panel').hidden=true;$('#support-form').reset();$('#support-messages').replaceChildren();$('#support-list').replaceChildren();$('#support-error').textContent='';},
  async open(){
    if(!this.allowed())return;window.TaxiChat?.closeChoices();$('#chat-panel').hidden=true;$('#driver-support-panel').hidden=true;$('#support-panel').hidden=false;
    $('#support-list').hidden=user.role!=='admin';
    await this.refresh();$('#support-form input').focus();
  },
  async refresh(){
    if(!this.allowed())return;if(this.refreshing)return this.refreshing;
    this.refreshing=this.fetchData().finally(()=>this.refreshing=null);return this.refreshing;
  },
  async fetchData(){
    const owner=user.id,rows=await api('support/conversations');if(user?.id!==owner)return;
    this.rows=rows;const unread=rows.reduce((sum,row)=>sum+Number(row.unread),0);
    document.querySelectorAll('[data-support-count]').forEach(el=>{el.textContent=unread>99?'99+':unread;el.hidden=!unread;});
    if($('#support-panel').hidden)return;
    if(user.role==='customer'&&!rows.some(row=>row.id===this.selected))this.selected=rows[0]?.id||null;
    const list=$('#support-list'),listKey=JSON.stringify(rows.map(row=>[row.id,row.last_message,row.unread,row.closed_at,row.rating]));
    if(list.dataset.key!==listKey){list.dataset.key=listKey;list.innerHTML=rows.map(row=>`<button type="button" class="support-conversation" data-support-thread="${row.id}"><b>${escape(row.name)}</b><small>${escape(row.last_message||'Chưa có tin nhắn')}</small>${Number(row.unread)?`<span class="support-count">${row.unread}</span>`:''}</button>`).join('')||'<p class="hint">Chưa có khách hàng nhắn tin.</p>';}
    list.querySelectorAll('[data-support-thread]').forEach(button=>button.classList.toggle('active',Number(button.dataset.supportThread)===this.selected));
    const selected=this.rows.find(row=>row.id===this.selected);
    this.renderActions(selected);
    $('#support-title').textContent=user.role==='admin'?(selected?'Hỗ trợ · '+selected.name:'Hỗ trợ khách hàng'):'Nhắn tin với Admin';
    $('#support-form').hidden=!!selected?.closed_at;
    $('#support-form input').disabled=!!selected?.closed_at||(user.role==='admin'&&!this.selected);
    $('#support-form button').disabled=this.busy||!!selected?.closed_at||(user.role==='admin'&&!this.selected);
    if(!this.selected){$('#support-messages').innerHTML='<p class="support-empty">'+(user.role==='admin'?'Chọn khách hàng để xem và trả lời tin nhắn.':'Gửi tin nhắn cho Admin. Nội dung sẽ được lưu và Admin có thể trả lời tại trung tâm hỗ trợ.')+'</p>';return;}
    const thread=this.selected,messages=await api('support/conversations/'+thread+'/messages');
    if(user?.id!==owner||this.selected!==thread||$('#support-panel').hidden)return;
    const key=JSON.stringify([thread,messages]);
    if(key!==this.signature){
      const box=$('#support-messages'),atBottom=box.scrollHeight-box.scrollTop-box.clientHeight<70||!this.signature;
      box.innerHTML=messages.map(item=>`<article class="support-message ${item.sender_role===user.role?'mine':''}"><small>${escape(item.sender_name)} · ${new Date(item.created_at).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'})}</small><p>${escape(item.content)}</p></article>`).join('');
      this.signature=key;if(atBottom)box.scrollTop=box.scrollHeight;
    }
    if(messages.length&&Number(selected?.unread)>0){await api('support/conversations/'+thread+'/read','POST',{last_id:messages.at(-1).id});}
  },
  async select(id){
    if(this.busy)return;this.drafts.set(this.selected,$('#support-form input').value);this.selected=id;this.signature='';
    $('#support-form input').value=this.drafts.get(id)||'';$('#support-error').textContent='';await this.refresh();
  },
  renderActions(row){
    const box=$('#support-actions');
    if(!row){box.innerHTML=user?.role==='customer'?'<button type="button" data-support-new>Bắt đầu cuộc trò chuyện mới</button>':'';return;}
    const closed=!!row.closed_at;
    box.innerHTML=closed?'<p>Cuộc trò chuyện đã kết thúc.</p>':'<button type="button" class="secondary" data-support-close-thread>Kết thúc trò chuyện</button>';
    if(closed&&user.role==='customer')box.insertAdjacentHTML('beforeend',`<p>Đánh giá hỗ trợ của Admin</p><div class="support-stars" role="group" aria-label="Đánh giá từ 1 đến 5 sao">${[1,2,3,4,5].map(n=>`<button type="button" data-support-rating="${n}" aria-label="${n} sao" aria-pressed="${n==row.rating}" class="${n<=Number(row.rating)?'chosen':''}">★</button>`).join('')}</div><small>${row.rating?'Đã đánh giá '+row.rating+'/5 sao':''}</small><button type="button" data-support-new>Bắt đầu cuộc trò chuyện mới</button>`);
    if(closed&&user.role==='admin'&&row.rating)box.insertAdjacentHTML('beforeend',`<p>Khách hàng đánh giá: ${row.rating}/5 sao</p>`);
    if(user.role==='customer'&&this.rows.length>1)box.insertAdjacentHTML('beforeend',`<label>Lịch sử trò chuyện<select id="support-history">${this.rows.map(item=>`<option value="${item.id}" ${item.id===this.selected?'selected':''}>#${item.id} · ${item.closed_at?'Đã kết thúc':'Đang trò chuyện'}</option>`).join('')}</select></label>`);
  },
  async action(kind,rating){
    if(this.busy)return;this.busy=true;const owner=user?.id;
    try{
      const path=kind==='new'?'support/conversations/new':'support/conversations/'+this.selected+'/'+kind;
      const result=await api(path,'POST',rating?{rating}:{});
      if(user?.id!==owner)return;
      if(kind==='new'){this.selected=result.id;this.signature='';$('#support-form').reset();}
      if(this.refreshing)await this.refreshing;await this.refresh();$('#support-error').textContent='';
    }catch(error){if(user?.id===owner)$('#support-error').textContent=error.message;}
    finally{this.busy=false;const row=this.rows.find(item=>item.id===this.selected);$('#support-form button').disabled=!!row?.closed_at||(user?.role==='admin'&&!this.selected);}
  },
  async send(){
    if(this.busy||!this.allowed())return;
    const input=$('#support-form input'),content=input.value.trim();if(!content)return;
    const owner=user.id,thread=this.selected;this.busy=true;$('#support-form button').disabled=true;$('#support-error').textContent='';
    try{
      const result=await api('support/messages','POST',{content,conversation_id:thread});
      if(user?.id!==owner)return;this.selected=result.conversation_id;input.value='';this.drafts.delete(thread);this.signature='';
      if(this.refreshing)await this.refreshing;await this.refresh();$('#support-messages').scrollTop=$('#support-messages').scrollHeight;
    }catch(error){if(user?.id===owner)$('#support-error').textContent=error.message;}
    finally{this.busy=false;$('#support-form button').disabled=!this.allowed()||(user?.role==='admin'&&!this.selected);}
  }
};
document.addEventListener('click',event=>{
  if(event.target.closest('[data-support-close-thread]'))SupportChat.action('close');
  if(event.target.closest('[data-support-new]'))SupportChat.action('new');
  const rating=event.target.closest('[data-support-rating]');if(rating)SupportChat.action('rating',Number(rating.dataset.supportRating));
  if(event.target.closest('[data-support-open]')){if(user?.role==='customer'&&event.target.closest('#support-launcher'))TaxiChat.open();else SupportChat.open().catch(error=>$('#support-error').textContent=error.message);}
  const thread=event.target.closest('[data-support-thread]');if(thread)SupportChat.select(Number(thread.dataset.supportThread)).catch(error=>$('#support-error').textContent=error.message);
});
document.addEventListener('change',event=>{if(event.target.id==='support-history')SupportChat.select(Number(event.target.value)).catch(error=>$('#support-error').textContent=error.message);});
$('#support-close').onclick=()=>$('#support-panel').hidden=true;
$('#support-form').onsubmit=event=>{event.preventDefault();SupportChat.send();};
document.addEventListener('keydown',event=>{if(event.key==='Escape')$('#support-panel').hidden=true;});
setInterval(()=>SupportChat.refresh().catch(error=>{if(!$('#support-panel').hidden)$('#support-error').textContent=error.message;}),5000);
SupportChat.updateVisibility();
