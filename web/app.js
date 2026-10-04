// JavaScript للواجهة — محفظة Zain Cash (محاكاة) + الكشف والتوعية
const API_BASE = '';

// السيناريوهات الجاهزة قديمة بـ r_xxx — نحوّلها لرقم محفظة عند التطبيق
const DEMO_MSISDN = {
  r_known: '07811110000',
  r_scam1: '07899990001',
  r_scam2: '07899990002',
};

let countdownTimer = null;   // عداد فترة التهدئة (يُنظّف عند كل نافذة)
let currentDecision = null;  // قرار آخر نافذة مفتوحة (للتمييز بين hold و warn)
let choiceRecipient = '';    // المستلم اللي ينرسل مع /api/choice (محفظة أو نص حر)
let lastScenarioText = '';   // آخر نص مُرسل (لتكميل الإجابة على السؤال)
let currentChatTxId = '';    // معاملة مربع الحوار الحالي (T11)

function recipientToMsisdn(id) {
  const raw = String(id || 'demo');
  if (/^07\d{9}$/.test(raw)) return raw;
  if (DEMO_MSISDN[raw]) return DEMO_MSISDN[raw];
  let h = 7;
  for (const c of raw) h = (h * 31 + c.charCodeAt(0)) % 1000000000;
  return '078' + String(h).padStart(8, '0');
}

// تحميل المستخدمين
async function loadUsers() {
  try {
    const res = await fetch(`${API_BASE}/api/users`);
    const data = await res.json();
    const select = document.getElementById('userSelect');
    select.innerHTML = '<option value="">-- بدون حساب (مستخدم جديد) --</option>';
    data.users.forEach(u => {
      const option = document.createElement('option');
      option.value = u.user_id;
      option.textContent = `${u.name || u.user_id} (${u.archetype || ''})`;
      select.appendChild(option);
    });
  } catch (err) {
    console.error('خطأ بتحميل المستخدمين:', err);
  }
}

// تحميل السيناريوهات الجاهزة
async function loadDemoScenarios() {
  try {
    const res = await fetch(`${API_BASE}/api/demo_scenarios`);
    const data = await res.json();
    const select = document.getElementById('demoSelect');
    select.innerHTML = '<option value="">-- جرّب سيناريو جاهز --</option>';
    data.scenarios.forEach(s => {
      const option = document.createElement('option');
      option.value = s.id;
      option.textContent = s.name_ar;
      select.appendChild(option);
    });
  } catch (err) {
    console.error('خطأ بتحميل السيناريوهات:', err);
  }
}

// تطبيق سيناريو جاهز (نص حر / تاريخ يدوي / محفظة)
function applyDemoScenario() {
  const select = document.getElementById('demoSelect');
  const id = select.value;
  if (!id) return;

  fetch(`${API_BASE}/api/demo_scenarios`)
    .then(res => res.json())
    .then(data => {
      const scenario = data.scenarios.find(s => s.id === id);
      if (!scenario) return;

      const payload = scenario.payload;

      // نص حر (T10): نملأ الصندوق ونفحصه فوراً
      if (payload.text) {
        document.getElementById('scenarioText').value = payload.text;
        submitScenarioText();
        return;
      }

      // تاريخ يدوي — احتيال بطيء (T10): يُرسل مباشرة على /api/scenario
      if (payload.history) {
        postScenario(payload);
        return;
      }

      // محفظة: نملأ حقول التحويل
      if (payload.user_id) {
        document.getElementById('userSelect').value = payload.user_id;
      }
      if (payload.transaction) {
        const tx = payload.transaction;
        document.getElementById('recipientMsisdn').value = recipientToMsisdn(tx.recipient_id);
        document.getElementById('amount').value = tx.amount_iqd || '';
        document.getElementById('note').value = tx.note || '';
        document.getElementById('contextMessage').value = tx.context_message || '';
        document.getElementById('recipientAge').value = tx.recipient_age_days || '';
      }
    });
}

