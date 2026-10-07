const Promotions=window.Promotions={
  invalidate(){const el=$('#promo-status');if(el)el.textContent=$('#promo-code')?.value?'Bấm Áp dụng để kiểm tra ưu đãi theo tuyến và loại xe hiện tại.':'';},
  async load(){
    if(!user||user.role==='driver')return;
    const id=user.id,rows=await api('promotions');if(user?.id!==id)return;
    const banner=$('#promotion-banner');banner.hidden=user.role!=='customer'||!rows.length;
    banner.innerHTML=rows.map(p=>`<article><span>🎁 Ưu đãi chuyến đi</span><h3>${escape(p.title)}</h3><p>${p.kind==='percent'?Number(p.value)+'%':money(p.value)} · Tối đa ${money(p.max_discount)} · Chuyến từ ${money(p.min_fare)}</p><p>Mỗi khách ${p.per_customer_limit} lượt · Đến ${new Date(p.expires_at).toLocaleDateString('vi-VN')}</p><button type="button" class="secondary" data-use-promo="${escape(p.code)}">Dùng mã ${escape(p.code)}</button></article>`).join('');
    if(user.role==='admin')$('#promotion-admin-list').innerHTML=rows.map(p=>`<article class="trip-card"><b>${escape(p.code)} · ${escape(p.title)}</b><p>${p.active?'Đang bật':'Đã tắt'} · Hết hạn ${new Date(p.expires_at).toLocaleDateString('vi-VN')}</p><button type="button" data-toggle-promo="${p.id}" data-active="${!p.active}">${p.active?'Tắt quảng cáo / mã':'Bật quảng cáo / mã'}</button></article>`).join('');
  },
  async apply(){
    const code=$('#promo-code').value.trim().toUpperCase();if(!code)throw new Error('Nhập mã giảm giá trước.');
    const quote=await TaxiMaps.prepareBooking();
    const result=await api('promotions/preview','POST',{code,route_quote_id:quote.route_quote_id,seats:Number($('[name="seats"]:checked').value)});
    $('#promo-code').value=result.code;$('#promo-status').textContent=`Giảm ${money(result.discount)} · Giá gốc ${money(result.subtotal)} · Còn ${money(result.total)}. Mã được kiểm tra lại khi đặt chuyến.`;
    $('#estimate').textContent=money(result.total);
  }
};
$('#apply-promo').onclick=()=>run(()=>Promotions.apply());
$('#promo-code').oninput=()=>{estimate();};
$('#promotion-form').onsubmit=e=>{e.preventDefault();run(async()=>{await api('admin/promotions','POST',Object.fromEntries(new FormData(e.target)));e.target.reset();await Promotions.load();message('Đã tạo mã và quảng cáo cho khách.');});};
document.addEventListener('click',e=>{
  const use=e.target.closest('[data-use-promo]');if(use){$('#promo-code').value=use.dataset.usePromo;run(()=>Promotions.apply());}
  const toggle=e.target.closest('[data-toggle-promo]');if(toggle)run(async()=>{await api('admin/promotions/'+toggle.dataset.togglePromo,'PATCH',{active:toggle.dataset.active==='true'});await Promotions.load();message('Đã cập nhật mã ưu đãi.');});
  const button=e.target.closest('button');if(button&&!button.disabled&&!matchMedia('(prefers-reduced-motion: reduce)').matches){button.classList.remove('button-click');void button.offsetWidth;button.classList.add('button-click');setTimeout(()=>button.classList.remove('button-click'),350);}
});
