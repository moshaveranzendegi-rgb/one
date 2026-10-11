(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('projectForm');
  let currentJobId = null;
  let pollHandle = null;
  const voices = {
    fa: [{value:'fa-IR-DilaraNeural', label:'دیلا‌را · زن'}, {value:'fa-IR-FaridNeural', label:'فرید · مرد'}],
    en: [{value:'en-US-JennyNeural', label:'Jenny · Female'}, {value:'en-US-GuyNeural', label:'Guy · Male'}],
    ru: [{value:'ru-RU-SvetlanaNeural', label:'Светлана · женский'}, {value:'ru-RU-DmitryNeural', label:'Дмитрий · мужской'}]
  };
  const statusNames = {queued:'در صف', running:'در حال ساخت', completed:'تکمیل شد', failed:'ناموفق', cancelled:'لغو شد'};
  const capabilityNames = {
    ffmpeg:['FFmpeg و پردازش ویدئو', s => `${s.version || 'نسخه نامشخص'}${s.subtitle_filter ? ' · زیرنویس آماده' : ' · فیلتر زیرنویس ندارد'}`],
    wsl:['محیط WSL2 / GPU', s => s.message || ''],
    omniavatar:['موتور آواتار متحرک', s => s.ready ? 'مدل ۱٫۳B شناسایی شد' : 'کد یا وزن‌های مدل نصب نیست'],
    fashn:['تعویض لباس FASHN', s => s.ready ? 'وزن‌ها شناسایی شد' : 'اختیاری · مدل لباس نصب نیست'],
    body_completion:['تکمیل بدن', s => s.ready ? 'موتور نصب است' : 'اختیاری · مدل inpainting نصب نیست'],
    tts:['تبدیل متن به گفتار', s => s.ready ? 'Edge TTS نصب است' : 'برای استفاده از سناریو باید نصب شود'],
    background_removal:['حذف پس‌زمینه', s => s.ready ? 'برای ترکیب محیط آماده است' : 'برای عکس محیط نصب شود'],
    transcription:['زیرنویس صدای آپلودی', s => s.ready ? 'Whisper نصب است' : 'برای زیرنویس خودکار نصب شود']
  };
  function getToken() { return localStorage.getItem('rsai-token') || ''; }
  function setMessage(el, text, kind='') { el.textContent = text; el.className = `${el.dataset.base || el.className.split(' ')[0]}${kind ? ' '+kind : ''}`; }
  function toPersianDigits(value) { return String(value).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]); }
  async function api(path, options={}) {
    const headers = new Headers(options.headers || {});
    if (getToken()) headers.set('X-RS-AI-Token', getToken());
    const response = await fetch(path, {...options, headers});
    const type = response.headers.get('content-type') || '';
    const payload = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) throw new Error((payload && payload.detail) || `HTTP ${response.status}`);
    return payload;
  }
  function revealTokenPanel(message='برای ادامه، توکن دسترسی نصب را وارد کن.') {
    $('tokenPanel').classList.remove('hidden');
    $('tokenMessage').textContent = message;
  }
  function processHashToken() {
    if (location.hash.startsWith('#token=')) {
      const token = decodeURIComponent(location.hash.slice(7));
      if (token) localStorage.setItem('rsai-token', token);
      history.replaceState(null, '', location.pathname + location.search);
    }
  }
  function updateVoices() {
    const language = $('language').value;
    $('voice').replaceChildren(...voices[language].map(v => {
      const option = document.createElement('option'); option.value = v.value; option.textContent = v.label; return option;
    }));
    $('scenario').placeholder = language === 'fa' ? 'مثلاً: سلام، امروز می‌خواهم دربارهٔ خدمات مجموعه توضیح بدهم...' : language === 'en' ? 'For example: Hello, today I want to introduce our services...' : 'Например: Здравствуйте, сегодня я расскажу о наших услугах...';
  }
  function updateAudioMode() {
    const upload = $('audioSource').value === 'upload';
    $('voiceField').classList.toggle('hidden', upload);
    $('audioUploadField').classList.toggle('hidden', !upload);
    $('audioFile').required = upload;
    $('scenario').required = !upload;
  }
  function updateClothingMode() {
    const current = document.querySelector('input[name="clothing_mode"]:checked').value === 'current';
    $('garmentArea').classList.toggle('disabled-area', current);
    $('garmentArea').setAttribute('aria-disabled', String(current));
    $('garmentArea').querySelectorAll('input, select').forEach(el => { el.disabled = current; if (current && el.type === 'file') el.value = ''; });
  }
  function updateOnepieceAvailability() {
    const one = $('garmentOnepiece').files.length > 0;
    const upper = $('garmentUpper').files.length > 0;
    const lower = $('garmentLower').files.length > 0;
    $('garmentUpper').setCustomValidity(one && upper ? 'لباس یک‌تکه با بالاتنه هم‌زمان نمی‌شود.' : '');
    $('garmentLower').setCustomValidity(one && lower ? 'لباس یک‌تکه با پایین‌تنه هم‌زمان نمی‌شود.' : '');
    $('garmentOnepiece').setCustomValidity(one && (upper || lower) ? 'لباس یک‌تکه با دو لایه دیگر هم‌زمان نمی‌شود.' : '');
  }
  function fileLabel(inputId, labelId, fallback) {
    const file = $(inputId).files[0]; $(labelId).textContent = file ? file.name : fallback;
  }
  function capabilityRow(key, value) {
    const cfg = capabilityNames[key]; const row = document.createElement('div'); row.className='capability';
    const left = document.createElement('div'); const strong = document.createElement('strong'); strong.textContent = cfg[0];
    const small = document.createElement('small'); small.textContent = cfg[1](value || {}); left.append(strong,small);
    const badge = document.createElement('span'); badge.className = 'state-pill ' + (value?.ready ? 'ok' : (key === 'fashn' || key === 'body_completion' || key === 'background_removal' || key === 'transcription' ? '' : 'bad'));
    badge.textContent = value?.ready ? 'آماده' : ((key === 'fashn' || key === 'body_completion' || key === 'background_removal' || key === 'transcription') ? 'اختیاری' : 'نیاز به نصب');
    row.append(left,badge); return row;
  }
  async function refreshStatus() {
    try {
      const s = await api('/api/status');
      const list = $('capabilityList'); list.replaceChildren();
      Object.keys(capabilityNames).forEach(k => { if (s[k]) list.append(capabilityRow(k,s[k])); });
      const canGenerate = s.ffmpeg?.ready && s.wsl?.ready && s.wsl?.gpu_ready && s.omniavatar?.ready;
      $('serverBadge').className = 'status-badge ' + (canGenerate ? 'ready' : 'warn');
      $('serverBadge').lastChild.textContent = canGenerate ? 'موتور اصلی آماده است' : 'نیاز به آماده‌سازی موتور';
      return s;
    } catch (error) {
      $('serverBadge').className = 'status-badge unknown';
      $('serverBadge').lastChild.textContent = 'دسترسی لازم است';
      revealTokenPanel(error.message.includes('توکن') ? error.message : 'اتصال به موتور برقرار نشد؛ توکن را بررسی کن.');
      $('capabilityList').replaceChildren(Object.assign(document.createElement('div'), {className:'empty-state',textContent:'برای مشاهدهٔ وضعیت، ابتدا توکن دسترسی معتبر وارد کن.'}));
      return null;
    }
  }
  function renderHistory(items) {
    const root = $('jobHistory'); root.replaceChildren();
    if (!items || !items.length) { root.append(Object.assign(document.createElement('div'), {className:'empty-state',textContent:'هنوز پروژه‌ای ساخته نشده است.'})); return; }
    items.forEach(item => {
      const card = document.createElement('div'); card.className='history-item';
      const top = document.createElement('div'); top.className='history-top';
      const id = document.createElement('strong'); id.textContent = item.id.slice(0,8);
      const state = document.createElement('span'); state.className='history-status '+item.status; state.textContent=statusNames[item.status] || item.status;
      top.append(id,state);
      const message=document.createElement('p'); message.textContent=item.message || '';
      card.append(top,message);
      if (item.status === 'completed') { const a=document.createElement('a'); a.href=`/api/jobs/${item.id}/download`; a.textContent='دریافت فایل'; a.addEventListener('click',e=>{e.preventDefault();download(item.id)});card.append(a); }
      root.append(card);
    });
  }
  async function refreshJobs() {
    try { const data = await api('/api/jobs'); $('todayCount').textContent=toPersianDigits(data.today_count || 0); renderHistory(data.items); } catch (_) { /* status view reports auth errors */ }
  }
  function showActiveJob(id) {
    currentJobId=id; $('activeJobPanel').classList.remove('hidden'); $('jobError').classList.add('hidden'); $('jobResult').classList.add('hidden'); $('downloadLink').classList.add('hidden'); $('jobStatus').textContent='در صف'; $('progressBar').style.width='0%';
    if (pollHandle) clearInterval(pollHandle); pollJob(); pollHandle=setInterval(pollJob,2500);
  }
  async function pollJob() {
    if (!currentJobId) return;
    try {
      const job=await api(`/api/jobs/${currentJobId}`);
      $('jobStatus').textContent=statusNames[job.status] || job.status;
      $('progressBar').style.width=`${Math.max(0,Math.min(100,job.progress || 0))}%`;
      $('progressText').textContent=toPersianDigits(job.progress || 0)+'٪';
      $('progressMessage').textContent=job.message || '';
      if (job.status==='failed') { $('jobError').classList.remove('hidden'); $('jobError').textContent=job.error || 'خطای نامشخص'; $('createButton').disabled=false; clearInterval(pollHandle); pollHandle=null; refreshJobs(); }
      if (job.status==='completed') { $('jobResult').classList.remove('hidden'); $('jobResult').textContent=`ذخیره شد: ${job.output_path || ''}`; $('downloadLink').classList.remove('hidden'); $('downloadLink').href='#'; $('downloadLink').onclick=(e)=>{e.preventDefault();download(job.id)}; $('createButton').disabled=false; clearInterval(pollHandle); pollHandle=null; refreshJobs(); }
    } catch (error) { $('progressMessage').textContent=error.message; }
  }
  async function download(id) {
    try {
      const response=await fetch(`/api/jobs/${id}/download`,{headers:{'X-RS-AI-Token':getToken()}});
      if (!response.ok) throw new Error('دانلود فایل ناموفق بود.');
      const blob=await response.blob(); const url=URL.createObjectURL(blob); const a=document.createElement('a');a.href=url;a.download=`RS-ai-${id.slice(0,8)}.mp4`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
    } catch(error) { alert(error.message); }
  }
  $('language').addEventListener('change',updateVoices);
  $('audioSource').addEventListener('change',updateAudioMode);
  document.querySelectorAll('input[name="clothing_mode"]').forEach(el => el.addEventListener('change',updateClothingMode));
  ['garmentUpper','garmentLower','garmentOnepiece'].forEach(id => $(id).addEventListener('change',updateOnepieceAvailability));
  $('avatarFile').addEventListener('change',()=>fileLabel('avatarFile','avatarName','انتخاب عکس'));
  $('environmentFile').addEventListener('change',()=>fileLabel('environmentFile','environmentName','انتخاب محیط'));
  $('audioFile').addEventListener('change',()=>fileLabel('audioFile','audioName','MP3 / WAV / M4A · حداکثر ۳ دقیقه'));
  $('scenario').addEventListener('input',()=> $('scenarioCount').textContent=toPersianDigits($('scenario').value.length)+' کاراکتر');
  $('refreshStatus').addEventListener('click',refreshStatus); $('openSettings').addEventListener('click',()=>{ $('activeJobPanel').classList.add('hidden'); document.querySelector('.status-panel').scrollIntoView({behavior:'smooth',block:'center'}); refreshStatus(); });
  $('saveToken').addEventListener('click',async()=>{ const value=$('tokenInput').value.trim(); if(!value){$('tokenMessage').textContent='توکن را وارد کن.';return;}localStorage.setItem('rsai-token',value);const data=await refreshStatus();if(data){$('tokenPanel').classList.add('hidden');$('tokenMessage').textContent='اتصال برقرار شد.';refreshJobs();}else{localStorage.removeItem('rsai-token');$('tokenMessage').textContent='توکن معتبر نیست.';} });
  form.addEventListener('submit',async(e)=>{
    e.preventDefault(); $('formMessage').textContent=''; $('formMessage').className='form-message';
    if (!getToken()) { revealTokenPanel(); return; }
    if (!$('avatarFile').files[0]) { $('formMessage').textContent='ابتدا عکس آواتار را انتخاب کن.'; $('formMessage').classList.add('error'); return; }
    updateOnepieceAvailability(); if (!form.reportValidity()) return;
    if ($('audioSource').value==='upload'&&!$('audioFile').files[0]) { $('formMessage').textContent='فایل صدای خودت را انتخاب کن.'; $('formMessage').classList.add('error'); return; }
    if ($('subtitles').checked && $('audioSource').value==='upload') { const status=await refreshStatus(); if(status && !status.transcription.ready) { const ok=confirm('برای زیرنویس دقیق این فایل صوتی، Whisper باید نصب باشد. ارسال پروژه ادامه یابد تا خطای نصب را از موتور دریافت کنی؟'); if(!ok)return; } }
    const data=new FormData(form); if(!$('subtitles').checked)data.set('subtitles','false'); else data.set('subtitles','true');
    $('createButton').disabled=true; $('createButton').querySelector('span').textContent='در حال ثبت پروژه…';
    try { const result=await api('/api/jobs',{method:'POST',body:data}); $('formMessage').textContent=`پروژه ثبت شد: ${result.id.slice(0,8)}`; $('formMessage').classList.add('success'); showActiveJob(result.id); await refreshJobs(); $('activeJobPanel').scrollIntoView({behavior:'smooth',block:'start'}); }
    catch(error) { $('formMessage').textContent=error.message; $('formMessage').classList.add('error'); $('createButton').disabled=false; }
    finally { $('createButton').querySelector('span').textContent='ساخت ویدئوی متحرک'; }
  });
  processHashToken(); updateVoices(); updateAudioMode(); updateClothingMode(); updateOnepieceAvailability();
  refreshStatus().then(data=>{if(data){$('tokenPanel').classList.add('hidden');refreshJobs();}else revealTokenPanel();});
})();