// إرسال سيناريو ذو تاريخ يدوي على /api/scenario (شكل ب من قسم 14.1)
async function postScenario(payload) {
  try {
    const res = await fetch(`${API_BASE}/api/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      alert(typeof data.detail === 'string' ? data.detail : 'مدخل غير صالح — راجع السيناريو');
      return;
    }
    choiceRecipient = (payload.transaction && payload.transaction.recipient_id) || '';
    document.getElementById('successMessage').classList.remove('active');
    if (data.decision === 'allow') {
      showSuccess(data);
    } else {
      showWarning(data);  // نفس نافذة التحذير: أسباب + توعية + اختيار
    }
  } catch (err) {
    alert('حدث خطأ: ' + err.message);
  }
}

// إرسال طلب التحويل إلى المحفظة (يعترضه الوكيل قبل التنفيذ)
async function submitTransfer(event) {
  event.preventDefault();

  const sender = document.getElementById('senderMsisdn').value.trim();
  const recipient = document.getElementById('recipientMsisdn').value.trim();
  const amount = parseInt(document.getElementById('amount').value, 10);
  const pin = document.getElementById('pin').value.trim();
  const userId = document.getElementById('userSelect').value;
  const note = document.getElementById('note').value.trim();
  const contextMessage = document.getElementById('contextMessage').value.trim();
  const recipientAge = document.getElementById('recipientAge').value;

  if (!sender || !recipient || !amount || !pin) {
    alert('يرجى ملء رقم المستلم والمبلغ والرمز السري');
    return;
  }
  if (!/^07\d{9}$/.test(sender) || !/^07\d{9}$/.test(recipient)) {
    alert('رقم المحفظة لازم 11 رقم يبدأ بـ 07');
    return;
  }
  if (!/^\d{4,6}$/.test(pin)) {
    alert('الرمز السري 4 إلى 6 أرقام');
    return;
  }

  const payload = {
    sender_msisdn: sender,
    recipient_msisdn: recipient,
    amount_iqd: amount,
    pin: pin,
    note: note || undefined,
    context_message: contextMessage || undefined,
    use_llm: true,
  };
  choiceRecipient = recipient;
  if (userId) payload.user_id = userId;
  if (recipientAge) payload.recipient_age_days = parseInt(recipientAge, 10);

  try {
    const res = await fetch(`${API_BASE}/api/wallet/transfer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      alert(typeof data.detail === 'string' ? data.detail : 'مدخل غير صالح — راجع الحقول');
      return;
    }

    document.getElementById('successMessage').classList.remove('active');

    if (data.status === 'executed') {
      showReceipt({ receipt: data.receipt, coaching_message: data.coaching_message });
    } else {
      showWarning(data);
    }
  } catch (err) {
    alert('حدث خطأ: ' + err.message);
  }
}

// عرض الإيصال بعد نجاح التحويل
function showReceipt(data) {
  const el = document.getElementById('successMessage');
  el.textContent = '';

  const head = document.createElement('div');
  head.textContent = '✓ تم التحويل بنجاح — Zain Cash';

  const r = data.receipt || {};
  const line = document.createElement('div');
  line.className = 'receipt-line';
  const amount = Number(r.amount_iqd || 0).toLocaleString('en-US');
  line.textContent = `رقم الإيصال: ${r.receipt_id || '—'} · ${amount} د.ع · إلى ${r.recipient_msisdn_masked || ''}`;

  const coach = document.createElement('div');
  coach.className = 'receipt-coach';
  coach.textContent = data.coaching_message || '';

  el.append(head, line, coach);
  el.classList.add('active');
  document.getElementById('warningModal').classList.remove('active');
}

// عرض رسالة نجاح بدون إيصال (مسار /api/assess)
function showSuccess(data) {
  const el = document.getElementById('successMessage');
  el.textContent = `✓ العملية آمنة — ${data.coaching_message}`;
  el.classList.add('active');
  document.getElementById('warningModal').classList.remove('active');
}

