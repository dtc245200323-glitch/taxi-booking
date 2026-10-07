const paymentLabels={awaiting_transfer:'Chưa chuyển khoản',pending:'Chờ xác nhận',success:'Chuyển khoản thành công',failed:'Chuyển khoản thất bại'};
const paymentBadge=p=>`<span class="badge ${p.status==='success'?'completed':p.status==='failed'?'cancelled':'pending'}">${paymentLabels[p.status]}</span>`;
const Extras=window.Extras={
  payments:[],seen:null,dialogTrip:null,uploading:false,
  reset(){this.payments=[];this.seen=null;this.dialogTrip=null;$('#customer-payments').replaceChildren();$('#payment-admin-list').replaceChildren();$('#bank-settings-form').reset();$('#avatar-file').value='';$('#header-avatar').textContent='●';$('#profile-photo').src='/assets/driver.svg';},
  async load(){
    const id=user?.id;if(!id)return;
    $('#avatar-editor').hidden=user.role!=='driver';
    if(user.role==='driver'){
      const url=profileData.avatar_url||'/assets/driver.svg';
      $('#profile-photo').src=url;
      $('#header-avatar').innerHTML=`<img src="${escape(url)}" alt="Ảnh đại diện">`;$('#remove-avatar').hidden=!profileData.avatar_url;return;
    }
    const role=user.role;
    const [payments,bank]=await Promise.all([api(role==='admin'?'admin/payments':'payments'),api('payment/settings')]);
    if(user?.id!==id)return;
    this.payments=payments;
    if(role==='admin')for(const key of ['bank_name','bank_bin','account_no','account_name'])if(!document.activeElement.closest('#bank-settings-form'))$('#bank-settings-form [name='+key+']').value=bank[key];
    if(role==='customer'&&this.seen){for(const p of payments){if(this.seen[p.id]&&this.seen[p.id]!==p.status&&['success','failed'].includes(p.status))message(`${paymentLabels[p.status]} · Chuyến #TX${p.trip_id}${p.note?' · '+p.note:''}`,p.status==='failed');}}
    this.seen=Object.fromEntries(payments.map(p=>[p.id,p.status]));this.renderPayments();
  },
  renderPayments(){
    const admin=user.role==='admin';$('#admin-payments').hidden=!admin;
    $('#customer-payments').hidden=admin;
    if(admin){const filter=$('#payment-status-filter').value;$('#payment-admin-list').innerHTML=this.payments.filter(p=>!filter||p.status===filter).map(p=>`<tr><td><b>#TX${p.trip_id}</b><br>${escape(p.customer_name)}</td><td>${money(p.amount)}<br><b>${escape(p.reference)}</b></td><td>${escape(p.bank_name)}<br>${escape(p.account_no)}<br>${escape(p.account_name)}</td><td>${paymentBadge(p)}${p.note?`<p>${escape(p.note)}</p>`:''}</td><td>${p.status==='pending'?`<button data-confirm-payment="${p.id}" data-payment-decision="success">Đã nhận tiền</button><button class="secondary" data-confirm-payment="${p.id}" data-payment-decision="failed">Từ chối</button>`:'Đã lưu trạng thái'}</td></tr>`).join('')||'<tr><td colspan="5">Chưa có chuyển khoản theo bộ lọc.</td></tr>';}
    else $('#customer-payments').innerHTML=this.payments.map(p=>`<article class="feedback-card"><div class="profile-heading"><b>Chuyến #TX${p.trip_id} · ${money(p.amount)}</b>${paymentBadge(p)}</div><p>${escape(p.pickup)} → ${escape(p.destination)}</p><p>Nội dung: <b>${escape(p.reference)}</b></p>${p.note?`<p>${escape(p.note)}</p>`:''}<button class="secondary" data-payment-trip="${p.trip_id}">Xem thanh toán</button></article>`).join('')||'<p>Chưa có yêu cầu chuyển khoản. Chọn phương thức chuyển khoản khi đặt xe hoặc trong chi tiết chuyến.</p>';
  },
  async showPayment(tripId,create=false){
    const result=await api('trips/'+tripId+'/payment',create?'POST':'GET',create?{}:undefined),p=result.payment;
    this.dialogTrip=tripId;
    if(!p){Admin.open('Thanh toán chuyển khoản',`<p>Chưa tạo mã thanh toán cho chuyến #TX${tripId}.</p><button type="button" data-create-payment="${tripId}">Tạo mã QR chuyển khoản</button>`,null);return;}
    let html=`<div class="transfer-card"><div class="section-title"><h3>${escape(p.bank_name)}</h3>${paymentBadge(p)}</div><p>Chuyến #TX${tripId} · <strong>${money(p.amount)}</strong></p>`;
    if(p.status==='awaiting_transfer')html+=`<img class="transfer-qr" src="${escape(p.qr_url)}" alt="Mã VietQR chuyển khoản cho chuyến TX${tripId}"><p id="qr-error" class="error" hidden>Không tải được QR. Bạn có thể nhập thông tin tài khoản bên dưới trong ứng dụng ngân hàng.</p>`;
    html+=`<dl class="transfer-info"><dt>Chủ tài khoản</dt><dd>${escape(p.account_name)}</dd><dt>Số tài khoản</dt><dd>${escape(p.account_no)}</dd><dt>Nội dung chuyển khoản</dt><dd><b>${escape(p.reference)}</b></dd></dl>`;
    if(p.note)html+=`<p class="${p.status==='failed'?'error':'info-banner'}">${escape(p.note)}</p>`;
    if(p.status==='awaiting_transfer')html+=`<p>Kiểm tra người nhận, chuyển đúng số tiền và nội dung trong ứng dụng ngân hàng. Mã VietQR được tạo trực tiếp trong hệ thống.</p><button type="button" class="primary" data-submit-payment="${tripId}" data-payment-id="${p.id}">Tôi đã chuyển khoản</button>`;
    if(p.status==='pending')html+='<p class="info-banner">Đã gửi yêu cầu xác nhận. Admin đang kiểm tra tiền vào tài khoản; chưa được xác nhận thành công.</p>';
    if(p.status==='failed')html+=`<p>Kiểm tra lý do từ chối trước khi chuyển lại. Nếu đã bị trừ tiền, liên hệ admin và cung cấp mã giao dịch.</p><button type="button" data-create-payment="${tripId}">Tạo yêu cầu mới</button>`;
    html+=`<button type="button" class="secondary" data-payment-trip="${tripId}">Kiểm tra trạng thái</button></div>`;
    if(result.history.length>1)html+='<h3>Lịch sử thanh toán</h3>'+result.history.map(h=>`<p>${paymentBadge(h)} · ${new Date(h.created_at).toLocaleString('vi-VN')} ${escape(h.note)}</p>`).join('');
    Admin.open('Thanh toán chuyển khoản',html,null);
    $('.transfer-qr')?.addEventListener('error',()=>{$('#qr-error').hidden=false;$('.transfer-qr').hidden=true;});
  },
  async upload(file){
    if(this.uploading)return;
    if(!file)return;
    if(file.size>2*1024*1024)throw new Error('Ảnh phải nhỏ hơn 2 MB.');
    if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('Chọn ảnh JPG, PNG hoặc WebP.');
    this.uploading=true;document.querySelectorAll('[data-choose-avatar]').forEach(b=>b.disabled=true);
    try{const data=new FormData();data.append('image',file);const r=await fetch('/api/profile/avatar',{method:'PUT',credentials:'same-origin',headers:{'X-CSRF-Token':csrf},body:data});const result=await r.json();if(!r.ok)throw new Error(result.error||'Tải ảnh thất bại');await load();message('Đã cập nhật ảnh đại diện tài xế.');}
    finally{this.uploading=false;$('#avatar-file').value='';document.querySelectorAll('[data-choose-avatar]').forEach(b=>b.disabled=false);}
  }
};
document.addEventListener('click',e=>{
  const photo=e.target.closest('[data-choose-avatar]');if(photo){$('#avatar-file').click();return;}
  const show=e.target.closest('[data-payment-trip]');if(show){run(()=>Extras.showPayment(Number(show.dataset.paymentTrip)));return;}
  const create=e.target.closest('[data-create-payment]');if(create){run(async()=>{create.disabled=true;try{await Extras.showPayment(Number(create.dataset.createPayment),true);await load();}finally{create.disabled=false;}});return;}
  const sent=e.target.closest('[data-submit-payment]');if(sent){run(async()=>{sent.disabled=true;try{await api('trips/'+sent.dataset.submitPayment+'/payment/submit','POST',{payment_id:Number(sent.dataset.paymentId)});await Extras.showPayment(Number(sent.dataset.submitPayment));await load();message('Đã gửi yêu cầu. Chuyển khoản đang chờ admin xác nhận.');}finally{sent.disabled=false;}});return;}
  const review=e.target.closest('[data-confirm-payment]');if(review){const decision=review.dataset.paymentDecision,p=Extras.payments.find(p=>p.id===Number(review.dataset.confirmPayment));Admin.open(decision==='success'?'Xác nhận đã nhận tiền':'Chuyển khoản thất bại',`<p>Chuyến #TX${p.trip_id} · ${money(p.amount)} · ${escape(p.reference)}</p><p>${decision==='success'?'Chỉ xác nhận sau khi kiểm tra sao kê và tiền đã vào đúng tài khoản.':'Nhập lý do để khách kiểm tra giao dịch.'}</p>`+Admin.input(decision==='success'?'Mã giao dịch / ghi chú đối soát':'Lý do từ chối','note','','text','maxlength="500"'),data=>api('admin/payments/'+p.id,'PATCH',{status:decision,note:data.note}));}
});
$('#avatar-file').onchange=e=>run(()=>Extras.upload(e.target.files[0]));
$('#remove-avatar').onclick=()=>run(async()=>{await api('profile/avatar','DELETE');await load();message('Đã xóa ảnh đại diện.');});
$('#bank-settings-form').onsubmit=e=>{e.preventDefault();run(async()=>{await api('payment/settings','PATCH',Object.fromEntries(new FormData(e.target)));await load();message('Đã lưu tài khoản nhận chuyển khoản.');});};
$('#payment-status-filter').onchange=()=>Extras.renderPayments();
$('#refresh-payments').onclick=()=>run(load);
setInterval(()=>{if(user?.role==='customer'&&Extras.dialogTrip&&$('#admin-dialog').open&&$('#dialog-title').textContent==='Thanh toán chuyển khoản')run(async()=>{const result=await api('trips/'+Extras.dialogTrip+'/payment');const p=result.payment;if(p&&['success','failed'].includes(p.status)&&!$('#dialog-fields').textContent.includes(paymentLabels[p.status])){await Extras.showPayment(Extras.dialogTrip);message(paymentLabels[p.status]+(p.note?' · '+p.note:''),p.status==='failed');}});},6000);
