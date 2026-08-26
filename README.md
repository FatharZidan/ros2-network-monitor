# ROS 2 Network Performance Monitor — Panduan Lengkap (BRONE Robot)

## Arsitektur Jaringan BRONE

```
                          ZeroTier VPN (Internet)
  ┌──────────────┐       ══════════════════════        ┌──────────────────────┐
  │  PC Peneliti │◄════►   10.101.143.111 (NUC)        │   Intel NUC          │
  │  (Windows)   │        10.101.143.175 (Jetson) ═══► │   ROS 2 Jazzy        │
  │              │                                     │   Ubuntu 24.04       │
  └──────────────┘                                     │   User: brone-ub     │
                                                       │                      │
                                                       │   enp114s0:          │
                                                       │   192.168.100.1      │
                                                       └──────────┬───────────┘
                                                                  │
                                                          Kabel RJ45 Langsung
                                                         (Point-to-Point LAN)
                                                                  │
                                                       ┌──────────┴───────────┐
                                                       │   NVIDIA Jetson      │
                                                       │   ROS 2 Humble       │
                                                       │   User: brone        │
                                                       │                      │
                                                       │   enP8p1s0:          │
                                                       │   192.168.100.2      │
                                                       └──────────────────────┘
```

### Ringkasan Koneksi

| Perangkat | IP LAN (RJ45) | IP ZeroTier | SSH User | ROS 2 |
|-----------|---------------|-------------|----------|-------|
| Intel NUC | `192.168.100.1` | `10.101.143.111` | `brone-ub` | Jazzy |
| NVIDIA Jetson | `192.168.100.2` | `10.101.143.169` | `brone` | Humble |

### Middleware: CycloneDDS (Unicast)

Kedua mesin menggunakan **CycloneDDS** dengan konfigurasi unicast (tanpa multicast).
File konfigurasi sudah ada di `~/cyclonedds.xml` pada kedua mesin.
Environment variables sudah dikonfigurasi di `~/.bashrc`:

```bash
# Sudah ada di .bashrc NUC & Jetson:
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/<user>/cyclonedds.xml
```

---

## Arsitektur Program Monitor

```
┌─────────────────────┐                     ┌──────────────────────────────────┐
│  dummy_publisher.py │    /test_topic      │  network_monitor.py (CLI)        │
│                     │   ─── DDS ──────▶   │  network_monitor_gui.py (Web)    │
│  Kirim:             │   String + JSON     │                                  │
│   • seq number      │   (CycloneDDS)      │  Terima & Hitung:                │
│   • timestamp       │                     │   • Frekuensi (Hz)               │
│                     │                     │   • Latency (ms)                 │
│                     │                     │   • Statistik/detik              │
└─────────────────────┘                     └───────────┬──────────────────────┘
                                                        │ (GUI only)
                                                        │ HTTP :8080
                                                        ▼
                                            ┌──────────────────────┐
                                            │  Browser (Windows/   │
                                            │  Ubuntu/HP apapun)   │
                                            │  dashboard.html      │
                                            │   • Grafik real-time │
                                            │   • Kartu metrik     │
                                            │   • Clock skew alert │
                                            └──────────────────────┘
```

### Dua Mode Monitoring

| Mode | File | Output | Kapan Dipakai |
|------|------|--------|---------------|
| **CLI** | `network_monitor.py` | Log teks di terminal | SSH tanpa browser, debugging cepat |
| **Web GUI** | `network_monitor_gui.py` + `dashboard.html` | Dashboard grafis di browser | Demo, presentasi, monitoring jangka panjang |

---

## Prasyarat

Pastikan di mesin target (NUC/Jetson) sudah tersedia:

```bash
# ROS 2 harus sudah di-source
# Di NUC (Jazzy):
source /opt/ros/jazzy/setup.bash

# Di Jetson (Humble):
source /opt/ros/humble/setup.bash

# Pastikan rclpy dan std_msgs tersedia
python3 -c "import rclpy; print('rclpy OK')"
python3 -c "from std_msgs.msg import String; print('std_msgs OK')"
```

---

## Transfer File ke NUC & Jetson

### Opsi A — SCP dari Windows (CMD)

```cmd
REM cd ke folder project dulu (menghindari masalah path spasi)
cd "C:\Users\Patarajah\Documents\IDE Antigravity\ros2_network_monitor"

REM Transfer semua file ke NUC
scp dummy_publisher.py network_monitor.py network_monitor_gui.py dashboard.html brone-ub@10.101.143.111:~/ros2_network_monitor/

REM Transfer ke Jetson (opsional, via ZeroTier)
scp dummy_publisher.py network_monitor.py network_monitor_gui.py dashboard.html humanoid@10.101.143.175:~/ros2_network_monitor/
```

> **Catatan:** Jangan gunakan path lengkap `C:\...` di perintah `scp`
> karena CMD bisa salah parsing tanda `:` sebagai hostname.

### Opsi B — Dari Dalam Sesi SSH (Sudah di NUC)

Jika Anda **sudah SSH ke NUC** dan ingin membuat file tanpa `scp` dari Windows:

#### Metode 1 — Heredoc (Copy-Paste Langsung, Direkomendasikan)

```bash
# Buat direktori
mkdir -p ~/ros2_network_monitor
cd ~/ros2_network_monitor

# Tempel isi dummy_publisher.py menggunakan heredoc
cat > dummy_publisher.py << 'SCRIPT_END'
<paste seluruh isi dummy_publisher.py di sini>
SCRIPT_END

# Ulangi untuk network_monitor.py
cat > network_monitor.py << 'SCRIPT_END'
<paste seluruh isi network_monitor.py di sini>
SCRIPT_END
```

> **Penting:** Gunakan kutip tunggal di `'SCRIPT_END'` agar shell
> **tidak** meng-expand variabel `$` di dalam isi script.