// عرض نافذة التحذير + فترة التهدئة (10 ثواني لـ warn و hold بالمحفظة)
function showWarning(data) {
  const modal = document.getElementById('warningModal');
  const badge = document.getElementById('decisionBadge');
  const reasonsList = document.getElementById('reasonsList');
  const coachingMsg = document.getElementById('coachingMessage');
  const coachingSource = document.getElementById('coachingSource');
  const warningText = document.getElementById('warningText');
  const holdCheckbox = document.getElementById('holdCheckbox');
  const holdInput = document.getElementById('holdCheckboxInput');
  const continueBtn = document.getElementById('continueBtn');
  const countdown = document.getElementById('countdown');

  // حفظ tx_id
  document.getElementById('txId').value = data.tx_id;
  currentDecision = data.decision;
  if (holdInput) holdInput.checked = false;

  // مربع الحوار (T11): نبدأ جلسة جديدة مع كل نافذة
  currentChatTxId = data.tx_id;
  const chatLog = document.getElementById('chatLog');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');
  if (chatLog) chatLog.innerHTML = '';
  if (chatInput) { chatInput.value = ''; chatInput.disabled = false; }
  if (chatSendBtn) chatSendBtn.disabled = false;

  // شارة القرار
  badge.className = `decision-badge ${data.decision}`;
  badge.textContent = data.decision === 'hold' ? '⚠ تحذير شديد' : '⚠ تنبيه';

  // الأسباب
  reasonsList.innerHTML = '';
  (data.reasons || []).forEach(r => {
    const li = document.createElement('li');
    li.textContent = r.text_ar;
    reasonsList.appendChild(li);
  });

  // رسالة التوعية
  coachingMsg.textContent = data.coaching_message;
  coachingSource.textContent = `المصدر: ${data.coaching_source === 'llm' ? 'LLM' : 'قالب'}`;

  // نص التحذير
  warningText.textContent = 'العملية لم تكتمل بعد';

  // مربع "فهمت المخاطرة" بس بحالة hold
  holdCheckbox.style.display = data.decision === 'hold' ? 'flex' : 'none';

  // فترة التهدئة: cooling_off_seconds (محفظة) أو hold_seconds (مسار assessment)
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  let seconds = Number(data.cooling_off_seconds ?? data.hold_seconds ?? 0);
  if (seconds > 0) {
    continueBtn.disabled = true;
    countdown.style.display = 'block';
    countdown.textContent = `التحويل معلّق — فترة تهدئة ${seconds} ثانية...`;
    countdownTimer = setInterval(() => {
      seconds -= 1;
      if (seconds <= 0) {
        clearInterval(countdownTimer);
        countdownTimer = null;
        countdown.textContent = 'انتهت فترة التهدئة — تكدر تختار الحين';
        continueBtn.disabled = false;
      } else {
        countdown.textContent = `التحويل معلّق — فترة تهدئة ${seconds} ثانية...`;
      }
    }, 1000);
  } else {
    countdown.style.display = 'none';
    continueBtn.disabled = false;
  }

  modal.classList.add('active');
}

