/* Personal vocabulary stays on this browser and works without a dictionary connection. */
(() => {
  const KEY = 'englishlens.vocabulary.v1';
  let words = [], editing = null, queue = [], initialCount = 0, learned = 0, flipped = false;
  let storageReady = true;
  const normalize = word => word.trim().replace(/\s+/g, ' ').toLowerCase();
  const notice = text => { $('vocabMessage').textContent = text; };
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw === null ? [] : JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.some(w => !w || typeof w.word !== 'string' || !w.word.trim() || typeof w.meaning !== 'string' || typeof w.definition !== 'string' || typeof w.phonetic !== 'string')) throw new Error('Invalid vocabulary');
    words = parsed;
  } catch {
    storageReady = false;
    notice('Không đọc được dữ liệu đã lưu. Hãy kiểm tra quyền lưu trữ của trình duyệt; dữ liệu cũ sẽ không bị ghi đè.');
  }
  function persist(next) {
    if (!storageReady) { notice('Chưa thể lưu bộ từ. Kiểm tra dữ liệu hoặc quyền lưu trữ rồi tải lại trang.'); return false; }
    try { localStorage.setItem(KEY, JSON.stringify(next)); words = next; return true; }
    catch { notice('Không lưu được. Bộ nhớ trình duyệt có thể đầy hoặc bị chặn; thay đổi chưa được lưu.'); return false; }
  }
  function button(text, action) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'textButton'; b.textContent = text; b.onclick = action; return b;
  }
  let wordAudio = null, audioSequence = 0;
  const pending = new Set();
  function stopSpeech() {
    audioSequence++;
    if (wordAudio) { wordAudio.pause(); wordAudio = null; }
    if (window.speechSynthesis) speechSynthesis.cancel();
  }
  async function speak(word) {
    if (pronunciation) pronunciation.pause();
    stopSpeech(); const token = audioSequence;
    const fallback = () => {
      if (token !== audioSequence) return;
      if (wordAudio) { wordAudio.pause(); wordAudio = null; }
      if (!window.speechSynthesis) { notice('Không có âm thanh cho từ này.'); return; }
      notice('Audio API chưa dùng được; đang dùng giọng đọc trình duyệt.');
      const speech = new SpeechSynthesisUtterance(word); speech.lang = 'en-US'; speech.rate = .85;
      speech.onerror = () => { if (token === audioSequence) notice('Không phát được giọng đọc.'); };
      speechSynthesis.speak(speech);
    };
    const audio = new Audio('/api/pronunciation?word=' + encodeURIComponent(word)); wordAudio = audio;
    let failed = false;
    const fail = () => { if (!failed) { failed = true; fallback(); } };
    audio.onerror = fail;
    try { await audio.play(); } catch { fail(); }
  }
  async function enrich(word) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch('/api/vocabulary?word=' + encodeURIComponent(word), {signal: controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Không lấy được dữ liệu API.');
      return data;
    } finally { clearTimeout(timeout); }
  }
  async function addWord(word, meaning = '') {
    if (word.length > 80 || !/^[a-z]+(?:[ '\-][a-z]+)*$/.test(word)) { notice('Nhập từ hoặc cụm từ tiếng Anh hợp lệ (tối đa 80 ký tự).'); return; }
    if (pending.has(word)) return;
    pending.add(word); notice('Đang dịch và lấy ví dụ cho “' + word + '”…');
    try {
      let data;
      try { data = await enrich(word); }
      catch (error) { data = {warnings: [error.name === 'AbortError' ? 'API phản hồi quá lâu. Có thể bấm Lấy lại API.' : error.message]}; }
      if (words.some(w => w.word === word)) return;
      const item = {word, meaning: meaning || data.meaning || '', definition: data.definition || '', phonetic: data.phonetic || '', example: data.example || '', translationSource: data.translationSource || '', dictionarySource: data.dictionarySource || '', meaningEdited: Boolean(meaning)};
      if (!persist([...words, item])) return;
      renderList(); notice('Đã lưu “' + word + '”. ' + (data.warnings || []).join(' '));
    } finally { pending.delete(word); }
  }
  async function refreshWord(word) {
    if (pending.has(word)) return;
    pending.add(word); notice('Đang lấy lại dữ liệu API cho “' + word + '”…');
    try {
      const data = await enrich(word), current = words.find(w => w.word === word);
      if (!current) return;
      const updated = {...current};
      for (const key of ['definition', 'example', 'phonetic', 'translationSource', 'dictionarySource']) if (data[key]) updated[key] = data[key];
      // Existing entries without this marker may contain a manually entered meaning.
      if (!current.meaning || current.meaningEdited === false) updated.meaning = data.meaning || current.meaning;
      if (!persist(words.map(w => w.word === word ? updated : w))) return;
      renderList(); if (!$('studyPanel').hidden) renderCard();
      notice('Đã cập nhật “' + word + '”. ' + (data.warnings || []).join(' '));
    } catch (error) { notice('Chưa cập nhật được: ' + error.message); }
    finally { pending.delete(word); }
  }
  function resetForm() {
    editing = null; $('wordForm').reset(); $('vocabWord').readOnly = false;
    $('submitWord').textContent = 'Lưu từ'; $('cancelEdit').hidden = true;
  }
  function edit(word) {
    editing = word.word; $('vocabWord').value = word.word; $('vocabWord').readOnly = true;
    $('vocabMeaning').value = word.meaning; $('submitWord').textContent = 'Lưu thay đổi';
    $('cancelEdit').hidden = false; $('vocabMeaning').focus();
  }
  function renderList() {
    $('vocabCount').textContent = words.length;
    $('startStudy').disabled = !words.length;
    const query = normalize($('vocabSearch').value);
    const list = $('vocabList'); list.replaceChildren();
    const filtered = words.filter(w => (w.word + ' ' + w.meaning + ' ' + w.definition).toLowerCase().includes(query));
    if (!filtered.length) {
      const p = document.createElement('p'); p.className = 'muted';
      p.textContent = words.length ? 'Không có từ phù hợp.' : 'Chưa có từ nào. Chọn vật thể trong ảnh và bấm Thêm vào bộ từ vựng.';
      list.append(p);
    }
    filtered.forEach(w => {
      const row = document.createElement('article'); row.className = 'vocabRow';
      const content = document.createElement('div'), title = document.createElement('strong'), meaning = document.createElement('p');
      title.textContent = w.word; meaning.textContent = w.meaning || w.definition || 'Chưa có nghĩa — bấm Sửa để bổ sung.';
      content.append(title, meaning);
      const example = document.createElement('p'); example.className = 'vocabExample';
      example.textContent = w.example ? 'Ví dụ: ' + w.example : 'API chưa có câu ví dụ. Có thể thử Lấy lại API.';
      const origin = document.createElement('small');
      origin.textContent = [w.phonetic, w.translationSource ? 'Dịch: ' + w.translationSource : '', w.dictionarySource ? 'Ví dụ / phát âm: ' + w.dictionarySource : ''].filter(Boolean).join(' · ');
      content.append(example, origin);
      const actions = document.createElement('div'); actions.className = 'vocabActions';
      actions.append(button('Nghe ▶', () => speak(w.word)), button('Lấy lại API', () => refreshWord(w.word)), button('Sửa', () => edit(w)), button('Xóa', () => {
        if (!confirm('Xóa “' + w.word + '” khỏi bộ từ vựng?')) return;
        if (!persist(words.filter(item => item.word !== w.word))) return;
        if (editing === w.word) resetForm();
        queue = queue.filter(word => word !== w.word);
        renderList(); if (!$('studyPanel').hidden) renderCard();
        notice('Đã xóa “' + w.word + '”.');
      }));
      row.append(content, actions); list.append(row);
    });
  }
  $('cancelEdit').onclick = resetForm;
  $('vocabSearch').oninput = renderList;
  $('wordForm').onsubmit = async event => {
    event.preventDefault();
    const word = normalize($('vocabWord').value), meaning = $('vocabMeaning').value.trim();
    if (!word) { notice('Nhập từ tiếng Anh trước khi lưu.'); return; }
    const existing = words.find(w => w.word === word);
    if (existing && !editing) { notice('Từ này đã có trong bộ từ. Bạn có thể sửa nghĩa bên dưới.'); edit(existing); return; }
    if (!existing) { resetForm(); await addWord(word, meaning); return; }
    const item = {...existing, meaning, meaningEdited: true};
    if (!persist(existing ? words.map(w => w.word === word ? item : w) : [...words, item])) return;
    resetForm(); renderList(); notice('Đã lưu “' + word + '”.');
    if (!$('studyPanel').hidden) renderCard();
  };
  $('saveWord').onclick = async () => {
    const detection = lastResult?.detections[selectedDetection];
    if (!detection) return;
    const word = normalize(detection.label), existing = words.find(w => w.word === word);
    if (existing) { notice('“' + word + '” đã có trong bộ từ.'); edit(existing); return; }
    await addWord(word);
  };
  function renderCard() {
    stopSpeech(); flipped = false;
    const current = words.find(w => w.word === queue[0]);
    const done = !current;
    $('flashcard').hidden = done;
    $('cardSpeak').disabled = done; $('cardAgain').disabled = true; $('cardKnown').disabled = true;
    $('restartStudy').hidden = !done;
    $('restartStudy').disabled = !words.length;
    $('studyProgress').textContent = done ? 'Hoàn thành lượt học! Đã nhớ ' + learned + ' từ.' : 'Đã nhớ ' + learned + ' / ' + initialCount + ' · Còn ' + queue.length + ' thẻ';
    if (done) return;
    $('cardSide').hidden = false; $('cardHint').hidden = false; $('cardWord').hidden = false;
    $('cardSide').textContent = 'TỪ TIẾNG ANH'; $('cardWord').textContent = current.word;
    $('cardMeaning').textContent = ''; $('cardHint').textContent = 'Bấm thẻ hoặc nhấn Enter để xem nghĩa';
    $('flashcard').classList.remove('flipped'); $('flashcard').setAttribute('aria-label', current.word + '. Lật thẻ để xem nghĩa');
  }
  function beginStudy() {
    if (!words.length) return;
    stopAI(); if (pronunciation) pronunciation.pause();
    queue = words.map(w => w.word);
    for (let i = queue.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [queue[i], queue[j]] = [queue[j], queue[i]]; }
    initialCount = queue.length; learned = 0; $('studyPanel').hidden = false; renderCard();
    $('flashcard').focus();
  }
  $('startStudy').onclick = beginStudy; $('restartStudy').onclick = beginStudy;
  $('closeStudy').onclick = () => { stopSpeech(); $('studyPanel').hidden = true; queue = []; $('startStudy').focus(); };
  $('flashcard').onclick = () => {
    const current = words.find(w => w.word === queue[0]); if (!current) return;
    flipped = !flipped; $('flashcard').classList.toggle('flipped', flipped);
    $('cardSide').hidden = flipped; $('cardHint').hidden = flipped; $('cardWord').hidden = flipped;
    $('cardMeaning').textContent = flipped ? [current.meaning || 'Chưa có nghĩa tiếng Việt.', current.example ? 'Ví dụ: ' + current.example : 'Chưa có câu ví dụ.'].filter(Boolean).join('\n\n') || 'Chưa có nghĩa. Bấm Sửa trong bộ từ để bổ sung.' : '';
    $('cardHint').textContent = flipped ? 'Bạn đã nhớ từ này chưa?' : 'Bấm thẻ hoặc nhấn Enter để xem nghĩa';
    $('flashcard').setAttribute('aria-label', flipped ? $('cardMeaning').textContent + '. Bấm để xem mặt trước' : current.word + '. Lật thẻ để xem nghĩa');
    $('cardAgain').disabled = !flipped; $('cardKnown').disabled = !flipped;
  };
  $('cardSpeak').onclick = () => { if (queue.length) speak(queue[0]); };
  function grade(known) {
    if (!flipped || !queue.length) return;
    const word = queue.shift(); if (known) learned++; else queue.push(word);
    renderCard(); (queue.length ? $('flashcard') : $('restartStudy')).focus();
  }
  $('cardAgain').onclick = () => grade(false); $('cardKnown').onclick = () => grade(true);
  renderList();
})();
