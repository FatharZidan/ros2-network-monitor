# 📑 Dokumen Evaluasi Kritis & Kompilasi Skeptisisme Sistem Monitoring ROS 2 — BRONE Robot

Dokumen ini disusun sebagai **catatan evaluasi metodologis komprehensif** berdasarkan diskusi kritis terkait keterbatasan, tantangan validasi, dan aspek-aspek skeptisisme terhadap sistem *ROS 2 Network Monitor*. Dokumen ini ditujukan sebagai bahan evaluasi tim, perbaikan instrumen pengujian, serta landasan penyusunan metodologi penelitian skripsi yang objektif.

---

## 🎯 Ringkasan Eksekutif Evaluasi

Sistem monitoring jaringan yang dikembangkan saat ini berhasil membuktikan keandalan dasar middleware *CycloneDDS* pada lingkungan *cross-distro* (Jazzy ↔ Humble). Namun, terdapat sejumlah **titik kritis metodologis** yang harus diperhatikan agar hasil pengukuran tidak menjadi *false positive* dan benar-benar mencerminkan performa nyata robot humanoid BRONE pada kondisi operasional penuh.

---

## 🔍 Kompilasi Poin-Poin Skeptisisme & Evaluasi Kritis

### 1. Skeptisisme Standar Acuan Kualitas (Risiko *False Positive* & Realitas Operasional)
* **Poin Kritis:**
  * Standar kualitas awal yang menetapkan latensi `< 2.0 ms` sebagai "Ideal" dan `> 10.0 ms` sebagai "Kritis" dinilai tidak realistis untuk operasional robot nyata.
  * Pengujian saat ini masih bersifat statis (data sintetis 128 Bytes, 50 Hz) tanpa melibatkan beban algoritma berat seperti *YOLOv11s*, *Facial Expression Recognition (FER v2)*, atau *streaming* kamera `/image_raw/compressed`.
  * Dalam kondisi riil, latensi jaringan nirkabel (WiFi / ZeroTier) dan pemrosesan visi umumnya berkisar puluhan hingga ratusan milidetik (20–100 ms).
  * Menetapkan angka batas ketat (misal 5 ms) berisiko memunculkan kesimpulan keliru (*false positive*), di mana lonjakan kecil yang sama sekali tidak mengganggu fisik robot (tidak terasa oleh manusia/motor) dicap sebagai sistem bermasalah.
* **Bahan Evaluasi:**
  * Penilaian kualitas harus berbasis **Siklus Waktu Subsistem (*Period Budgeting* $T = \frac{1}{f}$)**, bukan angka mutlak tunggal.
  * Untuk kontrol motor 50 Hz ($T = 20\text{ ms}$), latensi transmisi 4 ms vs 8 ms memiliki dampak fisik yang sama persis selama tiba sebelum siklus 20 ms berikutnya.
  * Perlu pemisahan tegas antara latensi *low-level control* (LAN kabel) dengan latensi *perception & telemetry* (WiFi/AI).

---

### 2. Skeptisisme Fenomena Pembacaan Data & Stabilitas Sistem
* **Poin Kritis:**
  * **Status UI Berubah "Tidak Ada Data Baru":** Muncul keraguan mengapa status monitor di web sesekali menunjukkan tidak ada data baru padahal *Miss Rate* tercatat 0.00%.
  * **Osilasi Frekuensi (49 Hz ↔ 51 Hz):** Mengapa frekuensi pesan per detik tidak selalu bernilai bulat 50 Hz konstan, melainkan terkadang 49 Hz lalu 51 Hz.
  * **Inisiasi di Awal Pengukuran:** Mengapa sistem tidak langsung berada di 50 Hz secara instan dari detik 0.0, padahal *clock* CPU Jetson mencapai orde GHz (jauh melampaui 50 Hz).
* **Bahan Evaluasi & Penjelasan Teknis:**
  * Status "Tidak Ada Data Baru" sesaat disebabkan oleh *Polling Phase Jitter* (perbedaan fase waktu asinkron antara timer JavaScript browser laptop dan timer Python di robot), bukan karena paket hilang.
  * Osilasi 49–51 Hz adalah fenomena alami *Window Boundary Quantization* pada Linux Non-Realtime (CFS scheduler), di mana keterlambatan sub-milidetik (0.2 ms) menggeser 1 paket ke jendela detik berikutnya tanpa adanya *packet loss* kumulatif.
  * *Ramp-up* di awal terjadi akibat alokasi memori runtime Python, *page faults*, serta fase *DDS Discovery Handshake* (SPDP/SEDP).