// إرسال اختيار المستخدم (continue ينفّذ التحويل المعلّق / cancel يلغية)
async function submitChoice(choice) {
  const txId = document.getElementById('txId').value;

  try {
    const res = await fetch(`${API_BASE}/api/choice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tx_id: txId,
        choice: choice,
        recipient_id: choiceRecipient || undefined
      })
    });

    const data = await res.json();
    if (!res.ok) {
      alert(typeof data.detail === 'string' ? data.detail : 'حدث خطأ بالخادم');
      return;
    }

    document.getElementById('warningModal').classList.remove('active');
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }

    if (choice !== 'continue') {
      alert('تم إلغاء التحويل. ما اننفّذ أي عملية.');
      return;
    }
    if (data.receipt) {
      showReceipt({ receipt: data.receipt, coaching_message: data.message_ar });
    } else {
      showSuccess({ coaching_message: data.message_ar });
    }
  } catch (err) {
    alert('حدث خطأ: ' + err.message);
  }
}

// ------------------------------------------- سيناريو من الحكم: نص حر (T6)
// يعرض السؤال التوضيحي أو رسالة آمنة داخل الصندوق
function showIntakeNotice(message, isError) {
  const box = document.getElementById('clarifyBox');
  const answerRow = document.getElementById('clarifyAnswerRow');
  if (!box) return;
  if (!message) {
    box.style.display = 'none';
    box.classList.remove('error');
    return;
  }
  box.style.display = 'block';
  box.classList.toggle('error', !!isError);
  document.getElementById('clarifyQuestion').textContent = message;
  if (answerRow) answerRow.style.display = isError ? 'none' : 'flex';
}

function handleScenarioResponse(data) {
  if (data.status !== 'assessed') {
    // needs_clarification: سؤال واحد — نعرضه وتكمل المستخدمة بالإجابة
    // cannot_parse: رسالة آمنة بالعربي (ما ننهار مع أي مدخل غريب)
    const isError = data.status !== 'needs_clarification';
    showIntakeNotice(data.message_ar || 'صارت مشكلة بسيطة، جرّب مرة ثانية.', isError);
    return;
  }
  showIntakeNotice('', false);
  const a = data.assessment;
  choiceRecipient = (data.extracted && data.extracted.recipient_id) || '';
  document.getElementById('successMessage').classList.remove('active');
  if (a.decision === 'allow') {
    showSuccess(a);
  } else {
    showWarning(a);  // نفس نافذة التحذير: أسباب + توعية + 10 ثواني hold + اختيار
  }
}

async function postScenarioText(text) {
  lastScenarioText = text;
  try {
    const res = await fetch(`${API_BASE}/api/scenario_text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, use_llm: true })    });
    const data = await res.json();
    if (!res.ok) {
      showIntakeNotice(
        typeof data.detail === 'string' ? data.detail : 'مدخل غير صالح — راجع النص (أقصى 2000 حرف).',
        true);
      return;
    }
    handleScenarioResponse(data);
  } catch (err) {
    showIntakeNotice('تعذر الاتصال بالخادم: ' + err.message, true);
  }
}

async function submitScenarioText() {
  const text = document.getElementById('scenarioText').value.trim();
  if (!text) {
    showIntakeNotice('اكتب النص أولاً أو الصق البيانات كـ JSON.', true);
    return;
  }
  if (text.length > 2000) {
    showIntakeNotice('النص طويل: أقصى 2000 حرف.', true);
    return;
  }
  await postScenarioText(text);
}

async function submitClarifyAnswer() {
  const answer = document.getElementById('clarifyAnswer').value.trim();
  if (!answer) {
    alert('اكتب إجابتك أولاً');
    return;
  }
  const combined = lastScenarioText + '\n' + answer;
  document.getElementById('scenarioText').value = combined;
  await postScenarioText(combined);
}

// تحميل السجل
async function loadLog() {
  try {
    const res = await fetch(`${API_BASE}/api/log?limit=100`);
    const data = await res.json();
    const tbody = document.getElementById('logTableBody');
    tbody.innerHTML = '';

    data.rows.forEach(row => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.created_at || ''}</td>
        <td>${row.user_id || ''}</td>
        <td>${row.risk_score ?? ''}</td>
        <td>${row.decision || ''}</td>
        <td>${row.matched_pattern || ''}</td>
        <td>${row.user_choice || ''}</td>
        <td>${row.final_status || ''}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('خطأ بتحميل السجل:', err);
  }
}