#### Metode 2 — Nano (Editor Interaktif)

```bash
mkdir -p ~/ros2_network_monitor && cd ~/ros2_network_monitor

nano dummy_publisher.py
# → Paste isi script (Ctrl+Shift+V)
# → Simpan: Ctrl+O → Enter
# → Keluar: Ctrl+X

nano network_monitor.py
# → Ulangi
```

#### Metode 3 — SCP dari NUC ke Jetson

Jika file sudah ada di NUC dan ingin dikirim ke Jetson via kabel LAN:

```bash
# Dari dalam sesi SSH di NUC
scp -r ~/ros2_network_monitor brone@192.168.100.2:~/ros2_network_monitor
```

### Verifikasi Setelah Transfer (Wajib)

```bash
cd ~/ros2_network_monitor

# Cek syntax Python (tidak ada output = OK)
python3 -m py_compile dummy_publisher.py
python3 -m py_compile network_monitor.py

# Cek dependensi ROS 2
python3 -c "import rclpy; from std_msgs.msg import String; print('Semua dependensi OK')"
```

---

## Langkah Dasar — Uji Lokal di NUC (TDD Baseline)

Pengujian pertama: jalankan publisher dan monitor **di mesin yang sama** (NUC)
untuk membuktikan akurasi program sebelum uji lintas mesin.

> **⚠️ PENTING: `unset CYCLONEDDS_URI` wajib untuk uji lokal!**
>
> File `~/cyclonedds.xml` yang sudah ada di `.bashrc` mengunci DDS ke
> interface LAN (`192.168.100.1`) dengan peer Jetson (`192.168.100.2`).
> Akibatnya, dua node di **mesin yang sama** tidak bisa saling menemukan
> karena DDS tidak melihat loopback. Solusi: `unset CYCLONEDDS_URI`
> agar DDS kembali ke discovery default (loopback).

### Terminal SSH 1 — Dummy Publisher

```bash
# Dari Windows CMD:
ssh brone-ub@10.101.143.111

# Source ROS 2 Jazzy
source /opt/ros/jazzy/setup.bash
source ~/.bashrc

# WAJIB: Nonaktifkan config CycloneDDS LAN untuk uji lokal
unset CYCLONEDDS_URI

cd ~/ros2_network_monitor
python3 dummy_publisher.py
```

**Output yang diharapkan (log setiap 1 detik):**
```
[INFO] [dummy_publisher]: [DummyPublisher] AKTIF — Target: 50.0 Hz | Periode: 20.00 ms | Topik: /test_topic
[INFO] [dummy_publisher]: [PUB] seq=50   stamp=1750321200.123456
[INFO] [dummy_publisher]: [PUB] seq=100  stamp=1750321201.123789
```

### Terminal SSH 2 — Network Monitor

```bash
# Buka CMD baru di Windows:
ssh brone-ub@10.101.143.111

source /opt/ros/jazzy/setup.bash
source ~/.bashrc

# WAJIB: Sama seperti terminal 1
unset CYCLONEDDS_URI

cd ~/ros2_network_monitor
python3 network_monitor.py
```

**Output yang diharapkan:**
```
[INFO] [network_monitor]: ────────────────────────────────────────────────────────────
[INFO] [network_monitor]:   Frekuensi  :    50.02 Hz   (50 pesan / 1.000 s)
[INFO] [network_monitor]:   Latency    : avg=  0.152 ms  min=  0.089 ms  max=  0.312 ms  std=  0.045 ms
[INFO] [network_monitor]:   Kumulatif  : 150 pesan total diterima
[INFO] [network_monitor]: ────────────────────────────────────────────────────────────
```

### Validasi TDD (Kriteria Kelulusan Baseline)

| Metrik | Kriteria Lulus | Penjelasan |
|--------|----------------|------------|
| **Frekuensi (Hz)** | `48.0 – 52.0 Hz` | Target 50 Hz; toleransi ±4% untuk timer OS |
| **Pesan per detik** | `48 – 52` | Konsisten mendekati 50 per jendela |
| **Avg Latency** | `< 5.0 ms` | Lokal di satu mesin, seharusnya sub-milidetik |
| **Std Latency** | `< 2.0 ms` | Jitter rendah = DDS stabil |

### Verifikasi Silang dengan Tool ROS 2

```bash
# Terminal SSH ke-3 di NUC:
ssh brone-ub@10.101.143.111
source ~/.bashrc

ros2 topic list           # Harus menampilkan /test_topic
ros2 topic hz /test_topic # Harus mendekati 50 Hz
ros2 topic echo /test_topic --once  # Cek isi pesan JSON
```

---

## Override Frekuensi (Opsional)

```bash
# 100 Hz
python3 dummy_publisher.py --ros-args -p target_hz:=100.0

# 10 Hz
python3 dummy_publisher.py --ros-args -p target_hz:=10.0
```

---

# Prasyarat Wajib: Sinkronisasi Clock (Chrony)

> **⚠️ KRITIS — Baca sebelum uji lintas mesin!**
>
> `time.time()` mengambil waktu dari **system clock masing-masing mesin**.
> Jika jam NUC dan Jetson berbeda 5 ms saja (sangat umum tanpa NTP presisi),
> maka **semua angka latency sudah salah dari awal** — bisa negatif, bisa
> ter-inflate. Script `network_monitor.py` akan otomatis menampilkan
> **peringatan CLOCK SKEW** jika mendeteksi latency negatif.
>
> **Untuk uji lokal di satu mesin (TDD Baseline), clock sync TIDAK
> diperlukan** karena publisher dan monitor menggunakan clock yang sama.

---

## Mengapa Chrony (Bukan ntpdate)?

