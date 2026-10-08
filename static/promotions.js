const Promotions=window.Promotions={
 rows:[],saved:[],selected:'',pickingImage:false,uploadingImages:new Set(),
 reset(){window.BannerMotion?.clear();this.pickingImage=false;this.uploadingImages.clear();clearInterval(this.carouselTimer);this.carouselObserver?.disconnect();this.rows=[];this.saved=[];this.selected='';$('#booking-ad-gallery').replaceChildren();},
 image(p){return /^\/api\/promotions\/\d+\/image\?v=[a-f0-9]+$/.test(p.image_url||'')?p.image_url:'/assets/taxi-hero.png';},
 openOffer(id){
   const p=this.rows.find(row=>row.id===id);if(!p)return;
   const saved=this.saved.some(row=>row.id===id);
   Admin.open('Chi tiết ưu đãi',`<article class="promotion-detail"><img src="${this.image(p)}" alt="${escape(p.title)}"><h3>${escape(p.title)}</h3><p class="promotion-detail-code">Mã ưu đãi: <b>${escape(p.code)}</b></p><p>${p.kind==='percent'?'Giảm '+Number(p.value)+'%':'Giảm '+money(p.value)} · Tối đa ${money(p.max_discount)}</p><p>Áp dụng cho chuyến từ ${money(p.min_fare)} · Mỗi khách ${p.per_customer_limit} lượt.</p><p>Hết hạn ${new Date(p.expires_at).toLocaleDateString('vi-VN')}</p><button type="button" class="primary" data-save-promo="${p.id}" ${saved?'disabled':''}>${saved?'Đã lưu mã':'Lưu mã ưu đãi'}</button></article>`,null);
 },
 renderPages(){
   if(user?.role!=='customer')return;
   const detail=p=>`${p.kind==='percent'?Number(p.value)+'%':money(p.value)} · Tối đa ${money(p.max_discount)} · Chuyến từ ${money(p.min_fare)}`;
   this.renderCarousel();
   $('#offer-cards').innerHTML=this.rows.map(p=>`<article class="offer-card" id="offer-${p.id}"><div class="offer-image"><img src="${this.image(p)}" alt="${escape(p.title)}"><span>${escape(p.code)}</span></div><h3>${escape(p.title)}</h3><p>${detail(p)}</p><p>Mỗi khách ${p.per_customer_limit} lượt · Hết hạn ${new Date(p.expires_at).toLocaleDateString('vi-VN')}</p><button type="button" class="primary" data-save-promo="${p.id}" ${this.saved.some(x=>x.id===p.id)?'disabled':''}>${this.saved.some(x=>x.id===p.id)?'Đã lưu':'Lưu mã'}</button></article>`).join('')||empty('Hiện chưa có ưu đãi khả dụng.');
   $('#saved-promo-cards').innerHTML=this.saved.map(p=>{const valid=p.active&&new Date(p.expires_at)>new Date();return `<label class="saved-promo-card"><input type="radio" name="saved-promo-choice" value="${escape(p.code)}" ${this.selected===p.code?'checked':''} ${valid?'':'disabled'}><span><b>${escape(p.code)} · ${escape(p.title)}</b><small>${detail(p)}</small><small>${valid?'Chọn để dùng cho chuyến':'Mã hết hạn hoặc đã tắt'}</small></span></label>`;}).join('')||empty('Bạn chưa lưu mã. Bấm Khám phá và lưu thêm mã.');
 },
 renderCarousel(){
   clearInterval(this.carouselTimer);this.carouselObserver?.disconnect();
   const gallery=$('#booking-ad-gallery');gallery.hidden=!this.rows.length;
   if(!this.rows.length){gallery.replaceChildren();return;}
   const track=document.createElement('div');track.className='promo-track';track.tabIndex=0;track.setAttribute('aria-label','Lướt xem mã giảm giá');
   track.innerHTML=this.rows.map(p=>`<button type="button" class="booking-ad${p.image_url?' has-custom-image':''}" data-offer="${p.id}" aria-label="${escape(p.title)} ? ${escape(p.code)} ? Xem và lưu mã"><img src="${this.image(p)}" alt="${escape(p.title)}">${p.image_url?'':`<span>🎁 Ưu đãi Taxi Booking</span><strong>${escape(p.title)}</strong><b>${escape(p.code)}</b><small>Xem và lưu mã →</small>`}</button>`).join('');
   gallery.replaceChildren(track);const controls=document.createElement('div');controls.className='promo-controls';controls.innerHTML='<button type="button" class="secondary" data-promo-prev aria-label="Ưu đãi trước">‹</button><span class="promo-dots"></span><button type="button" class="secondary" data-promo-next aria-label="Ưu đãi tiếp theo">›</button>';gallery.append(controls);
   const cards=[...track.children];let index=0,direction=1;const reduced=matchMedia('(prefers-reduced-motion: reduce)');
   const stops=()=>{const max=Math.max(0,track.scrollWidth-track.clientWidth);return [...new Set(cards.map(c=>Math.min(c.offsetLeft-cards[0].offsetLeft,max)))];};
   const update=()=>{const points=stops();index=points.reduce((best,x,i)=>Math.abs(x-track.scrollLeft)<Math.abs(points[best]-track.scrollLeft)?i:best,0);controls.hidden=points.length<2;controls.querySelector('.promo-dots').innerHTML=points.map((_,i)=>`<button type="button" data-promo-dot="${i}" aria-label="Xem nhóm ưu đãi ${i+1}" aria-current="${i===index}"></button>`).join('');};
   const go=i=>{const points=stops();index=(i+points.length)%points.length;track.scrollTo({left:points[index],behavior:reduced.matches?'instant':'smooth'});};
   gallery.onclick=e=>{if(e.target.closest('[data-promo-prev]'))go(index-1);if(e.target.closest('[data-promo-next]'))go(index+1);const dot=e.target.closest('[data-promo-dot]');if(dot)go(Number(dot.dataset.promoDot));};
   track.addEventListener('scroll',update,{passive:true});track.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();go(index+(e.key==='ArrowRight'?1:-1));}};
   this.carouselObserver=new ResizeObserver(update);this.carouselObserver.observe(track);
   this.carouselTimer=setInterval(()=>{if(document.hidden||currentPage!=='booking'||gallery.matches(':hover')||gallery.contains(document.activeElement)||reduced.matches)return;const points=stops();if(points.length<2)return;if(index>=points.length-1)direction=-1;if(index<=0)direction=1;go(index+direction);},3000);
   requestAnimationFrame(update);window.BannerMotion?.mount();
 },
  invalidate(){const el=$('#promo-status');if(el)el.textContent=$('#promo-code')?.value?'Bấm Áp dụng để kiểm tra ưu đãi theo tuyến và loại xe hiện tại.':'';},
  async load(){
    if(!user||user.role==='driver')return;
    if(user.role==='admin'&&(this.pickingImage||this.uploadingImages.size))return;
    const id=user.id,rows=await api('promotions');if(user?.id!==id)return;
    this.rows=rows.filter(p=>p.active&&new Date(p.expires_at)>new Date());if(user.role==='customer'){const saved=await api('promotions/saved');if(user?.id!==id)return;this.saved=saved;this.renderPages();}
    if(user.role==='admin'&&!this.pickingImage&&!this.uploadingImages.size)$('#promotion-admin-list').innerHTML=rows.map(p=>`<article class="trip-card"><b>${escape(p.code)} · ${escape(p.title)}</b><p>${p.active?'Đang bật':'Đã tắt'} · Hết hạn ${new Date(p.expires_at).toLocaleDateString('vi-VN')}</p><button type="button" data-toggle-promo="${p.id}" data-active="${!p.active}">${p.active?'Tắt quảng cáo / mã':'Bật quảng cáo / mã'}</button><img class="promotion-admin-preview" src="${this.image(p)}" alt="Ảnh quảng cáo ${escape(p.title)}"><p class="hint" data-image-status role="status">${p.image_url?'Ảnh đã lưu. Chọn tệp khác để thay ảnh.':'Đang dùng ảnh mặc định. Chọn tệp để lưu ảnh quảng cáo.'}</p><div class="promotion-image-picker" data-promo-drop="${p.id}"><p>Ảnh quảng cáo (JPG, PNG, WebP; tối đa 10 MB)</p><button type="button" class="secondary" data-choose-promo-image="${p.id}">Chọn ảnh</button><span>hoặc kéo thả ảnh vào đây</span><input type="file" accept="image/jpeg,image/png,image/webp" data-promo-image="${p.id}" aria-label="Chọn ảnh quảng cáo" hidden></div></article>`).join('');
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
  const offer=e.target.closest('[data-offer]');if(offer){Promotions.openOffer(Number(offer.dataset.offer));}
  const save=e.target.closest('[data-save-promo]');if(save)run(async()=>{save.disabled=true;try{await api('promotions/'+save.dataset.savePromo+'/save','POST',{});await Promotions.load();if(save.isConnected)save.textContent='Đã lưu mã';message('Đã lưu mã. Bạn có thể chọn mã này khi đặt xe.');}finally{if(save.isConnected)save.disabled=Promotions.saved.some(p=>p.id===Number(save.dataset.savePromo));}});
  const use=e.target.closest('[data-use-promo]');if(use){$('#promo-code').value=use.dataset.usePromo;run(()=>Promotions.apply());}
  const toggle=e.target.closest('[data-toggle-promo]');if(toggle)run(async()=>{await api('admin/promotions/'+toggle.dataset.togglePromo,'PATCH',{active:toggle.dataset.active==='true'});await Promotions.load();message('Đã cập nhật mã ưu đãi.');});
  const button=e.target.closest('button');if(button&&!button.disabled&&!matchMedia('(prefers-reduced-motion: reduce)').matches){button.classList.remove('button-click');void button.offsetWidth;button.classList.add('button-click');setTimeout(()=>button.classList.remove('button-click'),350);}
});

