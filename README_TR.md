# 📷 PCam - Uzak Kamera Sistemi

PCam, Android akıllı telefonunuzu bilgisayarınız için yüksek çözünürlüklü ve ultra düşük gecikmeli bir web kameraya dönüştüren taşınabilir ve tak-çalıştır bir uzak kamera uygulamasıdır.

Donanım hızlandırmalı H.264 video akışı sayesinde PCam; Zoom, Discord, Microsoft Teams, Skype, OBS Studio ve diğer görüntülü görüşme veya yayın platformlarına sorunsuz şekilde görüntü aktarabilir.

Sistem iki ana bileşenden oluşur:

* **PCam Masaüstü İstemcisi** (Python / Tkinter)
* **PCam Mobil Yayıncı** (Android / Jetpack Compose / MediaCodec)

---

## ✨ Özellikler

### 🚀 Kurulumsuz ve Taşınabilir

Masaüstü istemcisi tek bir çalıştırılabilir dosya olarak dağıtılır.

Kullanıcıların aşağıdakileri ayrıca kurmasına gerek yoktur:

* Python
* FFmpeg
* ADB

Gerekli tüm bileşenler paket içerisinde hazır olarak gelir.

### ⚡ Düşük Gecikmeli H.264 Altyapısı

* Donanım hızlandırmalı H.264 kodlama
* Optimize edilmiş görüntü aktarımı
* Düşük gecikme süresi
* Kararlı video yayını

### 🔗 Çift Bağlantı Desteği

#### Wi-Fi Modu

* mDNS ile otomatik cihaz keşfi
* Manuel IP girişi gerektirmez
* Tek tıkla bağlantı

#### USB Modu

* Otomatik ADB tünelleme
* Maksimum kararlılık
* En düşük gecikme süresi
* Yayın ve içerik üretimi için ideal

### 🔄 Uzaktan Kamera Kontrolü

Telefon kamerasını doğrudan masaüstü uygulamasından kontrol edebilirsiniz:

* Ön / arka kamera geçişi
* Flaş açma / kapatma
* Görüntü döndürme

### 🎭 Sanal Kamera Entegrasyonu

PCam, görüntüyü OBS Virtual Camera üzerinden aktararak telefonunuzu sistem tarafından tanınan bir web kamera haline getirir.

Desteklenen uygulamalar:

* Zoom
* Discord
* Microsoft Teams
* Skype
* Google Meet
* DirectShow destekleyen tüm uygulamalar

---

## 📦 Yayın Paketi Yapısı

Sıkıştırılmış dosya açıldığında aşağıdaki klasör yapısı oluşur:

```text
PCam/
│
├── PCam.exe
│
├── Binaries/
│   ├── ffmpeg.exe
│   ├── adb.exe
│   ├── AdbWinApi.dll
│   └── AdbWinUsbApi.dll
│
└── Images/
    └── PCam_logo.png
```

### Dahil Edilen Bileşenler

| Dosya            | Açıklama                   |
| ---------------- | -------------------------- |
| PCam.exe         | Ana masaüstü uygulaması    |
| ffmpeg.exe       | Dahili H.264 çözücü        |
| adb.exe          | Dahili Android USB köprüsü |
| AdbWinApi.dll    | ADB bağımlılığı            |
| AdbWinUsbApi.dll | ADB bağımlılığı            |
| PCam_logo.png    | Uygulama logosu            |

---

## 📱 Mobil Uygulamanın Kurulumu

1. `PCam-MobileApp.apk` dosyasını Android cihazınıza aktarın.
2. APK dosyasını kurun.
3. Gerekirse "Bilinmeyen Kaynaklardan Yükleme" izni verin.
4. Uygulamayı açın.
5. Kamera izinlerini onaylayın.

---

## 🔌 Cihaz Bağlantısı

### Seçenek A — Wi-Fi Bağlantısı

1. Telefon ve bilgisayarın aynı ağa bağlı olduğundan emin olun.
2. `PCam.exe` uygulamasını çalıştırın.
3. Durum göstergesinde aşağıdaki mesajı bekleyin:

```text
Cihazlar aranıyor...
```

4. Android uygulamasında yayın başlat düğmesine basın.
5. PCam cihazı mDNS üzerinden otomatik olarak bulacaktır.
6. Bağlantı kurulduğunda durum şu şekilde değişir:

```text
Bağlandı [Wi-Fi]
```

---

### Seçenek B — USB Bağlantısı (Önerilen)

1. Android cihazınızda **Geliştirici Seçenekleri**ni etkinleştirin.
2. **USB Hata Ayıklama** özelliğini açın.
3. Telefonu USB kablosu ile bilgisayara bağlayın.
4. Telefonda çıkan yetkilendirme penceresini onaylayın.
5. `PCam.exe` uygulamasını çalıştırın.

PCam otomatik olarak:

* Cihazı algılar
* ADB tünelini oluşturur
* Video aktarımını başlatır

Durum göstergesi:

```text
Bağlandı [USB]
```

---

## 🎭 Zoom, Discord ve Teams ile Kullanım

### OBS Studio Kurulumu

Bilgisayarınızda OBS Studio kurulu değilse yükleyin.

OBS, gerekli sanal kamera sürücülerini otomatik olarak kuracaktır.

### PCam'i Başlatın

1. Telefonu bağlayın.
2. Önizleme görüntüsünün geldiğini doğrulayın.

### Sanal Kamera Çıkışını Etkinleştirin

Ayarlar bölümündeki:

```text
Sanal Kameraya Gönder
```

seçeneğini aktif edin.

### OBS Virtual Camera'yı Seçin

Kullandığınız toplantı veya yayın uygulamasında:

1. Video ayarlarını açın.
2. Kamera olarak:

```text
OBS Virtual Camera
```

seçeneğini seçin.

Artık telefon kamerası sistem tarafından normal bir web kamera olarak kullanılacaktır.

---

## ⚙️ Sorun Giderme

### Yeşil Ekran veya Bozuk Görüntü

Kablosuz bağlantının kararsız olduğu durumlarda ilk H.264 ana kare (keyframe) parçalanmış şekilde gelebilir.

Eğer görüntü yeşil veya bozuk görünüyorsa:

1. Bir kez **Kamera Değiştir** düğmesine basın.
2. Android cihaz yeni bir ana kare oluşturacaktır.
3. Görüntü normale dönecektir.

---

### Geçici Bağlantı Kopmaları

PCam, bağlantının hemen kesilmesini önlemek için **4 saniyelik akıllı zaman aşımı mekanizması** kullanır.

Kısa süreli paket kayıplarında yayın sonlandırılmaz.

Maksimum kararlılık için USB modu önerilir.

---

### Windows Defender Uyarısı

PCam, PyInstaller kullanılarak tek bir çalıştırılabilir dosya halinde paketlendiği ve ticari bir dijital imza sertifikasına sahip olmadığı için Windows aşağıdaki uyarıyı gösterebilir:

```text
Windows bilgisayarınızı korudu
```

Bu durum bağımsız geliştiriciler tarafından dağıtılan uygulamalarda yaygın olarak görülen bir yanlış pozitif durumdur.

PCam:

* Açık kaynaklıdır
* Zararlı yazılım içermez
* Arka planda servis kurmaz
* Kapatıldığında tüm işlemleri temizler

---

## 👨‍💻 Yerel Geliştirme

### Gereksinimler

* Python 3.10+
* FFmpeg
* Android SDK Platform Tools (isteğe bağlı)

### Bağımlılıkları Kurma

```bash
pip install pillow opencv-python numpy zeroconf pyvirtualcam
```

### Masaüstü İstemcisini Çalıştırma

```bash
python PCam-Client.py
```

---

## 📦 Derleme

PyInstaller kurulumu:

```bash
pip install pyinstaller
```

Çalıştırılabilir dosya oluşturma:

```bash
pyinstaller PCam-Client.spec --clean
```

---

## 💡 Mimari Notları

PCam kaynak kullanımını minimum seviyede tutacak şekilde tasarlanmıştır.

Temel tasarım prensipleri:

* Asenkron ağ iletişimi
* Donanım hızlandırmalı video kodlama
* Minimum bellek kullanımı
* Hafif masaüstü arayüzü
* Olay tabanlı mimari

Bu sayede hem mobil cihazda hem de bilgisayarda düşük işlemci kullanımıyla düşük gecikmeli video aktarımı sağlanır.

📄 Lisans

Bu proje, MIT Lisansı ile lisanslanmıştır - detaylar için LICENSE dosyasına bakınız.