| Metode | Presisi | Sifat | Cocok Untuk |
|--------|---------|-------|-------------|
| `ntpdate` | ~5-10 ms | Satu kali koreksi, lalu drift lagi | Quick fix sementara |
| `chrony` | **< 0.1 ms** (LAN P2P) | Koreksi terus-menerus, anti-drift | Pengukuran latency presisi |

Untuk LAN point-to-point NUC↔Jetson, **chrony bisa mencapai offset < 0.1 ms**
yang berarti pengukuran latency kita akurat hingga sub-milidetik.

---

## Setup Chrony: NUC sebagai Server, Jetson sebagai Client

### Langkah 1 — Install Chrony di Kedua Mesin

```bash
# ── Di NUC ──
ssh brone-ub@10.101.143.111
sudo apt update && sudo apt install chrony -y

# ── Di Jetson ──
ssh humanoid@10.101.143.175
sudo apt update && sudo apt install chrony -y
```

### Langkah 2 — Konfigurasi NUC sebagai NTP Server

```bash
# ── Di NUC ──
ssh brone-ub@10.101.143.111

# Backup config asli
sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.bak

# Tambahkan baris berikut di AKHIR file /etc/chrony/chrony.conf:
echo '' | sudo tee -a /etc/chrony/chrony.conf
echo '# === BRONE: Izinkan Jetson sync ke NUC via LAN ===' | sudo tee -a /etc/chrony/chrony.conf
echo 'allow 192.168.100.0/24' | sudo tee -a /etc/chrony/chrony.conf
echo 'local stratum 10' | sudo tee -a /etc/chrony/chrony.conf

# Restart chrony
sudo systemctl restart chrony
sudo systemctl enable chrony

# Verifikasi chrony aktif
chronyc tracking
# Perhatikan baris "Leap status": harus "Normal"
```

> **`local stratum 10`** memastikan NUC tetap bisa jadi sumber waktu
> bahkan jika NUC sendiri tidak punya akses internet (misal di lapangan).

### Langkah 3 — Konfigurasi Jetson sebagai NTP Client

```bash
# ── Di Jetson ──
ssh humanoid@10.101.143.175

# Backup config asli
sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.bak

# Tambahkan NUC sebagai sumber waktu prioritas utama
# Buka file dengan nano:
sudo nano /etc/chrony/chrony.conf

# Tambahkan baris ini di AWAL file (sebelum server pool lainnya):
# server 192.168.100.1 iburst prefer minpoll 0 maxpoll 2

# Simpan (Ctrl+O, Enter) dan keluar (Ctrl+X)

# Restart chrony
sudo systemctl restart chrony
sudo systemctl enable chrony
```

> **Penjelasan parameter:**
> - `iburst` — Kirim 4 paket sekaligus saat pertama kali sync (cepat lock)
> - `prefer` — Prioritaskan server ini di atas sumber NTP lain
> - `minpoll 0, maxpoll 2` — Polling sangat sering (1–4 detik) untuk presisi maksimal di LAN

### Langkah 4 — Verifikasi Sinkronisasi

Tunggu **30–60 detik** setelah restart chrony, lalu verifikasi:

```bash
# ── Di Jetson ──
chronyc sources -v
# Cari baris dengan IP 192.168.100.1
# Kolom "Reach" harus 377 (semua polling berhasil)
# Tanda "^*" di depan = ini adalah sumber aktif

# Cek offset aktual
chronyc tracking
# Perhatikan:
#   "System time"  : harus mendekati 0.000 seconds
#   "RMS offset"   : TARGET < 0.000100 seconds (< 0.1 ms)
#   "Last offset"  : harus sangat kecil

# Quick check ringkas
chronyc tracking | grep -E "RMS offset|Last offset|Leap status"
```

**Output target yang diharapkan:**
```
RMS offset     : 0.000043 seconds        ← < 0.1 ms ✅
Last offset    : +0.000021 seconds        ← < 0.1 ms ✅
Leap status    : Normal                   ← Sinkron ✅
```

```bash
# ── Di NUC: cek apakah Jetson terdaftar sebagai client ──
chronyc clients
# Harus menampilkan 192.168.100.2 dengan NTP count > 0
```

### Langkah 5 — Quick Sanity Check (Opsional)

Bandingkan waktu kedua mesin secara manual:

```bash
# Jalankan di kedua mesin secara bersamaan (buka 2 terminal):
date +%s.%N

# Contoh output NUC  : 1750321200.123456789
# Contoh output Jetson: 1750321200.123498123
# Selisih harus < 0.001 detik (1 ms)
```

---

## Troubleshooting Chrony

| Masalah | Penyebab | Solusi |
|---------|----------|--------|
| `chronyc sources` kosong | Config belum ter-load | `sudo systemctl restart chrony`, tunggu 30 detik |
| Reach = 0 (tidak ada polling) | Firewall blokir NTP (UDP 123) | `sudo ufw allow 123/udp` di NUC |
| RMS offset > 1 ms | Polling terlalu jarang | Pastikan `minpoll 0 maxpoll 2` di config Jetson |
| "Not synchronised" | Belum cukup sampel | Tunggu 2–3 menit, chrony butuh waktu konvergensi |
| Offset besar lalu mengecil perlahan | Normal — chrony koreksi bertahap | Tunggu 5 menit untuk konvergensi penuh |

---

# Skenario Pengujian Lanjutan

---

## Skenario A — Uji Lintas Mesin: NUC ↔ Jetson (Kabel LAN Langsung)

**Tujuan:** Mengukur latency dan frekuensi komunikasi DDS antara NUC dan Jetson
melalui kabel RJ45 point-to-point menggunakan CycloneDDS unicast yang sudah
terkonfigurasi.

