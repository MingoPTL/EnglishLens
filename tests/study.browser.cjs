// Isolated browser profile and mocked HTTP: never touches the user's saved words.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('http://127.0.0.1:7860/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname.startsWith('/api/')) return route.fulfill({status: 503, contentType: 'application/json', body: '{}'});
      const name = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      const types = {html: 'text/html', js: 'text/javascript', css: 'text/css'};
      await route.fulfill({contentType: types[name.split('.').pop()], body: await fs.readFile(path.join(__dirname, '../web', name))});
    });
    await page.addInitScript(() => {
      // Deterministic playback; count objects to verify preload and repeat reuse.
      window.audioCreated = []; window.audioPlayed = [];
      window.Audio = class {
        constructor(url) { this.url = url; window.audioCreated.push(url); }
        pause() {}
        play() { window.audioPlayed.push(this.url); return Promise.resolve(); }
      };
    });
    await page.goto('http://127.0.0.1:7860');
    await page.evaluate(() => localStorage.setItem('englishlens.vocabulary.v1', JSON.stringify(
      ['bed', 'book', 'bottle'].map(word => ({word, meaning: 'nghĩa', definition: '', phonetic: ''}))
    )));
    await page.reload();
    await page.locator('#startStudy').click();
    assert.equal(await page.evaluate(() => audioCreated.length), 1, 'preloads current card');
    await page.locator('#cardSpeak').click(); await page.locator('#cardSpeak').click();
    assert.equal(await page.evaluate(() => audioCreated.length), 1, 'repeat reuses audio');
    assert.equal(await page.evaluate(() => audioPlayed.length), 2);
    await page.locator('#flashcard').click(); await page.locator('#cardAgain').click();
    await page.locator('#flashcard').click(); await page.locator('#cardKnown').click();
    const next = await page.locator('#cardWord').innerText();
    await page.reload();
    assert.match(await page.locator('#startStudy').innerText(), /Tiếp tục/);
    await page.locator('#startStudy').click();
    assert.equal(await page.locator('#cardWord').innerText(), next);
    assert.match(await page.locator('#studyProgress').innerText(), /Đã nhớ 1 \/ 3/);
    await page.locator('#closeStudy').click(); await page.locator('#startStudy').click();
    assert.equal(await page.locator('#cardWord').innerText(), next);
    for (let i = 0; i < 2; i++) { await page.locator('#flashcard').click(); await page.locator('#cardKnown').click(); }
    const state = await page.evaluate(() => JSON.parse(localStorage.getItem('englishlens.study.v1')));
    assert.equal(state.session, null); assert.equal(state.history.length, 1);
    assert.equal(state.history[0].learned, 3); assert.equal(state.history[0].again, 1);
    await page.reload();
    assert.match(await page.locator('#studyHistory').textContent(), /Đã nhớ 3 \/ 3 từ · Học lại 1 lần/);
    // Deleting a pending card keeps saved progress consistent, including after reload.
    await page.locator('#startStudy').click();
    page.on('dialog', d => d.accept());
    await page.locator('.vocabRow').first().getByRole('button', {name: 'Xóa', exact: true}).click();
    await page.reload(); await page.locator('#startStudy').click();
    assert.match(await page.locator('#studyProgress').innerText(), /Còn 2 thẻ/);
    // Corrupt progress is preserved and reported without breaking vocabulary.
    await page.evaluate(() => localStorage.setItem('englishlens.study.v1', '{bad'));
    await page.reload();
    assert.match(await page.locator('#vocabMessage').innerText(), /Không đọc được tiến độ/);
    assert.equal(await page.locator('.vocabRow').count(), 2);
    await page.locator('#startStudy').click();
    assert.equal(await page.evaluate(() => localStorage.getItem('englishlens.study.v1')), '{bad');
    assert.deepEqual(errors, []);
    console.log('PASS: audio preloading/reuse, resume after reload/close, saved history, deletion, corrupt storage.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
