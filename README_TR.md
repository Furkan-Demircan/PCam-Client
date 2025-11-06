# PCam-Client (Türkçe Çeviri)

PCam-Client, TCP sunucusundan canlı kamera kareleri alan ve yerel olarak önizleyen hafif bir Python GUI uygulamasıdır. İki çerçeveleme modu destekler: basit JPEG çerçeveli görüntüler ve ffmpeg ile çözümlenen H.264 akışı. İsteğe bağlı olarak, gelen kareler bir sanal kameraya (pyvirtualcam yüklüyse) gönderilebilir; böylece OBS, Zoom gibi uygulamalar bu akışı web kamerası kaynağı olarak kullanabilir.

## Temel özellikler

- TCP üzerinden kare alma için basit ve güvenilir bir protokol.
- JPEG çerçeveli görüntüler (4 bayt uzunluk başlığı) ve H.264 akışı desteği (ffmpeg ile decode).
- Gönderenin gönderdiği dönüş (rotation) bilgisini işleyerek önizlemede ve sanal kamerada uygular.
- `pyvirtualcam` ile isteğe bağlı sanal kamera çıktısı.
- Bağlantı ve decode sorunlarının tanılanması için temel durum ve debug günlükleri.

## Protokol özeti

- JPEG çerçeveleme: 4 bayt büyük uçlu (big-endian) unsigned int uzunluk, ardından JPEG baytları. Gönderen, uzunluk yerine (0/90/180/270/360) döndürme değeri gönderebilir; bu durumda ardından 4 bayt uzunluk ve JPEG baytları gelir.
- H.264 akışı: sunucu ASCII `H264` başlığı gönderebilir, ardından genişlik, yükseklik ve fps olmak üzere üç 4 bayt büyük uçlu tamsayı gelir. İstemci bu durumda `ffmpeg` başlatarak ham RGB kareleri çözer.

## Gereksinimler

- Python 3.8+
- Pillow (PIL)
- OpenCV (cv2)
- NumPy
- ffmpeg — yalnızca H.264 modu kullanılıyorsa gerekir ve PATH içinde bulunmalıdır
- pyvirtualcam — yalnızca sanal kamera kullanmak isterseniz

Python bağımlılıklarını yüklemek için:

```bash
pip install pillow opencv-python-headless numpy
# İsteğe bağlı
pip install pyvirtualcam
```

ffmpeg'i işletim sisteminizin paket yöneticisiyle yükleyin veya https://ffmpeg.org adresinden indirip `ffmpeg`'i PATH'e ekleyin.

Not: Windows üzerinde tam GUI yetenekleri için `opencv-python` tercih edilebilir.

## Kullanım

### Seçenek 1: Bağımsız çalıştırılabilir dosyayı kullanın (Windows)

Windows'ta PCam-Client kullanmanın en kolay yolu önceden derlenmiş exe dosyasını indirmektir:

1. `dist` klasöründen `PCam-Client.exe` dosyasını indirin
2. (Opsiyonel) H.264 akışı kullanacaksanız, ffmpeg'i https://ffmpeg.org adresinden indirip PATH'e ekleyin
3. Uygulamayı başlatmak için `PCam-Client.exe` dosyasına çift tıklayın
4. GUI'de sunucu host ve port bilgilerini girin (varsayılan `127.0.0.1:8080`)
5. Dönüş veya sanal kamera seçeneklerini gerektiği gibi açın

**Not:** Exe dosyası yaklaşık 65MB boyutundadır çünkü Python ve tüm gerekli kütüphaneleri içerir. Python kurulumu gerekmez!

### Seçenek 2: Python kaynak kodundan çalıştırın

1. Kareleri gönderecek sunucuyu (cihaz veya streaming sunucusu) başlatın.
2. İstemci GUI'yi çalıştırın:

```bash
python PCam-Client.py
```

3. GUI'de sunucu host ve port bilgilerini girin (varsayılan `127.0.0.1:8080`), dönüş veya sanal kamera seçeneklerini gerektiği gibi açın.

### Klavye kısayolları

- `r` — Reset / yeniden bağlan

## Sanal kamera

`pyvirtualcam` yüklüyse, "Send to virtual camera" seçeneğini etkinleştirerek gelen kareleri sistem sanal kamerası olarak yayınlayabilirsiniz. Sanal kamera başlamadan önce çözünürlük ve FPS değerlerini UI'den ayarlayın.

## Sorun Giderme

- İstemci "Device not Found" gösteriyorsa, sunucunun çalıştığından ve belirtilen host/port'tan erişilebilir olduğundan emin olun.
- H.264 akışı kullanıyorsanız `ffmpeg`'in PATH üzerinde olduğundan emin olun. İstemci eksik ffmpeg durumunda durumu bildirir.
- Daha detaylı konsol çıktısı için UI'de "Show debug logs" seçeneğini etkinleştirin.

## ADB yönlendirme (Android cihazlar)

Eğer `adb` PATH üzerinde bulunuyorsa, istemci otomatik olarak `adb forward tcp:8080 tcp:8080` komutunu çalıştırmayı dener; bu USB üzerinden Android cihazdan akış almak için kullanışlıdır.

## Exe dosyasını kendiniz derlemek

Exe dosyasını kendiniz derlemek isterseniz:

1. PyInstaller'ı yükleyin:
```bash
pip install pyinstaller
```

2. Exe dosyasını derleyin:
```bash
pyinstaller PCam-Client.spec --clean
```

3. Exe dosyası `dist` klasöründe oluşturulacaktır (yaklaşık 65MB)

Derleme işlemi, tüm gerekli bağımlılıkları (tkinter, PIL, OpenCV, NumPy, vb.) içeren `PCam-Client.spec` dosyası ile yapılandırılmıştır.

## Katkıda bulunma

Küçük düzeltmeler memnuniyetle kabul edilir. Lütfen kısa bir açıklama ile issue veya pull request açın.

## Diller

Bu dosya README dosyasının Türkçe çevirisidir. Orijinal İngilizce sürüm: [README.md](README.md)
