// JavaScript للشاشة الرئيسية
const API_BASE = '';

// تحميل المستخدمين
async function loadUsers() {
  try {
    const res = await fetch(`${API_BASE}/api/users`);
    const data = await res.json();
    const select = document.getElementById('userSelect');
    select.innerHTML = '<option value="">-- اختر مستخدم --</option>';
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

// تطبيق سيناريو جاهز
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
      if (payload.user_id) {
        document.getElementById('userSelect').value = payload.user_id;
      }
      if (payload.transaction) {
        const tx = payload.transaction;
        document.getElementById('recipientId').value = tx.recipient_id || '';
        document.getElementById('amount').value = tx.amount_iqd || '';
        document.getElementById('note').value = tx.note || '';
        document.getElementById('contextMessage').value = tx.context_message || '';
        if (tx.recipient_age_days) {
          document.getElementById('recipientAge').value = tx.recipient_age_days;
        }
      }
    });
}

// إرسال النموذج
async function submitTransfer(event) {
  event.preventDefault();

  const userId = document.getElementById('userSelect').value;
  const recipientId = document.getElementById('recipientId').value;
  const amount = parseInt(document.getElementById('amount').value);
  const note = document.getElementById('note').value;
  const contextMessage = document.getElementById('contextMessage').value;
  const recipientAge = document.getElementById('recipientAge').value;

  if (!userId || !recipientId || !amount) {
    alert('يرجى ملء جميع الحقول المطلوبة');
    return;
  }

  const payload = {
    user_id: userId,
    transaction: {
      amount_iqd: amount,
      recipient_id: recipientId,
      tx_type: 'transfer',
      note: note || undefined,
      context_message: contextMessage || undefined,
    }
  };

  if (recipientAge) {
    payload.transaction.recipient_age_days = parseInt(recipientAge);
  }

  try {
    const res = await fetch(`${API_BASE}/api/assess`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (data.decision === 'allow') {
      showSuccess(data);
    } else {
      showWarning(data);
    }
  } catch (err) {
    alert('حدث خطأ: ' + err.message);
  }
}

// عرض رسالة النجاح
function showSuccess(data) {
  const el = document.getElementById('successMessage');
  el.textContent = `✓ العملية آمنة — ${data.coaching_message}`;
  el.classList.add('active');
  document.getElementById('warningModal').classList.remove('active');
}

// عرض نافذة التحذير
function showWarning(data) {
  const modal = document.getElementById('warningModal');
  const badge = document.getElementById('decisionBadge');
  const reasonsList = document.getElementById('reasonsList');
  const coachingMsg = document.getElementById('coachingMessage');
  const coachingSource = document.getElementById('coachingSource');
  const warningText = document.getElementById('warningText');
  const holdCheckbox = document.getElementById('holdCheckbox');
  const continueBtn = document.getElementById('continueBtn');
  const countdown = document.getElementById('countdown');

  // حفظ tx_id
  document.getElementById('txId').value = data.tx_id;

  // شارة القرار
  badge.className = `decision-badge ${data.decision}`;
  badge.textContent = data.decision === 'hold' ? '⚠ تحذير شديد' : '⚠ تنبيه';

  // الأسباب
  reasonsList.innerHTML = '';
  data.reasons.forEach(r => {
    const li = document.createElement('li');
    li.textContent = r.text_ar;
    reasonsList.appendChild(li);
  });

  // رسالة التوعية
  coachingMsg.textContent = data.coaching_message;
  coachingSource.textContent = `المصدر: ${data.coaching_source === 'llm' ? 'LLM' : 'قالب'}`;

  // نص التحذير
  warningText.textContent = 'العملية لم تكتمل بعد';

  // حالة hold
  if (data.decision === 'hold') {
    holdCheckbox.style.display = 'flex';
    continueBtn.disabled = true;
    countdown.style.display = 'block';

    // عداد تنازلي
    let seconds = data.hold_seconds || 10;
    countdown.textContent = `انتظر ${seconds} ثانية...`;

    const timer = setInterval(() => {
      seconds--;
      if (seconds <= 0) {
        clearInterval(timer);
        countdown.textContent = '';
        continueBtn.disabled = false;
      } else {
        countdown.textContent = `انتظر ${seconds} ثانية...`;
      }
    }, 1000);
  } else {
    holdCheckbox.style.display = 'none';
    countdown.style.display = 'none';
    continueBtn.disabled = false;
  }

  modal.classList.add('active');
}

// إرسال اختيار المستخدم
async function submitChoice(choice) {
  const txId = document.getElementById('txId').value;
  const recipientId = document.getElementById('recipientId').value;

  try {
    const res = await fetch(`${API_BASE}/api/choice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tx_id: txId,
        choice: choice,
        recipient_id: recipientId
      })
    });

    const data = await res.json();
    document.getElementById('warningModal').classList.remove('active');

    if (choice === 'continue') {
      alert('تم إكمال التحويل. ' + data.message_ar);
    } else {
      alert('تم إلغاء التحويل.');
    }
  } catch (err) {
    alert('حدث خطأ: ' + err.message);
  }
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
  } catch (err) {
    console.error('خطأ بتحميل النتائج:', err);
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

// تهيئة الصفحة
document.addEventListener('DOMContentLoaded', () => {
  loadUsers();
  loadDemoScenarios();

  // النموذج
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
      const checkbox = document.getElementById('holdCheckboxInput');
      if (checkbox && !checkbox.checked) {
        alert('يرجى تأكيد فهم المخاطرة');
        return;
      }
      submitChoice('continue');
    });
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
