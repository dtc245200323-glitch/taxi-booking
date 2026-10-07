const Landing=window.Landing={
  promotions:[],
  route(update=true){if(user){$('#auth-page').hidden=true;return;}const page=location.hash.slice(1);if(['login','register','forgot','reset'].includes(page)){if(update)authForm(page+'-form',({login:'Đăng nhập',register:'Đăng ký',forgot:'Quên mật khẩu',reset:'Đặt lại mật khẩu'})[page]);else{$('#login-panel').hidden=true;$('#auth-page').hidden=false;}}else{$('#login-panel').hidden=false;$('#auth-page').hidden=true;}},
  showLogin(){authForm('login-form','Đăng nhập');$('#landing-auth-card').scrollIntoView({behavior:'smooth',block:'center'});$('#login-form [name=username]').focus({preventScroll:true});},
  dialog(title,content){$('#landing-dialog-title').textContent=title;$('#landing-dialog-content').innerHTML=content;$('#landing-dialog').showModal();},
  async loadPromotions(){
    try{
      const r=await fetch('/api/public/promotions');if(!r.ok)throw new Error('promotion unavailable');this.promotions=await r.json();
      const p=this.promotions[0];if(!p)return;
      $('#landing-promo-title').textContent=p.kind==='percent'?`Giảm ${Number(p.value)}% cho chuyến đi`:`Giảm ${money(p.value)} cho chuyến đi`;
      $('#landing-promo-code').hidden=false;$('#landing-promo-code').textContent='Mã: '+p.code;
      $('#landing-promo-conditions').textContent=`Tối đa ${money(p.max_discount)} · Chuyến từ ${money(p.min_fare)}`;
    }catch{this.promotions=[];}
  },
  afterLogin(){
    const next=sessionStorage.getItem('landing-next');sessionStorage.removeItem('landing-next');if(next==='history'){navigate(user?.role==='admin'?'trips':'history');return;}if(user?.role!=='customer')return;
    const seats=sessionStorage.getItem('landing-seats'),code=sessionStorage.getItem('landing-promo');
    if(seats){const input=$(`#trip-form [name=seats][value="${seats}"]`);if(input){input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));}}
    if(code){$('#promo-code').value=code;Promotions.invalidate();}
    if(seats||code)navigate('booking');sessionStorage.removeItem('landing-seats');sessionStorage.removeItem('landing-promo');
  }
};
$('#toggle-login-password').onclick=()=>{const input=$('#landing-password'),visible=input.type==='password';input.type=visible?'text':'password';$('#toggle-login-password').setAttribute('aria-pressed',String(visible));$('#toggle-login-password').setAttribute('aria-label',visible?'Ẩn mật khẩu':'Hiện mật khẩu');};
$('#landing-register').onclick=()=>{authForm('register-form','Đăng ký');$('#landing-auth-card').scrollIntoView({behavior:'smooth',block:'center'});};
$('#landing-my-trips').onclick=()=>{sessionStorage.setItem('landing-next','history');Landing.showLogin();message('Đăng nhập để xem chuyến đi của bạn.');};
$('#close-landing-dialog').onclick=()=>$('#landing-dialog').close();
$('#landing-view-promo').onclick=async()=>{
  await Landing.loadPromotions();
  const offers=Landing.promotions;
  Landing.dialog('Ưu đãi dành cho bạn',offers.length?offers.map(p=>`<article class="landing-offer-detail"><h3>${escape(p.title)}</h3><p><b>${escape(p.code)}</b> · ${p.kind==='percent'?Number(p.value)+'%':money(p.value)}</p><p>Giảm tối đa ${money(p.max_discount)}, giá chuyến từ ${money(p.min_fare)}. Mỗi khách ${p.per_customer_limit} lượt, đến ${new Date(p.expires_at).toLocaleDateString('vi-VN')}.</p><button type="button" class="primary" data-landing-use-code="${escape(p.code)}">Đăng nhập để dùng mã</button></article>`).join(''):'<p>Hiện chưa có mã ưu đãi khả dụng. Đăng nhập để đặt chuyến và xem các chương trình mới.</p>');
};
document.addEventListener('click',e=>{
  const home=e.target.closest('[data-landing-home]');if(home){e.preventDefault();history.pushState(null,'','#home');Landing.route();window.scrollTo({top:0,behavior:'smooth'});}
  const use=e.target.closest('[data-landing-use-code]');if(use){sessionStorage.setItem('landing-next','booking');sessionStorage.setItem('landing-promo',use.dataset.landingUseCode);$('#landing-dialog').close();Landing.showLogin();}
  const service=e.target.closest('[data-landing-service]');if(service){const key=service.dataset.landingService;const info={airport:['Đưa đón sân bay','Chọn địa chỉ sân bay làm điểm đón hoặc điểm đến. Xem tuyến đường và giá dự kiến trước khi đặt xe. Chọn xe 4 hoặc 7 chỗ phù hợp số người và hành lý.',4],city:['Di chuyển nội thành','Tìm địa điểm hoặc chọn trên bản đồ, chọn xe máy, xe 4 chỗ hoặc xe 7 chỗ. Theo dõi trạng thái chuyến và vị trí tài xế khi tài xế bật chia sẻ GPS.',4],family:['Xe 7 chỗ','Chọn xe 7 chỗ cho nhóm hoặc gia đình. Giá được tính theo biểu giá xe 7 chỗ và quãng đường; chỉ tài xế có phương tiện phù hợp mới nhận chuyến.',7]}[key];if(info)Landing.dialog(info[0],`<p>${escape(info[1])}</p><button type="button" class="primary" data-landing-select-seats="${info[2]}">Đăng nhập để đặt xe</button>`);}
  const seats=e.target.closest('[data-landing-select-seats]');if(seats){sessionStorage.setItem('landing-next','booking');sessionStorage.setItem('landing-seats',seats.dataset.landingSelectSeats);$('#landing-dialog').close();Landing.showLogin();}
  if(e.target.closest('[data-auth-login]'))Landing.showLogin();if(e.target.closest('[data-auth-register]'))authForm('register-form','Đăng ký');
  const info=e.target.closest('[data-landing-info]');if(info?.dataset.landingInfo==='support'){window.TaxiChat?.open();return;}if(info){const copy={support:['Hỗ trợ','Đăng nhập để xem lịch sử và thông tin chuyến đi. Nếu cần phản ánh về chuyến, mở chi tiết chuyến và chọn Gửi phản ánh. Quên mật khẩu? Sử dụng liên kết khôi phục với email đã lưu trong hồ sơ.'],about:['Giới thiệu Taxi Booking','Taxi Booking kết nối khách hàng, tài xế và người quản trị: đặt xe, theo dõi hành trình và quản lý chuyến đi trên cùng một nền tảng.'],terms:['Thông tin sử dụng','Kiểm tra điểm đón, điểm đến, loại xe và giá trước khi xác nhận. Khách có thể hủy khi chuyến đang chờ tài xế. Chuyển khoản cần được đối soát trước khi xác nhận thanh toán thành công.'],privacy:['Thông tin bảo mật','Hồ sơ và chuyến đi được giới hạn theo tài khoản. Mật khẩu được lưu dưới dạng hash. Vị trí GPS chỉ chia sẻ khi tài xế cho phép; khách chỉ theo dõi tài xế của chuyến đang phục vụ mình. Tìm địa điểm và tính tuyến gửi địa chỉ/tọa độ tới dịch vụ bản đồ.']}[info.dataset.landingInfo];if(copy)Landing.dialog(copy[0],`<p>${escape(copy[1])}</p>`);}
});
Landing.loadPromotions();

window.addEventListener("hashchange",()=>Landing.route());window.addEventListener("popstate",()=>Landing.route());Landing.route();
