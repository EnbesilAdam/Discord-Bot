# ❄️ Winter Hyacinth Bot

<p align="center">
  <img src="https://i.imgur.com/jlevP0F.jpeg" alt="Winter Hyacinth Banner" width="600"/>
</p>

**Winter Hyacinth Bot**, yazılım ve oyun geliştirme süreçlerinizi Discord topluluğunuzla anlık olarak buluşturan, gelişmiş yapay zeka ve otomatik takip sistemlerine sahip modern bir sunucu asistanıdır.

---

## 🚀 Öne Çıkan Özellikler

* **🤖 Hyacinth AI Debugger:** 
  * Gemini API altyapısı ile özel debug ve yazılım destek odaları oluşturur. 
  * 10 dakika hareketsizlik durumunda otomatik kanal kapatma, eşzamanlı kilit (`Semaphore`) yönetimi ve `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-1.5-flash` modelleri arasında otomatik yedekli geçiş (fallback) desteği sunar.

* **📦 Otomatik Kullanıcı & Repo Takibi (GitHub User Events):** 
  * Sabit liste sınırlaması olmadan, belirlediğiniz kullanıcının (`EnbesilAdam`) **tüm public repolarını** otomatik izler. 
  * **Yeni Repo Açılışı:** Sıfırdan public repo oluşturulduğunda (`CreateEvent`) özel mor kapak kartıyla duyuru geçer.
  * **Kod Güncellemeleri:** Kod push edildiğinde (`PushEvent`) commit mesajı ve detaylı inceleme linkiyle anlık bildirim düşer.

* **✍️ Otomatik Devlog Senkronizasyonu:** 
  * Gist JSON akışını düzenli aralıklarla tarar ve web sitenizde yeni bir geliştirici günlüğü (devlog) yayınlandığında görselleriyle birlikte `@everyone` duyurusu yapar.

* **🎫 Gelişmiş Bilet & Destek Sistemi (Support Tickets):** 
  * Kullanıcılar tek tıkla özel destek kanalı açabilir. Yetkili üstlenme (Claim) ve bilet kapatıldığında tüm sohbet geçmişini `.txt` transkripti olarak log kanalına arşivleme özelliğine sahiptir.

* **💼 Entegre Başvuru & Kariyer Paneli:** 
  * Dropdown menü üzerinden ekibe katılmak isteyen adaylar için önceden şablonu hazırlanmış Gmail başvuru bağlantısı oluşturur.

* **📊 Canlı Sistem Intelligence (`/info`):** 
  * Sunucu üye sayısı, rol/kanal sayıları, anlık bot gecikmesi (latency), canlı Uptime süresi, izlenen kullanıcı ve aktif AI oturumlarını dinamik olarak listeler.

---

## ⚙️ Hızlı Kurulum

Botu yerel makinenizde veya VDS/VPS sunucunuzda çalıştırmak için aşağıdaki adımları izleyebilirsiniz:

### 1. Kütüphaneleri Yükleyin
Gerekli asenkron Python paketlerini terminaliniz üzerinden kurun:

pip install discord.py python-dotenv aiohttp

### 2..env Dosyası Oluşturun
Proje ana dizininde .env adında bir dosya oluşturup API anahtarlarınızı tanımlayın:

DISCORD_BOT_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_personal_access_token_optional

3. Botu Başlatın

python3 botyeni.py

-|[###] Slash (/) Komut Rehberi [###]|-

<div class="command-table-container">
    <table class="command-table">
        <thead>
            <tr>
                <th>Komut</th>
                <th>Yetki</th>
                <th>Açıklama</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><code class="command-name">/ai</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Gemini AI modeline hızlıca soru sorarsınız.</td>
            </tr>
            <tr>
                <td><code class="command-name">/avatar</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Bir üyenin profil fotoğrafını büyük gösterir.</td>
            </tr>
            <tr>
                <td><code class="command-name">/ban</code></td>
                <td><span class="permission-badge permission-admin">Ban Members</span></td>
                <td>Bir üyeyi sunucudan yasaklar.</td>
            </tr>
            <tr>
                <td><code class="command-name">/clear</code></td>
                <td><span class="permission-badge permission-manage">Manage Messages</span></td>
                <td>Belirtilen miktarda mesajı siler.</td>
            </tr>
            <tr>
                <td><code class="command-name">/help</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Tüm komutları ve özellikleri gösterir.</td>
            </tr>
            <tr>
                <td><code class="command-name">/info</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Winter Hyacinth sunucusu ve bot hakkında bilgi verir.</td>
            </tr>
            <tr>
                <td><code class="command-name">/kick</code></td>
                <td><span class="permission-badge permission-admin">Kick Members</span></td>
                <td>Bir üyeyi sunucudan atar.</td>
            </tr>
            <tr>
                <td><code class="command-name">/ping</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Botun gecikme süresini ve API hızını gösterir.</td>
            </tr>
            <tr>
                <td><code class="command-name">/poll</code></td>
                <td><span class="permission-badge permission-manage">Manage Messages</span></td>
                <td>Reaksiyonlu bir anket oluşturur.</td>
            </tr>
            <tr>
                <td><code class="command-name">/setup</code></td>
                <td><span class="permission-badge permission-admin">Administrator</span></td>
                <td>Winter Hyacinth destek ve kariyer panelini gönderir.</td>
            </tr>
            <tr>
                <td><code class="command-name">/slowmode</code></td>
                <td><span class="permission-badge permission-manage">Manage Channels</span></td>
                <td>Kanalın yavaş modunu ayarlar (0 = kapalı).</td>
            </tr>
            <tr>
                <td><code class="command-name">/ticket</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Destek bilet odası açar.</td>
            </tr>
            <tr>
                <td><code class="command-name">/ticketadd</code></td>
                <td><span class="permission-badge permission-manage">Staff</span></td>
                <td>Ticket odasına bir üye ekler.</td>
            </tr>
            <tr>
                <td><code class="command-name">/ticketremove</code></td>
                <td><span class="permission-badge permission-manage">Staff</span></td>
                <td>Ticket odasından bir üyeyi çıkarır.</td>
            </tr>
            <tr>
                <td><code class="command-name">/timeout</code></td>
                <td><span class="permission-badge permission-manage">Moderate Members</span></td>
                <td>Bir üyeyi süreli susturur.</td>
            </tr>
            <tr>
                <td><code class="command-name">/untimeout</code></td>
                <td><span class="permission-badge permission-manage">Moderate Members</span></td>
                <td>Bir üyenin susturmasını kaldırır.</td>
            </tr>
            <tr>
                <td><code class="command-name">/userinfo</code></td>
                <td><span class="permission-badge">Herkes</span></td>
                <td>Bir üyenin profil bilgilerini gösterir.</td>
            </tr>
        </tbody>
    </table>
</div>