$('#choose-promo-page').addEventListener('change',e=>{if(e.target.name==='saved-promo-choice')Promotions.selected=e.target.value;});
$('#confirm-promo-choice').onclick=()=>{const code=$('#choose-promo-page [name="saved-promo-choice"]:checked')?.value;if(!code){message('Chọn một mã đã lưu trước nhé.',true);return;}$('#promo-code').value=code;Promotions.selected=code;estimate();Promotions.invalidate();navigate('booking');message('Đã chọn mã '+code+'. Bấm Áp dụng để kiểm tra theo chuyến hiện tại.');};
$('#clear-promo-choice').onclick=()=>{$('#promo-code').value='';Promotions.selected='';estimate();Promotions.invalidate();navigate('booking');};

document.addEventListener('click',e=>{
  const button=e.target.closest('[data-choose-promo-image]');if(!button)return;
  const input=button.closest('[data-promo-drop]').querySelector('[data-promo-image]');if(input.disabled)return;
  Promotions.pickingImage=true;
  try{if(typeof input.showPicker==='function')input.showPicker();else input.click();}
  catch{try{input.click();}catch{Promotions.pickingImage=false;message('Không mở được cửa sổ chọn ảnh. Bạn có thể kéo thả ảnh vào ô chọn ảnh.',true);}}
});
document.addEventListener('dragover',e=>{const drop=e.target.closest('[data-promo-drop]');if(!drop)return;e.preventDefault();e.dataTransfer.dropEffect='copy';drop.classList.add('dragging');});
document.addEventListener('dragleave',e=>{const drop=e.target.closest('[data-promo-drop]');if(drop&&!drop.contains(e.relatedTarget))drop.classList.remove('dragging');});
document.addEventListener('drop',e=>{
  const drop=e.target.closest('[data-promo-drop]');if(!drop)return;e.preventDefault();drop.classList.remove('dragging');
  const input=drop.querySelector('[data-promo-image]');if(input.disabled||!e.dataTransfer.files.length)return;
  const transfer=new DataTransfer();transfer.items.add(e.dataTransfer.files[0]);input.files=transfer.files;
  input.dispatchEvent(new Event('change',{bubbles:true}));
});
document.addEventListener('cancel',e=>{if(e.target.matches('[data-promo-image]'))Promotions.pickingImage=false;},true);
document.addEventListener('change',async e=>{
  const input=e.target.closest('[data-promo-image]');if(!input)return;
  Promotions.pickingImage=false;const file=input.files[0];if(!file)return;
  const promoId=input.dataset.promoImage,owner=user?.id,status=input.closest('article').querySelector('[data-image-status]');
  Promotions.uploadingImages.add(promoId);input.disabled=true;const choose=input.closest('article').querySelector('[data-choose-promo-image]');choose.disabled=true;status.className='hint';status.textContent='Đang lưu ảnh...';
  try{
    if(file.size>10*1024*1024)throw new Error('Ảnh tối đa 10 MB');
    const data=new FormData();data.append('image',file);
    const response=await fetch('/api/admin/promotions/'+promoId+'/image',{method:'POST',headers:{'X-CSRF-Token':csrf},body:data,signal:AbortSignal.timeout(60000)});
    const result=await response.json().catch(()=>({error:response.status===413?'Ảnh quảng cáo tối đa 10 MB':'Không tải được ảnh. Vui lòng thử lại.'}));if(!response.ok)throw new Error(result.error||'Không lưu được ảnh');
    Promotions.uploadingImages.delete(promoId);
    if(user?.id!==owner)return;
    const card=input.closest('article');
    if(!result.image_url)throw new Error('Máy chủ chưa trả về ảnh đã lưu. Vui lòng thử lại.');
    card.querySelector('.promotion-admin-preview').src=result.image_url;
    status.className='hint';status.textContent='Ảnh đã lưu: '+file.name+'. Chọn ảnh khác để thay thế.';
    message('Đã lưu ảnh quảng cáo. Ảnh vẫn được giữ khi tải lại trang.');
  }catch(error){
    if(user?.id===owner){const detail=error.name==='TimeoutError'?'Tải ảnh quá lâu. Vui lòng thử lại.':error.message;status.textContent=detail;status.className='error';message(detail,true);}
  }finally{Promotions.uploadingImages.delete(promoId);input.disabled=false;choose.disabled=false;input.value='';}
});