---

### 3. Skeptisisme Pemetaan Topologi & Validitas Komparasi Antar-Sesi
* **Poin Kritis:**
  * Ketidakpastian mengenai node dan topik mana pada program riil BRONE yang masuk ke dalam topologi `nuc2nuc`, `jetson2jetson`, `jetson2nuc`, atau `nuc2jetson`.
  * **Tantangan Validitas Antar-Sesi:** Menguji masing-masing topologi pada waktu/sesi yang terpisah menimbulkan keraguan metodologis karena kondisi lingkungan (suhu CPU, interferensi WiFi, beban *background process* OS) tidak dapat direplikasi 100% identik antar-sesi.
* **Bahan Evaluasi:**
  * Pengujian harus dibagi menjadi 2 tahap metodologis yang jelas:
    1. **Tahap 1 (Karakteristik Fisik Dasar):** Menguji batas bawah latensi kabel murni dengan parameter terkontrol ketat.
    2. **Tahap 2 (Uji Misi Terintegrasi):** Memasang monitor pada topik nyata saat robot menjalankan satu sesi skenario utuh, sehingga seluruh data terekam secara simultan dalam satu *timeline* waktu yang sinkron.

---

### 4. Skeptisisme Kegunaan Program Monitoring (Apakah Menjadi Sia-Sia?)
* **Poin Kritis:**
  * Jika program pengujian hanya mengukur data sintetis dummy pada kondisi statis dan belum menghitung latensi WiFi/AI sesungguhnya, timbul pertanyaan apakah program monitoring ini menjadi kurang berguna.
* **Bahan Evaluasi (Nilai Strategis Program):**
  * Program monitoring ini **tidak sia-sia**, melainkan berfungsi sebagai **Baseline Kontrol Murni (*Gold Standard Control Group*)**.
  * Tanpa data baseline komunikasi murni (~0.8 ms), peneliti tidak akan bisa membuktikan secara ilmiah apakah keterlambatan robot nantinya bersumber dari jaringan DDS atau komputasi AI/GPU.
  * Berfungsi sebagai bukti empiris keberhasilan migrasi *CycloneDDS* pada ROS 2 lintas distro (Jazzy ↔ Humble).

---

### 5. Skeptisisme Terhadap Asumsi Arsitektur Tanpa Verifikasi Repositori
* **Poin Kritis:**
  * Asumsi mengenai arsitektur komunikasi robot yang hanya didasarkan pada dokumen teks (BOS v4.0) tanpa memeriksa repositori kode dan hardware fisik secara langsung berisiko tidak akurat dengan kenyataan di lapangan.
  * Penggantian hardware (seperti Jetson Omniwheel mandiri) menuntut kehati-hatian agar konfigurasi tidak merusak skripsi pihak lain (*Zero-Touch constraint*).
* **Bahan Evaluasi:**
  * Menolak asumsi sepihak dan mewajibkan verifikasi *Ground Truth* menggunakan kakas introspeksi resmi ROS 2 sebelum mengambil kesimpulan topologi.

---

### 6. Disclaimer Ruang Lingkup & Batasan Pengukuran (*Scope & Limitations*)

Untuk menjaga integritas ilmiah dan mencegah salah interpretasi data saat sidang atau penulisan jurnal, batas-batas pengukuran program ini didefinisikan secara tegas sebagai berikut:

#### A. Apa yang Benar-Benar Diukur (*In-Scope*):
1. **Transport Latency & Jitter Lapisan DDS (ROS 2):**
   * Waktu serialisasi struct biner (16-byte header + padding) pada `rclpy`.
   * Waktu transmisi protokol RTPS UDP/IP melalui middleware *CycloneDDS*.
   * Waktu transit fisik melintasi **kabel LAN tembaga RJ45 Point-to-Point** (`192.168.100.x`) antar prosesor internal robot (Intel NUC ↔ NVIDIA Jetson).
   * Waktu deserialisasi pada penerima hingga data siap dieksekusi oleh *callback* ROS 2.