```
┌──────────────────────────┐    Kabel RJ45 Langsung     ┌──────────────────────────┐
│       Intel NUC          │ ◄════════════════════════► │      NVIDIA Jetson       │
│    (network_monitor)     │   (Point-to-Point LAN)     │    (dummy_publisher)     │
│                          │                            │                          │
│  IP LAN  : 192.168.100.1 │    CycloneDDS Unicast      │  IP LAN  : 192.168.100.2 │
│  Iface   : enp114s0      │    ROS_DOMAIN_ID=30        │  Iface   : enP8p1s0      │
│  ROS 2   : Jazzy         │                            │  ROS 2   : Humble        │
│  User    : brone-ub      │    ◄── /test_topic ──      │  User    : brone         │
└──────────────────────────┘                            └──────────────────────────┘
```

### Langkah A.1 — Verifikasi Konektivitas LAN

```bash
# ── SSH ke NUC ──
ssh brone-ub@10.101.143.111

# Ping Jetson via kabel LAN
ping -c 5 192.168.100.2
# Harus sukses dengan latency < 1 ms (koneksi langsung)
# Contoh: 64 bytes from 192.168.100.2: time=0.234 ms
```

```bash
# ── SSH ke Jetson (dari terminal Windows terpisah) ──
ssh humanoid@10.101.143.175

# Ping NUC via kabel LAN
ping -c 5 192.168.100.1
# Harus sukses juga
```

> **Jika ping gagal:**
> - Pastikan kabel RJ45 terpasang dengan benar
> - Cek IP statis: `ip addr show enp114s0` (NUC) / `ip addr show enP8p1s0` (Jetson)
> - Matikan Wi-Fi sementara untuk memaksa traffic lewat kabel LAN

### Langkah A.2 — Transfer Script ke Jetson

Ada dua cara transfer, pilih salah satu:

```bash
# ── Cara 1: Dari NUC ke Jetson via kabel LAN (dari dalam SSH NUC) ──
scp -r ~/ros2_network_monitor brone@192.168.100.2:~/ros2_network_monitor

# ── Cara 2: Dari Windows langsung ke Jetson via ZeroTier ──
# (jalankan di CMD Windows)
# scp -r "c:\Users\Patarajah\Documents\IDE Antigravity\ros2_network_monitor" humanoid@10.101.143.175:~/ros2_network_monitor
```

### Langkah A.3 — Verifikasi Environment CycloneDDS

CycloneDDS dan environment variables **sudah dikonfigurasi** di `~/.bashrc`
kedua mesin. Kita hanya perlu memastikan semuanya ter-load:

```bash
# ── Di NUC ──
ssh brone-ub@10.101.143.111

# Pastikan environment ter-load
source ~/.bashrc

# Verifikasi variabel (semua harus ada nilainya)
echo "DOMAIN_ID  = $ROS_DOMAIN_ID"          # Harus: 30
echo "RMW        = $RMW_IMPLEMENTATION"      # Harus: rmw_cyclonedds_cpp
echo "CYCLONE    = $CYCLONEDDS_URI"           # Harus: file:///home/brone-ub/cyclonedds.xml

# Pastikan file XML ada
cat ~/cyclonedds.xml
# Harus menampilkan config dengan <Peer address="192.168.100.2"/>
```

```bash
# ── Di Jetson ──
ssh humanoid@10.101.143.175

source ~/.bashrc

echo "DOMAIN_ID  = $ROS_DOMAIN_ID"          # Harus: 30
echo "RMW        = $RMW_IMPLEMENTATION"      # Harus: rmw_cyclonedds_cpp
echo "CYCLONE    = $CYCLONEDDS_URI"           # Harus: file:///home/brone/cyclonedds.xml

cat ~/cyclonedds.xml
# Harus menampilkan config dengan <Peer address="192.168.100.1"/>
```

> **Jika variabel kosong:** Jalankan `source ~/.bashrc` atau periksa apakah
> baris export sudah ada di `~/.bashrc` sesuai dokumentasi BRONE.

### Langkah A.4 — Reset Daemon ROS 2 (SOP Wajib)

Sesuai SOP BRONE, **selalu reset daemon** sebelum uji lintas mesin:

```bash
# ── Di NUC ──
ros2 daemon stop
ros2 daemon start

# ── Di Jetson (terminal terpisah) ──
ros2 daemon stop
ros2 daemon start
```

### Langkah A.5 — Jalankan Publisher di Jetson

```bash
# ── Terminal SSH ke Jetson ──
ssh humanoid@10.101.143.175

# Source ROS 2 Humble + environment CycloneDDS
source /opt/ros/humble/setup.bash
source ~/.bashrc

# Pastikan variabel ter-load
echo $ROS_DOMAIN_ID    # Harus: 30

cd ~/ros2_network_monitor
python3 dummy_publisher.py
```

**Output yang diharapkan:**
```
[INFO] [dummy_publisher]: [DummyPublisher] AKTIF — Target: 50.0 Hz | Periode: 20.00 ms | Topik: /test_topic
[INFO] [dummy_publisher]: [PUB] seq=50   stamp=1750321200.123456
[INFO] [dummy_publisher]: [PUB] seq=100  stamp=1750321201.567890
```

### Langkah A.6 — Jalankan Monitor di NUC

```bash
# ── Terminal SSH baru ke NUC ──
ssh brone-ub@10.101.143.111

# Source ROS 2 Jazzy + environment CycloneDDS
source /opt/ros/jazzy/setup.bash
source ~/.bashrc

cd ~/ros2_network_monitor
python3 network_monitor.py
```

**Output yang diharapkan:**
```
[INFO] [network_monitor]: ────────────────────────────────────────────────────────────
[INFO] [network_monitor]:   Frekuensi  :    49.97 Hz   (50 pesan / 1.001 s)
[INFO] [network_monitor]:   Latency    : avg=  0.483 ms  min=  0.201 ms  max=  1.105 ms  std=  0.178 ms
[INFO] [network_monitor]:   Kumulatif  : 200 pesan total diterima
[INFO] [network_monitor]: ────────────────────────────────────────────────────────────
```

