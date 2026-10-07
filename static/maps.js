/* Leaflet map selection, persisted road routes and opt-in driver GPS. */
const TaxiMaps=window.TaxiMaps={
  config:null,customerMap:null,driverMap:null,dialogMap:null,customerLayer:null,driverLayer:null,
  quote:null,version:0,mode:'booking',target:'pickup',trackedTrip:null,driverTrip:null,
  driverRows:[],activeRows:[],watch:null,lastPush:0,pushing:false,ownPosition:null,gpsPromise:null,
  points:{pickup:{lat:21.0067,lng:105.84314,label:'Đại học Bách khoa Hà Nội'},destination:{lat:21.0286,lng:105.852,label:'Hồ Hoàn Kiếm'}},
  async init(){
    if(!user)return;
    if(!this.config)this.config=await api('maps/config');
    this.layout();
  },
  createMap(id){
    const map=L.map(id,{zoomControl:true}).setView([21.0285,105.8542],13);
    L.tileLayer(this.config.tile_url,{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',updateWhenIdle:true,keepBuffer:1}).addTo(map)
      .on('tileerror',()=>{const status=id==='customer-map'?$('#map-route-status'):id==='driver-map'?$('#driver-route-status'):$('#dialog-map-status');if(status)status.textContent='Không tải được nền bản đồ. Kiểm tra kết nối Internet; các điểm và tuyến đã lưu vẫn hiển thị.';});
    return map;
  },
  layout(){
    if(!user||!this.config||typeof L==='undefined')return;
    if(user.role==='customer'&&currentPage==='booking'){
      if(!this.customerMap){this.customerMap=this.createMap('customer-map');this.customerLayer=L.layerGroup().addTo(this.customerMap);this.customerMap.on('click',e=>{if(this.mode!=='booking')return;this.setPoint(this.target,{lat:e.latlng.lat,lng:e.latlng.lng,label:(this.target==='pickup'?'Điểm đón':'Điểm đến')+' ('+e.latlng.lat.toFixed(5)+', '+e.latlng.lng.toFixed(5)+')'});});this.drawBooking();}
      this.customerMap.invalidateSize();
    }
    if(user.role==='driver'&&currentPage==='driver-home'){
      if(!this.driverMap){this.driverMap=this.createMap('driver-map');this.driverLayer=L.layerGroup().addTo(this.driverMap);if(this.driverTrip)run(()=>this.showDriverTrip(this.driverTrip,true));}
      this.driverMap.invalidateSize();
    }
  },
  marker(map,layer,p,label,kind,draggable=false){
    const marker=L.marker([Number(p.lat),Number(p.lng)],{draggable,icon:L.divIcon({className:'taxi-map-marker '+kind,html:kind==='driver'?'🚕':kind==='pickup'?'A':'B',iconSize:[34,34],iconAnchor:[17,34]})}).addTo(layer);
    marker.bindPopup(escape(label));return marker;
  },
  drawBooking(){
    if(!this.customerMap||this.mode!=='booking')return;
    this.customerLayer.clearLayers();
    for(const key of ['pickup','destination']){const p=this.points[key];if(p){const m=this.marker(this.customerMap,this.customerLayer,p,p.label,key,true);m.on('dragend',()=>{const ll=m.getLatLng();this.setPoint(key,{lat:ll.lat,lng:ll.lng,label:(key==='pickup'?'Điểm đón':'Điểm đến')+' ('+ll.lat.toFixed(5)+', '+ll.lng.toFixed(5)+')'});});}}
    if(this.quote)L.geoJSON(this.quote.geometry,{style:{color:'#14364f',weight:5}}).addTo(this.customerLayer);
  },
  setPoint(key,p){
    this.mode='booking';this.trackedTrip=null;this.points[key]={lat:Number(p.lat),lng:Number(p.lng),label:p.label};$('#'+key).value=p.label;
    $('#'+key+'-results').hidden=true;this.invalidateQuote();this.drawBooking();
    $('#customer-map-mode').textContent=(key==='pickup'?'Đã chọn điểm đón. Chọn điểm đến hoặc tính tuyến đường.':'Đã chọn điểm đến. Bấm Tính tuyến đường và giá.');
  },
  invalidateQuote(){this.version++;this.quote=null;$('#map-route-status').textContent='Vị trí đã thay đổi. Bấm Tính tuyến đường để cập nhật giá.';$('#trip-form [name=distance]').value='';$('#estimate').textContent='Chưa tính tuyến';},
  addressEdited(key){
    if(key){this.points[key]=null;$('#'+key+'-results').hidden=true;}else for(const k of ['pickup','destination'])if(this.points[k]?.label!==$('#'+k).value)this.points[k]=null;
    this.mode='booking';this.trackedTrip=null;this.invalidateQuote();this.drawBooking();
  },
  async search(key){
    const input=$('#'+key),query=input.value.trim();if(query.length<3)throw new Error('Nhập ít nhất 3 ký tự để tìm địa điểm.');
    const container=$('#'+key+'-results');container.hidden=false;container.textContent='Đang tìm địa điểm…';
    const id=user.id,old=query;
    try{const result=await api('maps/search','POST',{query,near:this.customerMap?{lat:this.customerMap.getCenter().lat,lng:this.customerMap.getCenter().lng}:{lat:21.0285,lng:105.8542}});
      if(user?.id!==id||input.value.trim()!==old)return;
      container.replaceChildren();for(const place of result.places){const b=document.createElement('button');b.type='button';b.className='place-result';b.textContent=place.label;b.onclick=()=>{this.setPoint(key,place);this.customerMap?.setView([place.lat,place.lng],16);};container.append(b);}if(!result.places.length)container.textContent='Không tìm thấy. Thử tên đường, thành phố hoặc chọn trực tiếp trên bản đồ.';
    }catch(error){container.textContent=error.message;throw error;}
  },
  async calculate(){
    if(!this.points.pickup||!this.points.destination)throw new Error('Tìm và chọn kết quả cho cả hai địa chỉ, hoặc chọn điểm trực tiếp trên bản đồ.');
    const version=this.version,id=user.id;
    const b=$('#calculate-route');b.disabled=true;$('#map-route-status').textContent='Đang tính tuyến đường ô tô…';
    try{const result=await api('maps/route','POST',{pickup:this.points.pickup,destination:this.points.destination});
      if(user?.id!==id||this.version!==version)throw new Error('Vị trí vừa thay đổi. Tính lại tuyến đường.');
      this.quote={...result,expiresAt:Date.now()+result.expires_in_seconds*1000};this.mode='booking';this.trackedTrip=null;$('#trip-form [name=distance]').value=result.distance_km;estimate();this.drawBooking();
      if(this.customerMap)this.customerMap.fitBounds(L.geoJSON(result.geometry).getBounds(),{padding:[30,30]});
      $('#map-route-status').textContent=`${result.distance_km} km đường ô tô · khoảng ${Math.max(1,Math.round(result.duration_seconds/60))} phút (không tính giao thông trực tiếp).`;
      return result;
    }catch(error){$('#map-route-status').textContent=error.message;throw error;}finally{b.disabled=false;}
  },
  async prepareBooking(){
    for(const key of ['pickup','destination'])if(this.points[key]?.label!==$('#'+key).value)this.points[key]=null;
    if(!this.quote||this.quote.expiresAt<Date.now())await this.calculate();
    return {route_quote_id:this.quote.quote_id,distance:this.quote.distance_km};
  },
  booked(){this.quote=null;this.version++;},
  drawTrip(map,layer,t,fit=false){
    layer.clearLayers();const points=[];
    if(t.pickup_lat!=null&&t.destination_lat!=null){
      const p={lat:t.pickup_lat,lng:t.pickup_lng},d={lat:t.destination_lat,lng:t.destination_lng};
      this.marker(map,layer,p,t.pickup,'pickup');this.marker(map,layer,d,t.destination,'destination');points.push([p.lat,p.lng],[d.lat,d.lng]);
      if(t.route_geometry)L.geoJSON(t.route_geometry,{style:{color:'#15374f',weight:5}}).addTo(layer);
    }
    if(t.driver_location){const gps=t.driver_location;this.marker(map,layer,gps,'Vị trí tài xế cập nhật '+new Date(gps.updated_at).toLocaleTimeString('vi-VN'),'driver');L.circle([gps.lat,gps.lng],{radius:Number(gps.accuracy),color:'#168a51',weight:1,fillOpacity:.12}).addTo(layer);points.push([gps.lat,gps.lng]);}
    if(fit&&points.length){const bounds=L.latLngBounds(points);if(t.route_geometry)bounds.extend(L.geoJSON(t.route_geometry).getBounds());map.fitBounds(bounds,{padding:[40,40],maxZoom:16});}
  },
  async viewTrip(id){
    if($('#admin-dialog').open)$('#admin-dialog').close();
    if(user.role==='customer'){
      this.trackedTrip=id;this.mode='tracking';navigate('booking');await this.init();const t=await api('trips/'+id+'/map');
      this.drawTrip(this.customerMap,this.customerLayer,t,true);$('#customer-map-mode').textContent='Đang theo dõi chuyến #TX'+id;
      $('#map-route-status').textContent=t.location_source==='map'?`${t.distance} km · ${t.driver_location?'Có vị trí GPS mới của tài xế':'Tài xế chưa chia sẻ GPS hoặc vị trí đã quá 2 phút.'}`:'Chuyến cũ chưa lưu tọa độ. Xem địa chỉ trong chi tiết chuyến.';
      $('#customer-map').scrollIntoView({behavior:'smooth',block:'center'});
    }else if(user.role==='driver'){this.driverTrip=id;navigate('driver-home');await this.init();$('#driver-map-trip').value=id;await this.showDriverTrip(id,true);$('#driver-map').scrollIntoView({behavior:'smooth',block:'center'});}
    else{await this.init();const t=await api('trips/'+id+'/map');Admin.open('Bản đồ chuyến #TX'+id,'<div id="dialog-trip-map" class="real-map"></div><p id="dialog-map-status"></p>',null);this.dialogMap=this.createMap('dialog-trip-map');this.drawTrip(this.dialogMap,L.layerGroup().addTo(this.dialogMap),t,true);$('#dialog-map-status').textContent=t.location_source==='map'?t.pickup+' → '+t.destination:'Chuyến chưa có tọa độ được lưu.';}
  },
  async customerTrips(active){
    if(this.trackedTrip&&active.some(t=>t.id===this.trackedTrip)&&this.customerMap&&currentPage==='booking'){
      const id=this.trackedTrip,t=await api('trips/'+id+'/map');if(this.trackedTrip===id){this.drawTrip(this.customerMap,this.customerLayer,t);$('#map-route-status').textContent=t.driver_location?'GPS tài xế: '+new Date(t.driver_location.updated_at).toLocaleTimeString('vi-VN')+' · Sai số khoảng '+Math.round(t.driver_location.accuracy)+' m':'Chưa có vị trí GPS mới của tài xế.';}
    }else if(this.trackedTrip&&!active.some(t=>t.id===this.trackedTrip)){
      // Remove the driver's live marker as soon as the trip ends.
      if(this.customerMap){const t=await api('trips/'+this.trackedTrip+'/map');this.drawTrip(this.customerMap,this.customerLayer,t);$('#map-route-status').textContent='Chuyến đã kết thúc; ngừng hiển thị GPS tài xế.';}
    }
  },
  async driverTrips(active,queue){
    this.activeRows=active;this.driverRows=[...active,...queue];
    const old=this.driverTrip;
    if(active.length)this.driverTrip=active[0].id;else if(!this.driverRows.some(t=>t.id===this.driverTrip))this.driverTrip=this.driverRows[0]?.id||null;
    $('#driver-map-trip').innerHTML='<option value="">Chọn chuyến để xem bản đồ</option>'+this.driverRows.map(t=>`<option value="${t.id}">#TX${t.id} · ${escape(t.pickup)} → ${escape(t.destination)}</option>`).join('');$('#driver-map-trip').value=this.driverTrip||'';
    if(profileData?.status==='offline'&&this.watch!==null)await this.stopGps();
    if(this.driverMap&&currentPage==='driver-home'){if(this.driverTrip)await this.showDriverTrip(this.driverTrip,old!==this.driverTrip);else{this.driverLayer.clearLayers();$('#driver-route-status').textContent='Chưa có chuyến để hiển thị.';}}
  },
  async showDriverTrip(id,fit=false){
    if(!id||!this.driverMap)return;const t=await api('trips/'+id+'/map');if(this.driverTrip!==Number(id))return;
    this.drawTrip(this.driverMap,this.driverLayer,t,fit);
    if(this.ownPosition&&!t.driver_location&&Date.now()-this.lastPush<120000)this.marker(this.driverMap,this.driverLayer,this.ownPosition,'GPS của bạn','driver');
    $('#driver-route-status').textContent=t.location_source==='map'?`${t.pickup} → ${t.destination} · ${t.distance} km · khoảng ${Math.max(1,Math.round(t.route_duration_seconds/60))} phút`:'Chuyến này chưa có tọa độ. Xem địa chỉ trong danh sách chuyến.';
  },
  async locateCustomer(){
    if(!navigator.geolocation)throw new Error('Trình duyệt không hỗ trợ định vị. Chọn điểm trên bản đồ.');
    const pos=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,e=>reject(new Error(e.code===1?'Bạn chưa cho phép truy cập vị trí. Chọn điểm trên bản đồ hoặc cho phép GPS.':'Không lấy được GPS. Kiểm tra vị trí trên thiết bị và thử lại.')),{enableHighAccuracy:true,timeout:15000,maximumAge:30000}));
    if(user?.role!=='customer')return;this.setPoint('pickup',{lat:pos.coords.latitude,lng:pos.coords.longitude,label:'Vị trí hiện tại ('+pos.coords.latitude.toFixed(5)+', '+pos.coords.longitude.toFixed(5)+')'});this.customerMap?.setView([pos.coords.latitude,pos.coords.longitude],16);
  },
  startGps(){
    if(this.watch!==null)return;
    if(!navigator.geolocation)throw new Error('Trình duyệt không hỗ trợ GPS.');
    if(profileData.status==='offline')throw new Error('Bật trạng thái nhận chuyến trước khi chia sẻ GPS.');
    $('#driver-gps-status').textContent='Đang xin quyền định vị…';$('#share-driver-gps').hidden=true;$('#stop-driver-gps').hidden=false;
    this.watch=navigator.geolocation.watchPosition(pos=>{
      if(user?.role!=='driver')return;this.ownPosition={lat:pos.coords.latitude,lng:pos.coords.longitude,accuracy:pos.coords.accuracy};
      if(this.pushing||Date.now()-this.lastPush<10000)return;this.pushing=true;this.lastPush=Date.now();
      this.gpsPromise=run(async()=>{try{await api('driver/location','PUT',this.ownPosition);if(this.watch===null||user?.role!=='driver')return;$('#driver-gps-status').textContent='Đang chia sẻ GPS · '+new Date().toLocaleTimeString('vi-VN')+' · Sai số khoảng '+Math.round(pos.coords.accuracy)+' m';if(this.driverTrip)await this.showDriverTrip(this.driverTrip);else if(this.driverMap){this.driverLayer.clearLayers();this.marker(this.driverMap,this.driverLayer,this.ownPosition,'Vị trí của bạn','driver');this.driverMap.setView([pos.coords.latitude,pos.coords.longitude],16);}}
        finally{this.pushing=false;}});
    },error=>run(async()=>{await this.stopGps();throw new Error(error.code===1?'Chưa được cấp quyền GPS. Cho phép vị trí trong trình duyệt để chia sẻ.':'Không lấy được GPS. Kiểm tra thiết bị và bật lại chia sẻ.');}),{enableHighAccuracy:true,timeout:15000,maximumAge:10000});
  },
  async stopGps(){
    if(this.watch!==null)navigator.geolocation.clearWatch(this.watch);this.watch=null;this.ownPosition=null;this.lastPush=0;
    if(this.gpsPromise)await this.gpsPromise;
    if(user?.role==='driver')await api('driver/location','DELETE');
    $('#share-driver-gps').hidden=false;$('#stop-driver-gps').hidden=true;$('#driver-gps-status').textContent='Đã dừng chia sẻ GPS.';
    if(this.driverMap&&this.driverTrip)await this.showDriverTrip(this.driverTrip);
  },
  reset(){
    if(this.watch!==null)navigator.geolocation?.clearWatch(this.watch);this.watch=null;this.ownPosition=null;this.lastPush=0;this.trackedTrip=null;this.driverTrip=null;this.driverRows=[];this.activeRows=[];this.quote=null;this.version++;this.mode='booking';
    for(const key of ['customerMap','driverMap','dialogMap']){this[key]?.remove();this[key]=null;}
    this.points={pickup:{lat:21.0067,lng:105.84314,label:'Đại học Bách khoa Hà Nội'},destination:{lat:21.0286,lng:105.852,label:'Hồ Hoàn Kiếm'}};
    for(const key of ['pickup','destination']){$('#'+key).value=this.points[key].label;$('#'+key+'-results').replaceChildren();$('#'+key+'-results').hidden=true;}
    $('#trip-form [name=distance]').value='';$('#estimate').textContent='Chưa tính tuyến';$('#map-route-status').textContent='Chọn hai điểm rồi tính tuyến đường.';
    $('#share-driver-gps').hidden=false;$('#stop-driver-gps').hidden=true;$('#driver-gps-status').textContent='Chưa chia sẻ vị trí.';
  }
};
document.addEventListener('click',e=>{
  const search=e.target.closest('[data-search-location]');if(search){run(()=>TaxiMaps.search(search.dataset.searchLocation));return;}
  const select=e.target.closest('[data-map-select]');if(select){TaxiMaps.target=select.dataset.mapSelect;TaxiMaps.mode='booking';TaxiMaps.trackedTrip=null;TaxiMaps.drawBooking();$('#customer-map-mode').textContent='Bấm trên bản đồ để chọn '+(TaxiMaps.target==='pickup'?'điểm đón':'điểm đến')+'.';return;}
  const view=e.target.closest('[data-view-trip-map]');if(view)run(()=>TaxiMaps.viewTrip(Number(view.dataset.viewTripMap)));
});
for(const key of ['pickup','destination'])$('#'+key).addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();run(()=>TaxiMaps.search(key));}});
$('#calculate-route').onclick=()=>run(()=>TaxiMaps.calculate());
$('#locate-customer').onclick=()=>run(()=>TaxiMaps.locateCustomer());
$('#reset-booking-map').onclick=()=>{TaxiMaps.mode='booking';TaxiMaps.trackedTrip=null;TaxiMaps.drawBooking();$('#customer-map-mode').textContent='Chọn điểm đón hoặc điểm đến trên bản đồ.';};
$('#driver-map-trip').onchange=e=>{TaxiMaps.driverTrip=Number(e.target.value)||null;run(()=>TaxiMaps.showDriverTrip(TaxiMaps.driverTrip,true));};
$('#share-driver-gps').onclick=()=>run(()=>TaxiMaps.startGps());$('#stop-driver-gps').onclick=()=>run(()=>TaxiMaps.stopGps());
$('#admin-dialog').addEventListener('close',()=>{TaxiMaps.dialogMap?.remove();TaxiMaps.dialogMap=null;});
window.addEventListener('pagehide',()=>{if(TaxiMaps.watch!==null&&user?.role==='driver'){navigator.geolocation.clearWatch(TaxiMaps.watch);fetch('/api/driver/location',{method:'DELETE',credentials:'same-origin',keepalive:true,headers:{'X-CSRF-Token':csrf}}).catch(()=>{});}});