---

#### B. Apa yang Berada di Luar Spesifikasi / Batasan (*Out-of-Scope*):
1. 📶 **Latensi Wi-Fi / SSH / ZeroTier Laptop ke Robot (Off-Board Telemetry):**
   * Sinyal nirkabel Wi-Fi laptop penguji (SSH/Browser) memiliki latensi acak ($\sim 20\text{ -- }100\text{ ms}$) akibat interferensi radio 2.4/5 GHz dan *CSMA/CA backoff*.
   * Latensi Wi-Fi ini **BUKAN** bagian dari kontrol internal robot dan **TIDAK** diukur oleh angka latensi di dashboard. Angka $\sim 1.2\text{ ms}$ di dashboard adalah waktu tempuh murni di kabel LAN robot.
2. 🔌 **Latensi Serial Bus Dynamixel / RS-485 / OpenCR / U2D2:**
   * Waktu transmisi fisik dari port USB/UART NUC ke mikrokontroler OpenCR/U2D2 dan propagasi sinyal serial RS-485 ke rantai motor servo Dynamixel (orde $\sim 1\text{ -- }3\text{ ms}$).
   * Monitor mengukur lapisan transportasi pesan ROS 2, bukan *hardware bus latency* Dynamixel.
3. 👁️ **Latensi Pemrosesan Sensor & Inferensi AI (Sensor Exposure & GPU Compute Time):**
   * Waktu eksposur sensor optik kamera CMOS (*rolling/global shutter* $\sim 15\text{ -- }30\text{ ms}$) dan waktu eksekusi inferensi tensor GPU AI (*YOLOv11s / FER v2* $\sim 20\text{ -- }50\text{ ms}$).
   * Waktu tersebut adalah **Latensi Komputasi (*Processing Latency*)**, bukan latensi transportasi jaringan. Monitor mengukur seberapa cepat hasil inferensi tersebut dipublikasikan dan ditransmisikan ke otak gerak.
4. ⏰ **Dependensi Presisi Sinkronisasi Waktu (*Clock Sync Dependency*):**
   * Pengukuran latensi satu arah lintas mesin (*Inter-host*) mengasumsikan kedua komputer telah disinkronkan jam internalnya via protokol `chrony` (akurasi sub-milidetik pada LAN kabel).

---

## 🛠️ Matriks Rencana Tindak Lanjut & Validasi Lapangan

| No | Aspek Evaluasi | Aksi Perbaikan / Verifikasi | Status |
| :--- | :--- | :--- | :--- : |
| 1 | **Tabel Acuan Kualitas** | Mengganti ambang batas tunggal dengan matriks berbasis subsistem (*Period Budgeting*: 20ms Motor, 33ms Visi, 100ms WiFi). | **SELESAI (Di Dashboard)** |
| 2 | **Fitur Anotasi Dinamis** | Menyediakan *Event Marker* (garis vertikal) untuk mencatat momen aktivasi program berat (YOLO/FER/Gerak) pada grafik kontinu. | **SELESAI** |
| 3 | **Kontrol Sesi Pengujian** | Mengembangkan fitur *Controlled Benchmark Session* (Tombol Start/Stop + Timer Otomatis 60s/300s) lengkap dengan countdown dan progress bar. | **SELESAI** |
| 4 | **Metrik Jitter Kontinu** | Menghitung standar deviasi latensi ($\sigma_\tau$) kontinu per detik dan menampilkan grafik time-series Jitter. | **SELESAI** |
| 5 | **Verifikasi Topologi Riil** | Menjalankan `ros2 topic list`, `ros2 topic info -v`, dan `rqt_graph` saat robot BRONE aktif bersama tim. | **AGENDA LAPANGAN** |
| 6 | **Pengujian Terintegrasi** | Menguji transmisi topik nyata lintas mesin saat robot menjalankan misi penuh untuk memvalidasi interaksi multivariabel. | **SELESAI (67k+ Paket)** |

---

*Dokumen ini disimpan di repositori proyek sebagai referensi analisis kritis dan bagian dari integritas metodologi penelitian.*