### Langkah A.7 — Verifikasi Silang dengan Tool ROS 2

```bash
# ── Di NUC (buka terminal SSH ke-3) ──
ssh brone-ub@10.101.143.111
source ~/.bashrc

# Cek topik terdeteksi lintas mesin
ros2 topic list
# Harus menampilkan: /test_topic

# Cek frekuensi (pembanding output monitor)
ros2 topic hz /test_topic
# Harus mendekati 50 Hz

# Cek node aktif dari kedua mesin
ros2 node list
# Harus menampilkan: /dummy_publisher dan /network_monitor

# Lihat isi pesan
ros2 topic echo /test_topic --once
# Harus menampilkan: data: '{"seq": ..., "stamp": ...}'
```

> **Catatan Warning "Failed to parse type hash":**
> Ini NORMAL karena perbedaan Jazzy ↔ Humble. Abaikan saja.
> Tidak mempengaruhi aliran data (sesuai dokumentasi BRONE).

### Kriteria Kelulusan Skenario A

| Metrik | Nilai Ekspektasi (LAN P2P) | Catatan |
|--------|---------------------------|---------|
| Frekuensi | 48–52 Hz | Hampir sama seperti lokal |
| Avg Latency | 0.2–2.0 ms | Sedikit lebih tinggi dari lokal, tapi tetap sub-ms area |
| Max Latency | < 5.0 ms | Spike sesekali wajar |
| Packet Loss | 0% | Tidak boleh ada loss di kabel LAN langsung |

### Troubleshooting Skenario A

| Masalah | Kemungkinan Penyebab | Solusi |
|---------|---------------------|--------|
| `ros2 topic list` kosong di NUC | DDS discovery gagal lintas mesin | 1. Cek `ROS_DOMAIN_ID` sama (30) di kedua mesin. 2. `ros2 daemon stop && ros2 daemon start`. 3. Matikan Wi-Fi sementara |
| Latency sangat tinggi (> 50 ms) | Clock tidak tersinkronisasi | `sudo ntpdate pool.ntp.org` di kedua mesin, atau aktifkan `chrony` |
| Hz terbaca 0 | Firewall memblokir port DDS | `sudo ufw allow 7400:7500/udp` di kedua mesin |
| Warning "Failed to parse type hash" | Perbedaan Jazzy ↔ Humble | **Abaikan.** Ini normal dan tidak mempengaruhi data |
| Topik terdeteksi tapi data kosong | `CYCLONEDDS_URI` salah path | Cek `echo $CYCLONEDDS_URI` dan pastikan file XML ada |
| Node Jetson tidak terlihat di NUC | Profil LAN tidak aktif | Pastikan kabel RJ45 terhubung dan cek `ip addr show enP8p1s0` |

---

## Skenario B — Uji Lintas VPN: Windows ↔ NUC (ZeroTier)

**Tujuan:** Mengukur overhead latency yang ditambahkan oleh tunnel VPN ZeroTier
dibanding komunikasi langsung. Ini menguji seberapa viable operasi remote
monitoring dari laptop peneliti.

```
┌─────────────────────────┐                            ┌─────────────────────────┐
│   PC Windows (Peneliti) │    ZeroTier VPN Tunnel     │       Intel NUC         │
│                         │◄══════════════════════════►│                         │
│   (network_monitor)     │   Encrypted UDP Tunnel     │   (dummy_publisher)     │
│                         │                            │                         │
│   ZT IP: (cek sendiri)  │   ◄── /test_topic ──       │   ZT IP: 10.101.143.111 │
│                         │       (DDS via VPN)        │   ROS 2: Jazzy          │
└─────────────────────────┘                            └─────────────────────────┘
```

> **Prasyarat Windows:** ROS 2 harus terinstall di Windows.
> Panduan: https://docs.ros.org/en/jazzy/Installation/Windows-Install-Binary.html
>
> Alternatif: Gunakan WSL2 Ubuntu dengan ROS 2 terinstall.

### Langkah B.1 — Pastikan ZeroTier Aktif & Catat IP

```cmd
REM ── Di Windows (CMD) ──
zerotier-cli info
REM Pastikan status: ONLINE

zerotier-cli listnetworks
REM Catat IP ZeroTier Windows Anda (cth: 10.101.x.x)
```

```bash
# ── Di NUC (SSH) ──
sudo zerotier-cli info
# Pastikan status: ONLINE

sudo zerotier-cli listnetworks
# Pastikan IP: 10.101.143.111
```

### Langkah B.2 — Verifikasi Konektivitas VPN

```cmd
REM ── Di Windows (CMD) ──
ping 10.101.143.111
REM Harus sukses. Catat rata-rata latency (= baseline VPN overhead)
REM Contoh: Average = 25ms
```

### Langkah B.3 — Konfigurasi CycloneDDS untuk VPN

ZeroTier **tidak mendukung multicast DDS** secara default. Kita perlu membuat
file CycloneDDS XML khusus yang mengarah ke peer melalui IP ZeroTier.

> **Penting:** Ini adalah config **terpisah** dari `~/cyclonedds.xml` yang
> sudah ada untuk koneksi LAN. Jangan timpa file yang sudah ada!

