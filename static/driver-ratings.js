const DriverRatings=window.DriverRatings={
  rows:[],seen:null,
  reset(){this.rows=[];this.seen=null;$('#driver-rating-list').replaceChildren();$('#driver-rating-section').hidden=true;},
  async load(){
    if(user?.role!=='customer')return;
    const owner=user.id,rows=await api('trips/reviewable');if(user?.id!==owner)return;
    const fresh=this.seen?rows.find(row=>!row.stars&&!this.seen.has(row.id)):null;
    this.rows=rows;this.seen=new Set(rows.map(row=>row.id));
    $('#driver-rating-section').hidden=!rows.length;
    $('#driver-rating-list').innerHTML=rows.map(row=>`<article class="feedback-card"><b>Chuyến #TX${row.id} · Tài xế ${escape(row.driver_name)}</b><p>${escape(row.pickup)} → ${escape(row.destination)}</p>${row.stars?`<p class="stars">${'★'.repeat(row.stars)}${'☆'.repeat(5-row.stars)} · Đã đánh giá</p>`:`<button type="button" data-rate-driver="${row.id}">★ Đánh giá tài xế</button>`}</article>`).join('');
    if(fresh&&!$('#admin-dialog').open)await this.open(fresh.id);
  },
  async open(id){
    if(user?.role!=='customer')return;
    const trip=await api('trips/'+id);
    if(trip.review){message('Bạn đã đánh giá chuyến này.');return;}
    Admin.open('Đánh giá tài xế',`<p><b>${escape(trip.driver_name||'Tài xế')} · Chuyến #TX${id}</b></p><p>Trải nghiệm chuyến đi của bạn thế nào?</p><input type="hidden" name="stars" value=""><div class="driver-rating-stars" role="group" aria-label="Chọn từ 1 đến 5 sao">${[1,2,3,4,5].map(n=>`<button type="button" data-driver-star="${n}" aria-label="${n} sao" aria-pressed="false">★</button>`).join('')}</div><p id="driver-rating-label" class="hint">Chọn số sao để đánh giá</p><label>Nhận xét (không bắt buộc)<textarea name="comment" maxlength="1000" rows="3"></textarea></label>`,async data=>{
      if(!Number(data.stars))throw new Error('Chọn từ 1 đến 5 sao trước khi gửi.');
      await api('trips/'+id+'/review','POST',{stars:Number(data.stars),comment:data.comment});
    },'Gửi đánh giá');
    $('#dialog-submit').disabled=true;
  }
};
const driverRatingSection=document.createElement('section');driverRatingSection.id='driver-rating-section';driverRatingSection.className='panel';driverRatingSection.dataset.page='booking payments history';driverRatingSection.hidden=true;driverRatingSection.innerHTML='<h2>Đánh giá tài xế sau chuyến đi</h2><div id="driver-rating-list"></div>';$('#workspace').append(driverRatingSection);
document.addEventListener('click',event=>{
  const review=event.target.closest('[data-rate-driver]');if(review)run(()=>DriverRatings.open(Number(review.dataset.rateDriver)));
  const star=event.target.closest('[data-driver-star]');if(!star)return;
  const n=Number(star.dataset.driverStar);$('#admin-dialog-form [name=stars]').value=n;
  document.querySelectorAll('[data-driver-star]').forEach(button=>{button.classList.toggle('chosen',Number(button.dataset.driverStar)<=n);button.setAttribute('aria-pressed',Number(button.dataset.driverStar)===n);});
  $('#driver-rating-label').textContent=['','Không hài lòng','Chưa tốt','Bình thường','Tốt','Rất tốt'][n];$('#dialog-submit').disabled=false;
});
