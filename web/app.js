const $ = id => document.getElementById(id);
let source = "ip", connected = false, media = null, active = false, busy = false;
let generation = 0, streamTimer = null, status = null, lastResult = null;
let cameraGeneration = 0;
let streamWanted = false;
let takingPhoto = false;
const say = (text, error=false) => { $("message").textContent = text; $("message").classList.toggle("error", error); };
async function api(path, body, raw=false) {
  const response = await fetch(path, {method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : {"Content-Type": raw ? "image/jpeg" : "application/json"},
    body: body === undefined ? undefined : raw ? body : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Yêu cầu thất bại.");
  return data;
}
function ready() { return status?.models.dino && ($("mode").value === "manual" || status?.models.ram); }
function controls() {
  $("snapshot").disabled = !connected || !ready() || busy;
  $("snapshot").textContent = takingPhoto ? "Đang nhận diện ảnh…" : "Chụp & nhận diện";
  $("ai").disabled = !connected || !ready() || (busy && !active);
  $("ai").textContent = active ? "Dừng nhận diện" : "Bật nhận diện liên tục";
  $("disconnect").disabled = !connected && $("cameraState").textContent !== "Đang kết nối";
  $("sample").disabled = busy || active || !ready();
}
function clearResult() {
  clearWordSelection(); resultPhoto=null;labelTargets=[];
  $("result").hidden = true; $("emptyResult").hidden = false;
  $("detections").replaceChildren(); $("tags").textContent = "";
  $("count").textContent = "00"; $("save").disabled = true;
  $("latency").textContent = "Chưa có kết quả"; lastResult = null;
}
function stopAI() { active = false; generation++; $("aiState").textContent = busy ? "Đang hoàn tất lượt xử lý" : "Đã dừng"; controls(); }
async function disconnect() {
  cameraGeneration++; stopAI(); stopStream();
  if (media) media.getTracks().forEach(track => track.stop());
  media = null; $("video").srcObject = null;
  connected = false; $("video").hidden = true; $("ipStream").hidden = true; $("emptyLive").hidden = false;
  $("liveDot").classList.remove("live"); $("cameraState").textContent = "Chưa kết nối";
  $("resolution").textContent = "— × —"; $("cameraFps").textContent = ""; clearResult(); controls();
  try { await api("/api/camera/disconnect", {}); } catch {}
}
function showFrame(width,height) {
  connected = true; $("emptyLive").hidden = true; $("liveDot").classList.add("live");
  $("cameraState").textContent = "Đang phát"; $("resolution").textContent = width + " × " + height;
  controls();
}
function stopStream() {
  streamWanted = false; clearTimeout(streamTimer);
  const image = $("ipStream"); image.onload = image.onerror = null;
  image.removeAttribute("src"); image.hidden = true;
}
function startStream(token) {
  if (token !== cameraGeneration || source !== "ip") return;
  streamWanted = true;
  const image = $("ipStream");
  image.onload = () => {
    if (token !== cameraGeneration || !streamWanted) return;
    clearTimeout(streamTimer);
    image.hidden = false; showFrame(image.naturalWidth, image.naturalHeight);
  };
  image.onerror = () => {
    if (token !== cameraGeneration || !streamWanted) return;
    connected = false; stopAI(); image.hidden = true;
    $("liveDot").classList.remove("live"); $("emptyLive").hidden = false;
    $("cameraState").textContent = "Mất tín hiệu"; $("cameraFps").textContent = "";
    clearTimeout(streamTimer);
    streamTimer = setTimeout(() => startStream(token), 500);
  };
  // The browser decodes/displays MJPEG directly, independently of AI and JS drawing.
  image.src = "/api/stream?session=" + token + "&t=" + Date.now();
}
$("connectForm").addEventListener("submit", async event => {
  event.preventDefault();
  $("connect").disabled = true;
  try {
    await disconnect(); const token = ++cameraGeneration;
    $("cameraState").textContent = "Đang kết nối"; controls();
    if (source === "ip") {
      await api("/api/camera/connect", {ip:$("ip").value.trim(), port:Number($("port").value)});
      say("Đang kết nối DroidCam… Giữ app mở trên điện thoại.");
      if (token === cameraGeneration) startStream(token);
    } else {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Mở giao diện bằng Chrome hoặc Edge tại localhost để dùng webcam.");
      const videoOptions = {frameRate:{ideal:30}};
      if ($("devices").value) videoOptions.deviceId = {exact:$("devices").value};
      media = await navigator.mediaDevices.getUserMedia({video:videoOptions, audio:false});
      const video = $("video"); video.srcObject = media; await video.play(); video.hidden = false;
      showFrame(video.videoWidth, video.videoHeight);
      const frameRate = media.getVideoTracks()[0].getSettings().frameRate;
      $("cameraFps").textContent = frameRate ? Math.round(frameRate) + " FPS · webcam" : "";
      const devices = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "videoinput");
      const selected = media.getVideoTracks()[0].getSettings().deviceId;
      $("devices").replaceChildren(...devices.map(d => new Option(d.label || "Camera",d.deviceId,false,d.deviceId===selected)));
      media.getVideoTracks()[0].addEventListener("ended", () => { disconnect(); say("Camera đã ngắt kết nối.",true); });
      say("Camera đã kết nối. Bạn có thể bật AI khi model sẵn sàng.");
    }
  } catch (error) {
    await disconnect();
    say(error.name === "NotAllowedError" ? "Chưa được cấp quyền camera. Cho phép camera trong trình duyệt rồi thử lại." : error.message,true);
  } finally { $("connect").disabled = false; controls(); }
});
$("disconnect").onclick = async () => { await disconnect(); say("Đã ngắt camera."); };
async function setSource(next) {
  await disconnect(); source = next;
  $("ipTab").classList.toggle("selected", next==="ip"); $("usbTab").classList.toggle("selected", next==="usb");
  $("ipFields").hidden = next!=="ip"; $("usbFields").hidden = next==="ip";
  $("ip").required = next==="ip"; $("port").required = next==="ip";
  say(next==="ip" ? "Nhập IP và cổng hiện tại trên DroidCam." : "Chọn camera và bấm Kết nối. Trình duyệt sẽ hỏi quyền camera.");
}
$("ipTab").onclick=()=>setSource("ip"); $("usbTab").onclick=()=>setSource("usb");
$("mode").onchange=()=>{stopAI();$("labelFields").hidden=$("mode").value==="auto";controls();};
$("threshold").oninput=()=>{$("thresholdValue").textContent=$("threshold").value+"%";};
function capture() {
  const input = source==="ip" ? $("ipStream") : $("video");
  const width = input.videoWidth || input.naturalWidth || input.width;
  const height = input.videoHeight || input.naturalHeight || input.height;
  if (!width || !height) throw new Error("Chưa có khung hình camera.");
  const scale = Math.min(1, 800 / Math.max(width,height));
  const canvas = document.createElement("canvas"); canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
  canvas.getContext("2d").drawImage(input,0,0,canvas.width,canvas.height);
  return canvas;
}
let resultPhoto = null, selectedDetection = null, labelTargets = [];
let lookupSequence = 0, lookupAbort = null, pronunciation = null;
const dictionaryCache = new Map();
function clearWordSelection() {
  lookupSequence++;
  if(lookupAbort)lookupAbort.abort();
  lookupAbort=null;
  if(pronunciation)pronunciation.pause();
  pronunciation=null;
  if(window.speechSynthesis)window.speechSynthesis.cancel();
  selectedDetection=null;
  $("wordPanel").hidden=true;$("showAll").hidden=true;
  $("wordConfidence").textContent="";
}
function redrawBoxes() {
  if(!resultPhoto||!lastResult)return;
  const output=$("result"),ctx=output.getContext("2d");
  ctx.clearRect(0,0,output.width,output.height);ctx.drawImage(resultPhoto,0,0);
  const sx=output.width/lastResult.size[0],sy=output.height/lastResult.size[1];
  ctx.font="14px Segoe UI";ctx.lineWidth=2;labelTargets=[];
  lastResult.detections.forEach((d,index)=>{
    if(selectedDetection!==null&&selectedDetection!==index)return;
    let [x,y,x2,y2]=d.box;x*=sx;x2*=sx;y*=sy;y2*=sy;
    ctx.strokeStyle="#c4ef83";ctx.strokeRect(x,y,x2-x,y2-y);
    const text=d.label+" "+Math.round(d.score*100)+"%",w=ctx.measureText(text).width+12;
    const left=Math.max(0,Math.min(x,output.width-w)),top=Math.max(0,y-23);
    ctx.fillStyle="#c4ef83";ctx.fillRect(left,top,w,23);ctx.fillStyle="#16200f";ctx.fillText(text,left+6,top+16);
    labelTargets.push({index,label:[left,top,left+w,top+23],box:[x,y,x2,y2]});
  });
  $("detections").querySelectorAll("button").forEach((button,index)=>{
    const selected=index===selectedDetection;
    button.classList.toggle("selected",selected);button.setAttribute("aria-pressed",String(selected));
  });
  $("showAll").hidden=selectedDetection===null;
}
function render(canvas,data) {
  clearWordSelection();
  resultPhoto=document.createElement("canvas");resultPhoto.width=canvas.width;resultPhoto.height=canvas.height;
  resultPhoto.getContext("2d").drawImage(canvas,0,0);
  lastResult=data;
  const output=$("result");output.width=canvas.width;output.height=canvas.height;
  output.hidden=false;$("emptyResult").hidden=true;
  $("count").textContent=String(data.detections.length).padStart(2,"0");
  $("latency").textContent=data.seconds+" giây / ảnh · "+data.device.toUpperCase();
  $("resultTime").textContent=new Date().toLocaleTimeString("vi-VN")+" · ẢNH ĐÃ PHÂN TÍCH";
  $("detections").replaceChildren();
  data.detections.forEach((d,index)=>{
    const card=document.createElement("button");card.type="button";card.className="detection";card.textContent=d.label;
    card.setAttribute("aria-label","Chọn "+d.label+" và nghe phát âm");card.setAttribute("aria-pressed","false");
    const score=document.createElement("small");score.textContent=Math.round(d.score*100)+"%";
    card.append(score);card.onclick=()=>selectDetection(index);$("detections").append(card);
  });
  if(!data.detections.length){const p=document.createElement("p");p.className="muted";p.textContent="Chưa tìm thấy vật thể phù hợp. Thử đổi nhãn hoặc giảm ngưỡng.";$("detections").append(p);}
  $("tags").textContent=data.tags.length?"Bấm vào nhãn trên ảnh hoặc từ bên dưới để tra từ và nghe phát âm.":"";
  $("save").disabled=false;redrawBoxes();
}
function dictionaryAudio(entries) {
  for(const entry of entries)for(const phonetic of entry.phonetics||[]){
    if(!phonetic.audio)continue;
    try{
      const url=new URL(phonetic.audio, "https://api.dictionaryapi.dev/");
      if(url.protocol==="https:")return url.href;
    }catch{}
  }
  return "";
}
function displayDictionary(entries) {
  const entry=entries.find(item=>item.phonetic)||(entries[0]||{});
  $("wordPhonetic").textContent=entry.phonetic||(entry.phonetics||[]).find(p=>p.text)?.text||"";
  $("wordDefinitions").replaceChildren();
  let count=0;
  for(const item of entries)for(const meaning of item.meanings||[]){
    for(const definition of meaning.definitions||[]){
      if(!definition.definition||count>=3)continue;
      const p=document.createElement("p"),pos=document.createElement("strong");
      pos.textContent=(meaning.partOfSpeech||"")+" · ";
      p.append(pos,document.createTextNode(definition.definition));
      if(definition.example){const example=document.createElement("small");example.textContent=definition.example;p.append(example);}
      $("wordDefinitions").append(p);count++;
    }
  }
  if(!count)$("wordNote").textContent="Chưa có định nghĩa cho từ này.";
}
async function readSelectedWord(sequence=lookupSequence) {
  if(selectedDetection===null||sequence!==lookupSequence)return;
  if(pronunciation){
    const audio=pronunciation;
    try{audio.currentTime=0;await audio.play();if(sequence===lookupSequence)$("wordNote").textContent="Đang phát âm thanh từ Dictionary API.";}
    catch{if(sequence===lookupSequence&&pronunciation===audio)$("wordNote").textContent="Bấm Nghe phát âm để thử lại; trình duyệt có thể đang chặn âm thanh.";}
  }else if(window.speechSynthesis){
    speechSynthesis.cancel();
    const speech=new SpeechSynthesisUtterance(lastResult.detections[selectedDetection].label);
    speech.lang="en-US";
    const voice=speechSynthesis.getVoices().find(v=>v.lang==="en-US")||speechSynthesis.getVoices().find(v=>v.lang.startsWith("en"));
    if(voice)speech.voice=voice;
    speech.rate=.85;
    speech.onerror=()=>{if(sequence===lookupSequence)$("wordNote").textContent="Không phát được giọng đọc. Bạn có thể thử lại."};
    speechSynthesis.speak(speech);
    $("wordNote").textContent="API chưa có âm thanh dùng được; đang đọc bằng giọng trình duyệt.";
  }else{
    $("wordNote").textContent="Không có âm thanh phát âm cho từ này.";
  }
}
async function selectDetection(index) {
  if(!lastResult?.detections[index])return;
  stopAI();clearWordSelection();selectedDetection=index;
  const sequence=lookupSequence,word=lastResult.detections[index].label.trim().toLowerCase();
  redrawBoxes();
  $("wordPanel").hidden=false;$("wordTitle").textContent=word;
  const detection=lastResult.detections[index];
  const percent=value=>(value*100).toLocaleString("vi-VN",{minimumFractionDigits:2,maximumFractionDigits:2})+"%";
  let ramText="RAM: không sử dụng trong chế độ nhập nhãn.";
  if(Number.isFinite(detection.ram_score)){
    ramText="RAM: "+percent(detection.ram_score)+" · ngưỡng nhãn: "+percent(detection.ram_threshold)+".";
  }else if(lastResult.mode==="auto"){
    ramText="RAM: không có điểm khớp chính xác với nhãn này.";
  }
  $("wordConfidence").textContent=ramText+" Grounding DINO: "+percent(detection.score)
    +". Điểm RAM áp dụng cho nhãn trong toàn ảnh; điểm DINO áp dụng cho box được chọn.";
  $("wordPhonetic").textContent="";$("wordDefinitions").replaceChildren();
  $("wordNote").textContent="Đang tra Dictionary API…";$("pronounce").disabled=true;
  $("aiState").textContent="Đang chọn: "+word;
  try{
    let entries=dictionaryCache.get(word);
    if(!entries){
      const controller=new AbortController();lookupAbort=controller;
      const timeout=setTimeout(()=>controller.abort(),10000);
      try{
        const response=await fetch("/api/dictionary?word="+encodeURIComponent(word),{signal:controller.signal});
        if(response.status===404)throw new Error("Từ điển chưa có mục từ này.");
        if(!response.ok)throw new Error("Từ điển đang không phản hồi. Bạn có thể thử lại.");
        entries=await response.json();
        if(!Array.isArray(entries)||!entries.length)throw new Error("Từ điển chưa có dữ liệu cho từ này.");
        dictionaryCache.set(word,entries);
      }finally{clearTimeout(timeout);}
    }
    if(sequence!==lookupSequence)return;
    displayDictionary(entries);
    const audioUrl=dictionaryAudio(entries);
    if(audioUrl){
      pronunciation=new Audio("/api/pronunciation?word="+encodeURIComponent(word));
      pronunciation.onended=()=>{if(sequence===lookupSequence)$("wordNote").textContent="Bấm Nghe phát âm để nghe lại.";};
      pronunciation.onerror=()=>{
        if(sequence!==lookupSequence)return;
        pronunciation=null;readSelectedWord(sequence);
      };
    }
    $("pronounce").disabled=false;
    await readSelectedWord(sequence);
  }catch(error){
    if(sequence!==lookupSequence)return;
    $("wordNote").textContent=error.name==="AbortError"?"Tra từ quá lâu hoặc không có mạng. Bấm Nghe phát âm để dùng giọng trình duyệt.":error.message;
    $("pronounce").disabled=!window.speechSynthesis;
    const detail=document.createElement("p");detail.textContent=$("wordNote").textContent;$("wordDefinitions").append(detail);
    if(window.speechSynthesis)await readSelectedWord(sequence);
  }
}
$("pronounce").onclick=()=>readSelectedWord();
$("showAll").onclick=()=>{clearWordSelection();redrawBoxes();$("aiState").textContent="Hiện tất cả vật thể";};
$("result").onclick=event=>{
  if(!resultPhoto)return;
  const canvas=$("result"),rect=canvas.getBoundingClientRect();
  const scale=Math.min(rect.width/canvas.width,rect.height/canvas.height);
  const x=(event.clientX-rect.left-(rect.width-canvas.width*scale)/2)/scale;
  const y=(event.clientY-rect.top-(rect.height-canvas.height*scale)/2)/scale;
  const contains=r=>x>=r[0]&&x<=r[2]&&y>=r[1]&&y<=r[3];
  const labels=labelTargets.filter(t=>contains(t.label));
  const boxes=labelTargets.filter(t=>contains(t.box)).sort((a,b)=>
    (a.box[2]-a.box[0])*(a.box[3]-a.box[1])-(b.box[2]-b.box[0])*(b.box[3]-b.box[1]));
  const hit=labels.at(-1)||boxes[0];
  if(hit)selectDetection(hit.index);
};

async function infer(canvas,token) {
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",.85));
  const query=new URLSearchParams({mode:$("mode").value,labels:$("labels").value,threshold:$("threshold").value/100});
  const data=await api("/api/infer?"+query,blob,true);
  if(token===generation)render(canvas,data);
}
async function loop(token) {
  if(!active||token!==generation||!connected)return;
  busy=true;controls();$("aiState").textContent="Đang phân tích";
  try{await infer(capture(),token);if(token===generation)$("aiState").textContent="Đang chạy";}
  catch(error){if(token===generation){stopAI();say(error.message,true);}}
  finally{busy=false;controls();}
  if(active&&token===generation)setTimeout(()=>loop(token),350);
}
$("ai").onclick=()=>{
  if(active){stopAI();return;}
  if($("mode").value==="manual"&&!$("labels").value.trim()){say("Nhập ít nhất một tên vật thể tiếng Anh.",true);return;}
  active=true;const token=++generation;controls();
  say("AI đang chạy. Bounding box nằm trên đúng ảnh đã phân tích ở khung bên phải.");loop(token);
};
$("snapshot").onclick=async()=>{
  if(busy || !connected || !ready()) return;
  if($("mode").value==="manual"&&!$("labels").value.trim()){
    say("Nhập ít nhất một tên vật thể tiếng Anh.",true);return;
  }
  stopAI();
  const token=generation;
  takingPhoto=true;busy=true;controls();$("aiState").textContent="Đang nhận diện ảnh chụp";
  try{
    const photo=capture();
    say("Đã chụp khung hình. AI đang nhận diện ảnh này…");
    await infer(photo,token);
    if(token===generation){
      $("aiState").textContent="Đã nhận diện ảnh chụp";
      say("Đã nhận diện xong. Bấm Chụp & nhận diện để phân tích một ảnh mới.");
    }
  }catch(error){
    if(token===generation){say(error.message,true);$("aiState").textContent="Không thành công";}
  }finally{takingPhoto=false;busy=false;controls();}
};
$("sample").onclick=async()=>{
  stopAI();const token=generation;busy=true;controls();$("aiState").textContent="Đang thử ảnh";
  try{
    const response=await fetch("/api/sample"), bitmap=await createImageBitmap(await response.blob());
    const canvas=document.createElement("canvas");const scale=Math.min(1,800/Math.max(bitmap.width,bitmap.height));canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
    canvas.getContext("2d").drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();await infer(canvas,token);
    $("aiState").textContent="Đã thử ảnh mẫu";say("Đã nhận diện ảnh mẫu. Kết nối camera để thử với khung hình của bạn.");
  }catch(error){say(error.message,true);$("aiState").textContent="Không thành công";}
  finally{busy=false;controls();}
};
$("save").onclick=()=>{const link=document.createElement("a");link.download="englishlens-"+Date.now()+".png";link.href=$("result").toDataURL("image/png");link.click();};
async function refresh() {
  try{
    status=await api("/api/status");const m=status.models;
    $("dinoState").textContent=m.dino?"Sẵn sàng":(m.dino_download_mb||0)+" / 689 MB";$("ramState").textContent=m.ram?"Sẵn sàng":"Chưa tải xong";
    $("ramProgress").style.width=Math.min(100,m.ram_download_mb/m.ram_total_mb*100)+"%";
    $("downloadText").textContent=m.ram?"RAM đã sẵn sàng":m.ram_download_mb+" / "+m.ram_total_mb+" MB";
    const phases={loading_ram:"Đang nạp RAM lần đầu",loading_dino:"Đang nạp DINO lần đầu",tagging:"Đang tìm nhãn",detecting:"Đang tìm vị trí"};
    if(busy&&phases[status.phase])$("aiState").textContent=phases[status.phase];
    if(source==="ip"&&streamWanted&&status.camera.state==="connected"){
      const image=$("ipStream");
      const fresh=status.camera.frame_age!==null&&status.camera.frame_age<2;
      if(fresh&&image.naturalWidth){
        image.hidden=false;showFrame(image.naturalWidth,image.naturalHeight);
        $("cameraFps").textContent=status.camera.fps+" FPS · nguồn camera";
      }else if(!fresh&&connected){
        connected=false;stopAI();image.hidden=true;$("emptyLive").hidden=false;
        $("liveDot").classList.remove("live");$("cameraState").textContent="Mất tín hiệu";
        $("cameraFps").textContent="";
      }
    }
    if(source==="ip"&&streamWanted&&["error","disconnected"].includes(status.camera.state)){
      say(status.camera.error||"Camera đã ngắt kết nối.",true);connected=false;stopAI();stopStream();
      $("cameraState").textContent="Không kết nối được";$("liveDot").classList.remove("live");
      $("emptyLive").hidden=false;$("cameraFps").textContent="";
    }
    controls();
  }catch{say("Không kết nối được máy chủ EnglishLens. Mở lại start-ui.cmd.",true);}
  setTimeout(refresh,2000);
}
refresh();