```bash
# ══════════════════════════════════════════════════════
# Di NUC: Buat config CycloneDDS KHUSUS untuk VPN
# ══════════════════════════════════════════════════════
ssh brone-ub@10.101.143.111

cat > ~/cyclonedds_vpn.xml << 'XML_END'
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS xmlns="https://github.com/eclipse-cyclonedds/cyclonedds">
    <Domain id="any">
        <General>
            <Interfaces>
                <NetworkInterface address="10.101.143.111"/>
            </Interfaces>
            <AllowMulticast>false</AllowMulticast>
            <MaxMessageSize>1472B</MaxMessageSize>
        </General>
        <Discovery>
            <ParticipantIndex>auto</ParticipantIndex>
            <Peers>
                <Peer address="WINDOWS_ZT_IP_DISINI"/>
            </Peers>
        </Discovery>
    </Domain>
</CycloneDDS>
XML_END

# Ganti placeholder dengan IP ZeroTier Windows Anda
# Contoh: sed -i 's/WINDOWS_ZT_IP_DISINI/10.101.xxx.xxx/' ~/cyclonedds_vpn.xml
sed -i 's/WINDOWS_ZT_IP_DISINI/<IP_ZEROTIER_WINDOWS_ANDA>/' ~/cyclonedds_vpn.xml

# Verifikasi isi file
cat ~/cyclonedds_vpn.xml
```

Di **Windows**, buat file `cyclonedds_vpn.xml` (misal di folder project):

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS xmlns="https://github.com/eclipse-cyclonedds/cyclonedds">
    <Domain id="any">
        <General>
            <Interfaces>
                <!-- Ganti dengan IP ZeroTier Windows Anda -->
                <NetworkInterface address="10.101.x.x"/>
            </Interfaces>
            <AllowMulticast>false</AllowMulticast>
            <MaxMessageSize>1472B</MaxMessageSize>
        </General>
        <Discovery>
            <ParticipantIndex>auto</ParticipantIndex>
            <Peers>
                <Peer address="10.101.143.111"/>
            </Peers>
        </Discovery>
    </Domain>
</CycloneDDS>
```

Simpan file ini, misalnya di:
`C:\Users\Patarajah\Documents\IDE Antigravity\ros2_network_monitor\cyclonedds_vpn.xml`

### Langkah B.4 — Jalankan Publisher di NUC (dengan Config VPN)

```bash
# ── SSH ke NUC ──
ssh brone-ub@10.101.143.111

source /opt/ros/jazzy/setup.bash

# Override CYCLONEDDS_URI ke config VPN (JANGAN timpa .bashrc!)
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/brone-ub/cyclonedds_vpn.xml

cd ~/ros2_network_monitor
python3 dummy_publisher.py
```

### Langkah B.5 — Jalankan Monitor di Windows

```cmd
REM ── Di Windows (CMD baru) ──

REM Source ROS 2 (sesuaikan path instalasi Anda)
call C:\dev\ros2_jazzy\local_setup.bat

REM Set environment variables
set ROS_DOMAIN_ID=30
set RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set CYCLONEDDS_URI=file:///C:/Users/Patarajah/Documents/IDE Antigravity/ros2_network_monitor/cyclonedds_vpn.xml

cd "C:\Users\Patarajah\Documents\IDE Antigravity\ros2_network_monitor"
python network_monitor.py
```

**Output yang diharapkan (latency lebih tinggi karena VPN):**
```
[INFO] [network_monitor]: ────────────────────────────────────────────────────────────
[INFO] [network_monitor]:   Frekuensi  :    49.85 Hz   (50 pesan / 1.003 s)
[INFO] [network_monitor]:   Latency    : avg= 22.541 ms  min= 18.203 ms  max= 45.892 ms  std=  5.123 ms
[INFO] [network_monitor]:   Kumulatif  : 100 pesan total diterima
[INFO] [network_monitor]: ────────────────────────────────────────────────────────────
```

### Langkah B.6 — Verifikasi Silang

```cmd
REM ── Di Windows ──
ros2 topic list
REM Harus menampilkan: /test_topic

ros2 topic hz /test_topic
REM Harus mendekati 50 Hz
```

### Kriteria Kelulusan Skenario B

| Metrik | Nilai Ekspektasi (VPN) | Catatan |
|--------|------------------------|---------|
| Frekuensi | 45–52 Hz | Lebih fluktuatif karena jitter VPN |
| Avg Latency | 10–100 ms | Tergantung kualitas internet & jarak |
| Std Latency | < 20 ms | Jitter VPN lebih besar dari LAN |
| Packet Loss | < 2% | Sedikit loss mungkin terjadi |

> **⚠️ Catatan Penting tentang Clock Skew:**
>
> Pengukuran latency menggunakan `time.time()` **sangat bergantung pada
> sinkronisasi jam** antar mesin. Jika jam Windows dan NUC berbeda,
> latency yang terukur akan tidak akurat (bisa negatif atau sangat besar).
>
> **Solusi — Sinkronkan jam kedua mesin:**
> ```bash
> # Di NUC:
> sudo ntpdate pool.ntp.org
> # Atau cek status sinkronisasi:
> timedatectl status
> ```
> ```cmd
> REM Di Windows:
> w32tm /resync
> ```

### Troubleshooting Skenario B

| Masalah | Kemungkinan Penyebab | Solusi |
|---------|---------------------|--------|
| Topik tidak terdeteksi di Windows | CycloneDDS VPN config salah | Cek IP di kedua file `cyclonedds_vpn.xml`, pastikan saling menunjuk |
| Latency negatif (minus) | Jam tidak sinkron | `w32tm /resync` (Windows), `sudo ntpdate pool.ntp.org` (NUC) |
| Koneksi putus-putus | ZeroTier tidak stabil | `zerotier-cli info` untuk cek status |
| Firewall Windows blokir DDS | Windows Defender Firewall | Buka port UDP 7400-7500, atau tambah exception untuk `python.exe` |
| `ImportError: rclpy` di Windows | ROS 2 belum di-source | Pastikan `call C:\dev\ros2_jazzy\local_setup.bat` sudah dijalankan |
| Topik terdeteksi tapi data kosong | `CYCLONEDDS_URI` mengarah ke config LAN, bukan VPN | Pastikan `export CYCLONEDDS_URI=.../cyclonedds_vpn.xml` (bukan `cyclonedds.xml`) |

---

## Skenario C — Stress Test (Frekuensi Tinggi di NUC)

**Tujuan:** Mengukur batas kemampuan DDS di Intel NUC — pada frekuensi berapa
komunikasi mulai degradasi (packet loss, latency naik, Hz tidak tercapai).

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Intel NUC (Loopback)                         │
│                                                                      │
│  ┌─────────────────┐   /test_topic (DDS)  ┌──────────────────────┐   │
│  │ dummy_publisher │ ═══════════════════▶ │  network_monitor     │  │
│  │                 │    CycloneDDS        │                      │   │
│  │  Uji bertahap:  │    DOMAIN_ID=30      │  Pantau:             │   │
│  │   • 100 Hz      │                      │   • Hz aktual vs     │   │
│  │   • 200 Hz      │                      │     target           │   │
│  │   • 500 Hz      │                      │   • Latency trend    │   │
│  │   • 1000 Hz     │                      │   • Packet loss      │   │
│  └─────────────────┘                      └──────────────────────┘   │
│      Terminal 1                              Terminal 2              │
└──────────────────────────────────────────────────────────────────────┘
```

