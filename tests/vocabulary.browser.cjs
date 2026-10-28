const {chromium} = require('../.cache/ui-tests/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const page = await browser.newPage(); const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/vocabulary?*', route => {
  const word = new URL(route.request().url()).searchParams.get('word');
  return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({word,meaning:'nghĩa API',definition:'A test definition',example:'This is a '+word+'.',phonetic:'/test/',warnings:[],translationSource:'Argos Translate',dictionarySource:'Free Dictionary API'})});
 });
 await page.goto('http://127.0.0.1:7860');
 await page.locator('#vocabWord').fill('  Bottle  '); await page.locator('#vocabMeaning').fill('chai nước');
 await page.locator('#submitWord').click(); await page.waitForFunction(()=>document.getElementById('vocabCount').textContent==='1'); assert.equal(await page.locator('#vocabCount').innerText(),'1');
 await page.reload(); assert.equal(await page.locator('.vocabRow strong').innerText(),'bottle');
 await page.locator('#vocabWord').fill('BOTTLE'); await page.locator('#submitWord').click();
 assert.equal(await page.locator('#vocabCount').innerText(),'1');
 await page.locator('#vocabMeaning').fill('cái chai'); await page.locator('#submitWord').click();
 assert.equal(await page.locator('.vocabRow p').first().innerText(),'cái chai');
 await page.locator('#vocabWord').fill('book'); await page.locator('#vocabMeaning').fill('quyển sách'); await page.locator('#submitWord').click(); await page.waitForFunction(()=>document.getElementById('vocabCount').textContent==='2');
 await page.locator('#vocabSearch').fill('sách'); assert.equal(await page.locator('.vocabRow').count(),1); await page.locator('#vocabSearch').fill('');
 await page.locator('#startStudy').click(); assert(await page.locator('#cardKnown').isDisabled());
 const first=await page.locator('#cardWord').innerText(); await page.locator('#flashcard').click();
 assert(await page.locator('#cardWord').isHidden());
 assert(await page.locator('#cardSide').isHidden());
 const back = await page.locator('#flashcard').innerText();
 assert(!back.includes('A test definition')); assert(!back.includes('/test/'));
 assert.match(back,/Ví dụ:/); assert.match(back,/cái chai|quyển sách/);
 await page.locator('#cardAgain').click(); assert(await page.locator('#cardWord').isVisible());
 assert.notEqual(await page.locator('#cardWord').innerText(),first);
 for(let i=0;i<2;i++){await page.locator('#flashcard').click(); await page.locator('#cardKnown').click();}
 assert(await page.locator('#restartStudy').isVisible()); assert.match(await page.locator('#studyProgress').innerText(),/Đã nhớ 2/);
 await page.locator('#closeStudy').click();
 await page.locator('.vocabRow').filter({hasText:'bottle'}).getByRole('button',{name:'Lấy lại API'}).click();
 await page.waitForFunction(()=>document.getElementById('vocabMessage').textContent.includes('Đã cập nhật'));
 assert.match(await page.locator('.vocabRow').filter({hasText:'bottle'}).innerText(), /cái chai/);
 // Exercise saving an actual detection without loading AI weights.
 await page.route('**/api/dictionary?*', route=>route.fulfill({status:404,contentType:'application/json',body:'{}'}));
 await page.evaluate(()=>{
  const canvas=document.createElement('canvas');canvas.width=100;canvas.height=100;
  render(canvas,{size:[100,100],seconds:1,device:'cpu',tags:['lamp'],mode:'manual',detections:[{label:'lamp',score:.8,box:[0,0,50,50]}]});
 });
 await page.locator('.detection').click(); await page.locator('#saveWord').click(); await page.waitForFunction(()=>document.getElementById('vocabCount').textContent==='3');
 assert.equal(await page.locator('#vocabCount').innerText(),'3');
 assert.match(await page.locator('.vocabRow').filter({hasText:'lamp'}).innerText(), /nghĩa API/);
 assert.match(await page.locator('.vocabRow').filter({hasText:'lamp'}).innerText(), /This is a lamp/);
 await page.locator('#saveWord').click(); assert.equal(await page.locator('#vocabCount').innerText(),'3');
 // Verify mirrored capture pixels, as well as the live preview transform.
 await page.evaluate(async()=>{
  const c=document.createElement('canvas');c.width=100;c.height=50;const ctx=c.getContext('2d');ctx.fillStyle='red';ctx.fillRect(0,0,50,50);ctx.fillStyle='blue';ctx.fillRect(50,0,50,50);
  const img=$('ipStream');img.src=c.toDataURL();await img.decode();source='ip';showFrame(100,50);
 });
 await page.locator('#mirrorCamera').click();
 assert.equal(await page.locator('#mirrorCamera').getAttribute('aria-pressed'),'true');
 const pixel=await page.evaluate(()=>Array.from(capture().getContext('2d').getImageData(10,10,1,1).data));assert.deepEqual(pixel,[0,0,255,255]);
 await page.locator('#mirrorCamera').click();
 const original=await page.evaluate(()=>Array.from(capture().getContext('2d').getImageData(10,10,1,1).data));assert.deepEqual(original,[255,0,0,255]);
 page.on('dialog',dialog=>dialog.accept());
 await page.locator('.vocabRow').filter({hasText:'lamp'}).getByRole('button',{name:'Xóa',exact:true}).click();
 await page.reload();assert.equal(await page.locator('#vocabCount').innerText(),'2');
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:'outputs/vocabulary-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});await page.locator('#startStudy').click();await page.locator('#flashcard').click();
 await page.locator('.vocabulary').screenshot({path:'outputs/vocabulary-desktop.png'});
 assert.deepEqual(errors,[]);console.log('PASS: persistence, duplicate prevention, edit, search, detection saving, flashcard queue, deletion, mirror capture, responsive layout; no JS errors.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
