(() => {
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let items=[],frame=0,last=0,observer;
  const vertex='attribute vec2 position; varying vec2 uv; void main(){uv=(position+1.0)*0.5;gl_Position=vec4(position,0.0,1.0);}';
  const fragment=`precision mediump float;
    varying vec2 uv; uniform sampler2D picture; uniform float time; uniform vec2 numberCenter;
    float region(vec2 p,vec2 center,vec2 radius){vec2 d=(p-center)/radius;return exp(-dot(d,d)*2.0);}
    void main(){
      vec2 carCenter=vec2(0.74,0.34);vec2 p=uv;
      float car=region(uv,carCenter,vec2(0.25,0.25));
      float number=region(uv,numberCenter,vec2(0.36,0.19));
      float pulse=0.085*(0.5+0.5*sin(time*2.8));
      p-=(uv-numberCenter)*pulse*number;
      p-=vec2(0.002*sin(time*3.1),0.004*sin(time*3.6))*number;
      p-=(uv-carCenter)*(0.018*sin(time*2.4))*car;
      p-=vec2(0.005*sin(time*3.4),0.007*sin(time*4.0))*car;
      gl_FragColor=texture2D(picture,clamp(p,0.0,1.0));
    }`;
  function shader(gl,type,source){const result=gl.createShader(type);gl.shaderSource(result,source);gl.compileShader(result);if(!gl.getShaderParameter(result,gl.COMPILE_STATUS)){gl.deleteShader(result);throw Error('shader');}return result;}
  function clear(){
    cancelAnimationFrame(frame);observer?.disconnect();
    for(const item of items){item.dead=true;item.image.removeEventListener('load',item.ready);item.card.classList.remove('banner-animated');if(item.gl){item.gl.getExtension('WEBGL_lose_context')?.loseContext();}item.canvas?.remove();}
    items=[];
  }
  function mount(){
    clear();if(reduced.matches)return;
    observer=new IntersectionObserver(entries=>{for(const entry of entries){const item=items.find(item=>item.card===entry.target);if(item)item.visible=entry.isIntersecting;}},{threshold:0.1});
    document.querySelectorAll('#booking-ad-gallery .has-custom-image').forEach((card,index)=>{
      const image=card.querySelector('img'),item={card,image,visible:false,dead:false};items.push(item);observer.observe(card);
      item.ready=()=>{
        if(item.dead||item.gl||!image.naturalWidth)return;
        const canvas=document.createElement('canvas');canvas.className='banner-motion-canvas';canvas.setAttribute('aria-hidden','true');
        const gl=canvas.getContext('webgl',{alpha:false,antialias:false});if(!gl)return;
        item.canvas=canvas;item.gl=gl;
        try{
          canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
          const program=gl.createProgram(),vs=shader(gl,gl.VERTEX_SHADER,vertex),fs=shader(gl,gl.FRAGMENT_SHADER,fragment);
          gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);
          if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('program');gl.useProgram(program);
          const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
          const position=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
          const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
          gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image);
          gl.uniform1i(gl.getUniformLocation(program,'picture'),0);gl.uniform2f(gl.getUniformLocation(program,'numberCenter'),index%2?0.50:0.32,index%2?0.67:0.64);
          item.time=gl.getUniformLocation(program,'time');gl.viewport(0,0,canvas.width,canvas.height);gl.uniform1f(item.time,0);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
          card.append(canvas);card.classList.add('banner-animated');
          canvas.addEventListener('webglcontextlost',()=>card.classList.remove('banner-animated'));
        }catch{card.classList.remove('banner-animated');canvas.remove();gl.getExtension('WEBGL_lose_context')?.loseContext();}
      };
      image.addEventListener('load',item.ready);if(image.complete)item.ready();
    });
    function draw(now){
      if(now-last>=32&&!document.hidden&&currentPage==='booking'){
        last=now;for(const item of items){if(item.gl&&item.time&&item.visible&&!item.gl.isContextLost()){item.gl.uniform1f(item.time,now/1000);item.gl.drawArrays(item.gl.TRIANGLE_STRIP,0,4);}}
      }
      frame=requestAnimationFrame(draw);
    }
    frame=requestAnimationFrame(draw);
  }
  window.BannerMotion={mount,clear};reduced.addEventListener('change',mount);
})();