// تحميل نتائج التقييم
async function loadResults() {
  try {
    const res = await fetch(`${API_BASE}/api/eval`);
    const data = await res.json();

    if (!data.available) {
      document.getElementById('resultsContent').innerHTML = '<p>لا توجد نتائج تقييم بعد.</p>';
      await loadFailureModes();  // حالات الفشل (T7) تظهر حتى بدون نتائج تقييم
      return;
    }

    const results = data.results;
    const metrics = results.metrics || {};

    let html = '<div class="metrics-grid">';

    // المؤشرات الرئيسية
    if (metrics.any_alert) {
      html += `
        <div class="metric-card">
          <div class="value">${(metrics.any_alert.recall * 100).toFixed(1)}%</div>
          <div class="label">Recall</div>
        </div>
        <div class="metric-card">
          <div class="value">${(metrics.any_alert.precision * 100).toFixed(1)}%</div>
          <div class="label">Precision</div>
        </div>
        <div class="metric-card">
          <div class="value">${(metrics.any_alert.fpr * 100).toFixed(1)}%</div>
          <div class="label">FPR</div>
        </div>
        <div class="metric-card">
          <div class="value">${results.n_transactions || 0}</div>
          <div class="label">المعاملات</div>
        </div>
      `;
    }

    html += '</div>';

    // مصفوفة الالتباس
    if (metrics.any_alert) {
      const m = metrics.any_alert;
      html += `
        <h3>مصفوفة الالتباس</h3>
        <table class="log-table">
          <tr>
            <th></th>
            <th>متوقع: احتيال</th>
            <th>متوقع: بريء</th>
          </tr>
          <tr>
            <td><b>تنبيه</b></td>
            <td>TP: ${m.tp}</td>
            <td>FP: ${m.fp}</td>
          </tr>
          <tr>
            <td><b>لا تنبيه</b></td>
            <td>FN: ${m.fn}</td>
            <td>TN: ${m.tn}</td>
          </tr>
        </table>
      `;
    }

    document.getElementById('resultsContent').innerHTML = html;
    await loadFailureModes();  // جدول حالات الفشل (T7) تحت جدول التقييم
  } catch (err) {
    console.error('خطأ بتحميل النتائج:', err);
  }
}

// حالات الفشل الستة (T7) — من docs/failure_modes_run.json عبر /api/failure_modes
async function loadFailureModes() {
  try {
    const res = await fetch(`${API_BASE}/api/failure_modes`);
    const data = await res.json();
    const box = document.getElementById('resultsContent');
    if (!box) return;

    if (!data.available || !data.cases || !data.cases.length) {
      box.insertAdjacentHTML('beforeend',
        '<h3>حالات الفشل (T7)</h3>' +
        '<p style="font-size:0.85rem;">ماكو نتائج بعد. شغلي: ' +
        '<code>python -m src.eval.failure_modes</code></p>');
      return;
    }

    let rows = '';
    for (const c of data.cases) {
      rows += `
        <tr>
          <td><b>${c.id}</b></td>
          <td>${c.title_ar}</td>
          <td>${c.result.decision}</td>
          <td>${c.result.score}</td>
          <td>${c.verdict_ar}</td>
        </tr>`;
    }
    box.insertAdjacentHTML('beforeend', `
      <h3>حالات الفشل (T7)</h3>
      <p style="font-size:0.85rem; opacity:0.85;">
        النتيجة الفعلية لستة سيناريوهات ثابتة — بدون تجميل.
        الشرح الكامل والأسباب بـ <code>docs/failure_modes.md</code>.
      </p>
      <table class="log-table">
        <tr><th>الحالة</th><th>الوصف</th><th>القرار</th><th>النقاط</th><th>الحكم</th></tr>
        ${rows}
      </table>`);
  } catch (err) {
    console.error('خطأ بتحميل حالات الفشل:', err);
  }
}

// تصدير السجل
async function exportLog() {
  try {
    const res = await fetch(`${API_BASE}/api/log/export`);
    const data = await res.json();
    alert(`تم تصدير ${data.rows} سجل إلى:\n${data.jsonl_path}\n${data.csv_path}`);
  } catch (err) {
    alert('حدث خطأ: ' + err.message);
  }
}