### Langkah C.1 — Persiapan

```bash
# ── SSH ke NUC ──
ssh brone-ub@10.101.143.111

source /opt/ros/jazzy/setup.bash
source ~/.bashrc

cd ~/ros2_network_monitor
```

### Langkah C.2 — Uji Bertahap (Rendah ke Tinggi)

Jalankan setiap tingkat frekuensi selama **minimal 30 detik** agar datanya
stabil, lalu catat hasilnya. Monitor cukup dijalankan sekali di Terminal 2.

**Terminal 2 (monitor) — jalankan satu kali, biarkan terus berjalan:**
```bash
python3 network_monitor.py
```

**Terminal 1 (publisher) — ganti frekuensi bertahap:**

```bash
# ── Tingkat 1: 100 Hz ──
python3 dummy_publisher.py --ros-args -p target_hz:=100.0
# Amati monitor ~30 detik, lalu Ctrl+C publisher
# Ekspektasi: Hz ≈ 100  |  Latency < 1 ms  |  Tanpa packet loss

# ── Tingkat 2: 200 Hz ──
python3 dummy_publisher.py --ros-args -p target_hz:=200.0
# Ekspektasi: Hz ≈ 200  |  Latency < 1 ms  |  Tanpa packet loss

# ── Tingkat 3: 500 Hz ──
python3 dummy_publisher.py --ros-args -p target_hz:=500.0
# Ekspektasi: Hz ≈ 480-500  |  Latency < 2 ms  |  Mungkin sedikit jitter

# ── Tingkat 4: 1000 Hz ──
python3 dummy_publisher.py --ros-args -p target_hz:=1000.0
# Ekspektasi: Hz ≈ 900-1000  |  Latency < 5 ms  |  Tergantung CPU NUC

# ── Tingkat 5: 2000 Hz (Extreme) ──
python3 dummy_publisher.py --ros-args -p target_hz:=2000.0
# Ekspektasi: Hz mungkin < 2000  |  Menguji batas absolut DDS + CPU
```

### Langkah C.3 — Catat & Bandingkan Hasil

Isi tabel ini dengan data aktual dari output monitor:

```
┌────────────┬───────────┬────────────┬────────────┬──────────────────────┐
│ Target Hz  │ Aktual Hz │ Avg Lat ms │ Max Lat ms │ Catatan              │
├────────────┼───────────┼────────────┼────────────┼──────────────────────┤
│    50      │   ___     │    ___     │    ___     │ Baseline             │
│    100     │   ___     │    ___     │    ___     │                      │
│    200     │   ___     │    ___     │    ___     │                      │
│    500     │   ___     │    ___     │    ___     │                      │
│   1000     │   ___     │    ___     │    ___     │                      │
│   2000     │   ___     │    ___     │    ___     │                      │
└────────────┴───────────┴────────────┴────────────┴──────────────────────┘
```

### Langkah C.4 — Monitor Sumber Daya Sistem (Disarankan)

Buka terminal SSH ke-3 ke NUC untuk memantau CPU/RAM selama stress test:

```bash
# ── Terminal 3 di NUC ──
ssh brone-ub@10.101.143.111

# Pantau CPU & RAM real-time
top -d 1

# Atau lebih visual (jika terinstall):
htop

# Pantau khusus proses Python ROS 2:
watch -n 1 "ps aux | grep -E 'dummy_pub|network_mon' | grep -v grep"
```

### Kriteria Kelulusan Skenario C

| Frekuensi Target | Hz Aktual Minimum | Avg Latency Maks | Status |
|-------------------|-------------------|-------------------|--------|
| 100 Hz | ≥ 98 Hz | < 1 ms | Harus LULUS |
| 200 Hz | ≥ 195 Hz | < 2 ms | Harus LULUS |
| 500 Hz | ≥ 480 Hz | < 3 ms | Seharusnya LULUS |
| 1000 Hz | ≥ 900 Hz | < 5 ms | Tergantung hardware NUC |
| 2000 Hz | Bervariasi | Bervariasi | Eksplorasi batas |

### Tanda-Tanda Degradasi yang Perlu Diwaspadai

- **Hz aktual jauh di bawah target** → CPU NUC tidak mampu handle timer rate
- **Avg Latency naik tajam** → Antrian DDS mulai menumpuk
- **Max Latency spike tinggi** → Scheduling delay di OS (cek apakah ada proses berat lain)
- **Std Latency besar** → Jitter tinggi, komunikasi tidak konsisten
- **Pesan hilang (gap di seq number)** → DDS mulai drop paket

