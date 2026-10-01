# نشر التطبيق على الإنترنت (Link حقيقي مو localhost)

الهدف: رابط مثل `https://fraud-agent.onrender.com` يفتحه أي شخص من أي مكان.

---

## قبل النشر (لحظات)

1. ✅ `.env` بـ `.gitignore` (تأكدنا — ما ينرفع أبداً)
2. ✅ `render.yaml` موجود (إعدادات النشر)
3. ✅ الكود يشتغل بدون مفتاح Gemini (الوضع `template`)
4. ⚠️ قاعدة البيانات SQLite على المنصة المجانية **مؤقتة** (تنمسح إذا سكّر الموقع فترة) — الديمو يشتغل لأن البيانات تُحمّل تلقائياً عند أول تشغيل

---

## الخطوات (حوالي 10 دقائق)

### 1. ارفعي الكود على GitHub
```powershell
cd "C:\Fraud & Scam Protection Agent"
git add .
git commit -m "T5: web UI + deploy config"
git remote add origin https://github.com/USERNAME/fraud-agent.git
git push -u origin main
```
(إنتِ اللي تسوين الـ commits — هذا قاعدة المشروع)

### 2. سجّلي بـ Render
- افتحي https://render.com → Sign up (مجاني، بالـ GitHub أسهل)

### 3. أنشئي خدمة جديدة
- New → **Web Service** → اختر الريبو
- الاسم: `fraud-protection-agent`
- Runtime: **Python**
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
- اضغط **Create Web Service**

### 4. انتظري 3–5 دقائق
- أول تشغيل يحمّل تلقائياً `pip` + بيانات dev (30 مستخدم)
- لما يكتب **Live** → الرابط جاهز

### 5. الرابط النهائي
`https://fraud-agent.onrender.com` (أو أي اسم اخترتيه)

---

## ملاحظات مهمة

1. **الرابط ينمسح إذا الديمو سكّرت أسبوع** (Render المجاني يوقف الخدمة). تنشغلينها مرة ثانية بضغطة **Manual Deploy**
2. **بدون مفتاح Gemini:** الواجهة والكشف يشتغلون بالكامل (قوالب)، والرسائل `قالب`
3. **البيانات المعزولة** `data/test_sealed/` موجودة بالريبو بس النظام **ما يقرأها** إلا بأمر `--final` — آمن
4. **بدون نشر ممكن عرض مؤقت:** `ngrok http 8000` (رابط عام لمدة ساعة)

---

## خيارات ثانية

| المنصة | مجاني | صعوبة |
|--------|-------|-------|
| **Render** (موصى به) | ✅ | سهلة |
| Railway | ✅ حد | سهلة |
| Fly.io | ✅ حد | متوسط |
| حساب VPS (DigitalOcean) | ❌ $5/شهر | صعبة |

---

## تحقق بعد النشر

1. افتحي الرابط → لازم تشوفين واجهة المحفظة
2. اختاري مستخدم → سيناريو جائزة → التحويل → لازم يظهر تحذير شديد
3. سجّلي → لازم يبين الاختيار