// ----------------------------------------------------------------- حوار (T11)
function appendChatBubble(text, who) {
  const log = document.getElementById('chatLog');
  if (!log) return;
  const div = document.createElement('div');
  div.className = `chat-msg ${who}`;
  div.textContent = text;   // نص فقط: أي HTML بالرد يظهر كنص (XSS)
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const message = input ? input.value.trim() : '';
  if (!message || !currentChatTxId) return;
  if (input) input.value = '';
  appendChatBubble(message, 'user');
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tx_id: currentChatTxId,
        message: message,
        use_llm: true   // LLM إن كان مفعّل، وإلا الرد الجاهز
      })
    });
    const data = await res.json();
    if (!res.ok) {
      appendChatBubble(
        typeof data.detail === 'string' ? data.detail : 'صار خطأ بسيط بالحوار.',
        'bot'
      );
      return;
    }
    appendChatBubble(data.reply_ar, 'bot');
    if (data.limit_reached && input) {
      // خلصت الرسائل (5): نقفل الإدخال — القرار يبقى للمستخدم
      input.disabled = true;
      const btn = document.getElementById('chatSendBtn');
      if (btn) btn.disabled = true;
    }
  } catch (err) {
    appendChatBubble('ماگدرت أوصل للخادم — جرّب بعد شوية.', 'bot');
  }
}

// ----------------------------------------------------------------- تدريب (T12)
let trainingState = null;  // {scenario_id, total, answers: []} — حالة بالصفحة فقط

function appendTrainingBubble(text, who) {
  const log = document.getElementById('trainingLog');
  if (!log) return null;
  const div = document.createElement('div');
  div.className = `chat-msg ${who}`;
  div.textContent = text;   // نص فقط: أي HTML يظهر كنص (XSS)
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function setTrainingBusy(busy) {
  ['flagBtn', 'trainingContinueBtn'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = busy;
  });
}

function showTrainingResult(ev) {
  const box = document.getElementById('trainingResult');
  const score = document.getElementById('trainingScore');
  const verdict = document.getElementById('trainingVerdict');
  const feedback = document.getElementById('trainingFeedback');
  if (score) score.textContent = `${ev.correct} / ${ev.total}  (${ev.score_pct}%)`;
  if (verdict) verdict.textContent = ev.verdict_ar;
  if (feedback) feedback.textContent = ev.feedback_ar;
  if (box) box.style.display = 'block';
  const actions = document.getElementById('trainingActions');
  if (actions) actions.style.display = 'none';
  const startBtn = document.getElementById('trainingStartBtn');
  if (startBtn) {
    startBtn.textContent = 'تدريب جديد';
    startBtn.style.display = 'block';
  }
  trainingState = null;
}