---

## Skenario D — Uji Lintas Mesin + VPN Gabungan (Jetson → NUC → Windows)

**Tujuan:** Skenario end-to-end paling realistis — publisher di Jetson,
monitor di NUC, dan *juga* monitor di Windows secara bersamaan.

```
┌──────────────┐   ZeroTier   ┌──────────────┐    LAN RJ45    ┌───────────────┐
│   Windows    │◄════════════►│    NUC       │◄══════════════►│   Jetson      │
│  (monitor 2) │  VPN Tunnel  │  (monitor 1) │  Direct Cable  │ (publisher)   │
│  10.101.x.x  │              │  10.101.143  │  192.168.100.1 │ 192.168.100.2 │
│              │              │      .111    │                │               │
└──────────────┘              └──────────────┘                └───────────────┘
```

### Langkah D.1 — Jalankan Publisher di Jetson

```bash
ssh humanoid@10.101.143.175
source /opt/ros/humble/setup.bash
source ~/.bashrc
cd ~/ros2_network_monitor
python3 dummy_publisher.py
```

### Langkah D.2 — Jalankan Monitor di NUC (menggunakan config LAN standar)

```bash
ssh brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
source ~/.bashrc
# .bashrc sudah mengarah ke cyclonedds.xml (LAN)
cd ~/ros2_network_monitor
python3 network_monitor.py
```

### Langkah D.3 — Jalankan Monitor di Windows (menggunakan config VPN)

```cmd
call C:\dev\ros2_jazzy\local_setup.bat
set ROS_DOMAIN_ID=30
set RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set CYCLONEDDS_URI=file:///C:/Users/Patarajah/Documents/IDE Antigravity/ros2_network_monitor/cyclonedds_vpn.xml

cd "C:\Users\Patarajah\Documents\IDE Antigravity\ros2_network_monitor"
python network_monitor.py
```

### Langkah D.4 — Bandingkan Hasil

Bandingkan output dari Monitor NUC vs Monitor Windows:

```
┌──────────────────┬───────────────┬─────────────────┐
│ Metrik           │ Monitor NUC   │ Monitor Windows │
├──────────────────┼───────────────┼─────────────────┤
│ Hz               │ ~50 Hz        │ ~50 Hz          │
│ Avg Latency      │ ~0.5 ms (LAN) │ ~25 ms (VPN)    │
│ Jitter           │ Rendah        │ Lebih tinggi    │
└──────────────────┴───────────────┴─────────────────┘
```

> Selisih latency antara keduanya ≈ overhead VPN ZeroTier.

---

## Menghentikan Program

Tekan `Ctrl+C` di masing-masing terminal. Kedua node akan shutdown dengan
aman dan menampilkan pesan konfirmasi.

```bash
# Jika Ctrl+C tidak berhenti (jarang terjadi):
ps aux | grep dummy_publisher
kill -9 <PID>

ps aux | grep network_monitor
kill -9 <PID>
```

---

## Ringkasan Perintah SSH Cepat

```bash
# SSH ke NUC (via ZeroTier)
ssh brone-ub@10.101.143.111

# SSH ke Jetson (via ZeroTier)
ssh humanoid@10.101.143.175

# SSH ke Jetson (dari dalam NUC, via kabel LAN)
ssh brone@192.168.100.2
```

---

## Struktur File

```
~/ros2_network_monitor/
├── dummy_publisher.py          # Node publisher (TDD mock, 50 Hz + timestamp)
├── network_monitor.py          # Monitor CLI (log teks di terminal)
├── network_monitor_gui.py      # Monitor GUI (web dashboard + HTTP server)
├── dashboard.html              # Frontend dashboard (Chart.js real-time)
├── cyclonedds_vpn.xml          # Config CycloneDDS untuk koneksi VPN (opsional)
└── README.md                   # Panduan ini
```

---

## Web GUI Dashboard

### Fitur

- **6 kartu metrik real-time** — Hz, Avg/Min/Max Latency, Jitter (Std), Total Pesan
- **2 grafik real-time** — Frekuensi (Hz) & Latency (ms) dengan history 2 menit
- **Deteksi clock skew** — Banner peringatan otomatis jika latency negatif
- **Status koneksi** — Indikator hijau (menerima data) / merah (terputus)
- **Zero dependencies** — Hanya butuh `rclpy` + `std_msgs` (sudah ada di ROS 2)
- **Cross-platform** — Jalan di Windows & Ubuntu, buka dari browser manapun
- **Threaded HTTP server** — Tidak memblokir terminal SSH lain

### Cara Menjalankan

**Terminal SSH 1 — Publisher:**
```bash
ssh brone-ub@10.101.143.111
source ~/.bashrc && unset CYCLONEDDS_URI    # unset untuk uji lokal
cd ~/ros2_network_monitor
python3 dummy_publisher.py
```

**Terminal SSH 2 — GUI Monitor:**
```bash
ssh brone-ub@10.101.143.111
source ~/.bashrc && unset CYCLONEDDS_URI
cd ~/ros2_network_monitor
python3 network_monitor_gui.py
```

**Browser di Windows/Ubuntu — buka:**
```
http://10.101.143.111:8080
```

> Ganti port dengan parameter: `python3 network_monitor_gui.py --ros-args -p http_port:=9090`

### Catatan Penting

- **Firewall:** Jika dashboard tidak bisa diakses, buka port:
  `sudo ufw allow 8080/tcp`
- **`unset CYCLONEDDS_URI`:** Wajib untuk uji lokal (alasan: lihat bagian Baseline)
- **Untuk skenario lintas mesin (A/B/D):** Jangan `unset`, biarkan CycloneDDS config aktif
