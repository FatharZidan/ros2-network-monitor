# Panduan Perintah Monitoring ROS 2 — BRONE v2

## 📌 Ringkasan Konfigurasi Inti

- **Middleware DDS:** `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` (Wajib diset di Jetson & NUC agar tidak terjadi buffer error FastDDS/Fast-CDR).
- **Domain ID:** `ROS_DOMAIN_ID=30` (SOP Robot BRONE).
- **Time Synchronization:** Disinkronkan otomatis oleh `chrony` (tidak perlu `ntpdate` manual).
- **Tipe Pesan:** `std_msgs/msg/UInt8MultiArray` (Biner struct presisi tinggi).
- **Download CSV:** Tersedia tombol **"Download CSV"** di pojok kanan atas Web Dashboard (`:8765`), atau diekspor otomatis saat menggunakan mode CLI (`network_monitor.py`).

> 💡 **Rekomendasi Setup Sekali Jalan (Opsional tapi Memudahkan):**
> Masukkan ke `~/.bashrc` di NUC dan Jetson agar selalu aktif otomatis:
> ```bash
> echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
> echo "export ROS_DOMAIN_ID=30" >> ~/.bashrc
> ```

---

## 1. Uji Baseline / Lokal (Satu Komputer)

### A. Lokal JETSON (`jetson2jetson`)

**Terminal 1 — Publisher:**
```bash
ssh brone@10.101.143.169
source /opt/ros/humble/setup.bash
source ~/.bashrc
unset CYCLONEDDS_URI
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
cd ~/ros2_network_monitor

# Monitoring tanpa batas:
python3 dummy_publisher.py --topology jetson2jetson --samples 0

# Atau uji batch (contoh 1000 sampel):
python3 dummy_publisher.py --topology jetson2jetson --samples 1000
```

**Terminal 2 — Web GUI Monitor:**
```bash
ssh -L 8765:127.0.0.1:8765 brone@10.101.143.169
source /opt/ros/humble/setup.bash
source ~/.bashrc
unset CYCLONEDDS_URI
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
cd ~/ros2_network_monitor

python3 network_monitor_gui.py --ros-args -p topology:=jetson2jetson
```
👉 *Buka di browser: `http://10.101.143.169:8765` (atau `http://localhost:8765`)*

**Terminal 2 Alternatif — CLI Monitor (Batch & Auto-Export CSV):**
```bash
python3 network_monitor.py --topology jetson2jetson --samples 1000
```

---

### B. Lokal NUC (`nuc2nuc`)

**Terminal 1 — Publisher:**
```bash
ssh brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
source ~/.bashrc
unset CYCLONEDDS_URI
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
cd ~/ros2_network_monitor

python3 dummy_publisher.py --topology nuc2nuc --samples 0
```

**Terminal 2 — Web GUI Monitor:**
```bash
ssh -L 8765:127.0.0.1:8765 brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
source ~/.bashrc
unset CYCLONEDDS_URI
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
cd ~/ros2_network_monitor

python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc
```
👉 *Buka di browser: `http://10.101.143.111:8765` (atau `http://localhost:8765`)*

**Terminal 2 Alternatif — CLI Monitor (Batch & Auto-Export CSV):**
```bash
python3 network_monitor.py --topology nuc2nuc --samples 1000
```

---

## 2. Uji Lintas Mesin (JETSON ↔ NUC via ZeroTier)

### A. JETSON ➔ NUC (Jetson Mengirim, NUC Memonitor)

**Terminal 1 — JETSON (Publisher):**
```bash
ssh brone@10.101.143.169
source /opt/ros/humble/setup.bash
source ~/.bashrc
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=30
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_jetson.xml
cd ~/ros2_network_monitor

# Monitoring tanpa batas:
python3 dummy_publisher.py --topology jetson2nuc --samples 0

# Atau uji batch:
python3 dummy_publisher.py --topology jetson2nuc --samples 1000 --freq 50 --payload 128
```

**Terminal 2 — NUC (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
source ~/.bashrc
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=30
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_nuc.xml
cd ~/ros2_network_monitor

python3 network_monitor_gui.py --ros-args -p topology:=jetson2nuc
```
👉 *Buka di browser: `http://10.101.143.111:8765` (atau `http://localhost:8765`)*

**Terminal 2 Alternatif — NUC (CLI Monitor Auto-CSV):**
```bash
python3 network_monitor.py --topology jetson2nuc --samples 1000 --freq 50 --payload 128
```

---

### B. NUC ➔ JETSON (NUC Mengirim, Jetson Memonitor)

**Terminal 1 — NUC (Publisher):**
```bash
ssh brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
source ~/.bashrc
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=30
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_nuc.xml
cd ~/ros2_network_monitor

python3 dummy_publisher.py --topology nuc2jetson --samples 0
```

**Terminal 2 — JETSON (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone@10.101.143.169
source /opt/ros/humble/setup.bash
source ~/.bashrc
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=30
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_jetson.xml
cd ~/ros2_network_monitor

python3 network_monitor_gui.py --ros-args -p topology:=nuc2jetson
```
👉 *Buka di browser: `http://10.101.143.169:8765` (atau `http://localhost:8765`)*

---

## 3. Uji Beban & Stress Test (Variasi Parameter)

Untuk eksperimen performa batas sistem (misal menguji payload besar atau frekuensi tinggi):

```bash
# Contoh 1: 100 Hz, Payload 512 bytes
python3 dummy_publisher.py --topology nuc2nuc --freq 100 --payload 512 --samples 3000
python3 network_monitor.py --topology nuc2nuc --freq 100 --payload 512 --samples 3000

# Contoh 2: 500 Hz, Payload 1024 bytes (1 KB)
python3 dummy_publisher.py --topology nuc2nuc --freq 500 --payload 1024 --samples 5000
python3 network_monitor.py --topology nuc2nuc --freq 500 --payload 1024 --samples 5000

# Contoh 3: QoS Reliable (Menjamin zero packet loss)
python3 dummy_publisher.py --topology jetson2nuc --freq 50 --payload 256 --samples 1000 --qos reliable
python3 network_monitor.py --topology jetson2nuc --freq 50 --payload 256 --samples 1000 --qos reliable
```

---

## 4. Parameter Command Line Lengkap

| Parameter | Default | Keterangan |
|---|---|---|
| `--topology` | *(Wajib)* | `nuc2nuc`, `jetson2jetson`, `nuc2jetson`, `jetson2nuc` |
| `--freq` | `50` | Frekuensi publikasi (Hz) |
| `--payload` | `128` | Ukuran payload dalam bytes (minimum 16 bytes) |
| `--samples` | `1000` | Jumlah sampel pengujian (`0` = jalan terus tanpa batas) |
| `--warmup-seconds` | `3` | Waktu tunggu sebelum data mulai dicatat |
| `--qos` | `best_effort` | Profil keandalan: `best_effort` atau `reliable` |

---

## 5. Ringkasan Kapan Pakai `unset` vs `export CYCLONEDDS_URI`

| Kondisi Pengujian | Perintah DDS URI | Alasan |
|---|---|---|
| **Lokal (1 Komputer)** | `unset CYCLONEDDS_URI` | Memaksa DDS memakai antarmuka loopback lokal. |
| **Lintas Mesin (2 Komputer)** | `export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_xxx.xml` | Memaksa DDS mengarahkan paket ke IP target di jaringan. |