async function startTraining() {
  const sel = document.getElementById('trainingSelect');
  const startBtn = document.getElementById('trainingStartBtn');
  const log = document.getElementById('trainingLog');
  const result = document.getElementById('trainingResult');
  if (log) log.innerHTML = '';
  if (result) result.style.display = 'none';
  if (startBtn) startBtn.style.display = 'none';
  try {
    const res = await fetch(`${API_BASE}/api/training/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: sel ? sel.value : 'fake_support',
        use_llm: true
      })
    });
    const data = await res.json();
    if (!res.ok) {
      appendTrainingBubble(
        typeof data.detail === 'string' ? data.detail : 'صار خطأ بسيط.', 'bot');
      if (startBtn) startBtn.style.display = 'block';
      return;
    }
    trainingState = {
      scenario_id: data.scenario_id,
      total: data.total_turns,
      answers: []
    };
    appendTrainingBubble(`📘 ${data.training_notice_ar}`, 'bot');
    appendTrainingBubble(data.line_ar, 'bot');
    const actions = document.getElementById('trainingActions');
    if (actions) actions.style.display = 'flex';
    setTrainingBusy(false);
  } catch (err) {
    appendTrainingBubble('ماگدرت أوصل للخادم — جرّب بعد شوية.', 'bot');
    if (startBtn) startBtn.style.display = 'block';
  }
}

async function answerTraining(action) {
  if (!trainingState) return;
  const bubble = appendTrainingBubble(
    action === 'flag' ? 'هذا احتيال' : 'أكمل', 'user');
  setTrainingBusy(true);
  const answers = [...trainingState.answers, action];  // تراكمي — بلا حالة بالخادم
  try {
    const res = await fetch(`${API_BASE}/api/training/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: trainingState.scenario_id,
        answers: answers,
        use_llm: true
      })
    });
    const data = await res.json();
    if (!res.ok) {
      if (bubble) bubble.remove();   // الفشل: نرجّع الحال كما كانت
      appendTrainingBubble(
        typeof data.detail === 'string' ? data.detail : 'صار خطأ بسيط.', 'bot');
      setTrainingBusy(false);
      return;
    }
    trainingState.answers = answers;
    if (data.status === 'finished' && data.evaluation) {
      showTrainingResult(data.evaluation);
    } else {
      appendTrainingBubble(data.line_ar, 'bot');
      setTrainingBusy(false);
    }
  } catch (err) {
    if (bubble) bubble.remove();
    appendTrainingBubble('ماگدرت أوصل للخادم — جرّب بعد شوية.', 'bot');
    setTrainingBusy(false);
  }
}

// تهيئة الصفحة
document.addEventListener('DOMContentLoaded', () => {
  loadUsers();
  loadDemoScenarios();

  // نموذج التحويل
  const form = document.getElementById('transferForm');
  if (form) {
    form.addEventListener('submit', submitTransfer);
  }

  // أزرار الاختيار
  const cancelBtn = document.getElementById('cancelBtn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => submitChoice('cancel'));
  }

  const continueBtn = document.getElementById('continueBtn');
  if (continueBtn) {
    continueBtn.addEventListener('click', () => {
      const holdWrap = document.getElementById('holdCheckbox');
      const checkbox = document.getElementById('holdCheckboxInput');
      const needConfirm = holdWrap && holdWrap.style.display !== 'none';
      if (needConfirm && checkbox && !checkbox.checked) {
        alert('يرجى تأكيد فهم المخاطرة');
        return;
      }
      submitChoice('continue');
    });
  }

  // سيناريو النص الحر (T6)
  const scenarioBtn = document.getElementById('scenarioTextBtn');
  if (scenarioBtn) {
    scenarioBtn.addEventListener('click', submitScenarioText);
  }

  const clarifyBtn = document.getElementById('clarifyBtn');
  if (clarifyBtn) {
    clarifyBtn.addEventListener('click', submitClarifyAnswer);
  }

  // مربع الحوار (T11)
  const chatSendBtn = document.getElementById('chatSendBtn');
  if (chatSendBtn) {
    chatSendBtn.addEventListener('click', sendChat);
  }
  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendChat();
    });
  }

  // وضع التدريب (T12)
  const trainingStartBtn = document.getElementById('trainingStartBtn');
  if (trainingStartBtn) {
    trainingStartBtn.addEventListener('click', startTraining);
  }
  const flagBtn = document.getElementById('flagBtn');
  if (flagBtn) {
    flagBtn.addEventListener('click', () => answerTraining('flag'));
  }
  const trainingContinueBtn = document.getElementById('trainingContinueBtn');
  if (trainingContinueBtn) {
    trainingContinueBtn.addEventListener('click', () => answerTraining('continue'));
  }

  // تحميل السجل إذا موجود
  if (document.getElementById('logTableBody')) {
    loadLog();
  }

  // تحميل النتائج إذا موجودة
  if (document.getElementById('resultsContent')) {
    loadResults();
  }
});
