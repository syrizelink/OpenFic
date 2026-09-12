# OpenFic

![GitHub Repo stars](https://img.shields.io/github/stars/syrizelink/OpenFic)
![License](https://img.shields.io/badge/License-Apache_2.0-red)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![GitHub Release](https://img.shields.io/github/v/release/syrizelink/OpenFic?logo=githubactions&logoColor=white&color=yellow)
![Release Downloads](https://img.shields.io/github/downloads/syrizelink/OpenFic/total?logo=github&logoColor=white&label=Release%20downloads&color=yellow)
![PyPI - Version](https://img.shields.io/pypi/v/openfic?logo=pypi&logoColor=white&color=green)
[![QQ Group](https://img.shields.io/badge/QQ%20Group-1105304435-12B7F5?logo=qq&logoColor=white)](https://qun.qq.com/universal-share/share?ac=1&authKey=XxKBo33K1IAy%2FejDsGPWOn51pCNk1Bu1%2F2dtldtWCWSdPGor4tZkaboxgrGkz2BS&busi_data=eyJncm91cENvZGUiOiIxMTA1MzA0NDM1IiwidG9rZW4iOiJCY1NuV2s5d1B2QmI2R0ZiMldMbDE4MVRPV1puMFJlWjZIRlZrRjk4WGUwY2wvdUlaWEFPZ1cvV0lLbWl6d3JwIiwidWluIjoiMjUzMjEyNDQwNCJ9&data=B2VDUuvIYSScsKPwMeFB6txn6fj8I18zG6EKsmsrZDwPpmNCoJ7r5NTLtmUUf58MK3Lw9evkkPg28EglHJNONA&svctype=4&tempid=h5_group_info)

Bahasa Indonesia | [English](./README_EN.md)

**OpenFic** adalah alat Vibe Writing satu pintu yang lintas platform, ramah pengguna, dan AI Native, dibuat khusus untuk penulisan novel. Bangun latar, rancang tokoh, sesuaikan alur kerja, dan buat Agent menyesuaikan diri dengan proses menulis Anda, bukan sebaliknya.

![Demo Screenshot](./demo.png)


## Kapan Digunakan

> [!Tip]  
> *Gagasan rancangan OpenFic adalah membuat Agent terlibat mendalam dalam proses penulisan novel, bukan menghasilkan teks tanpa jiwa untuk Anda dengan sekali klik. Ini pertama-tama adalah alat penulisan novel yang ramah pengguna, dan baru setelah itu sebuah sistem AI Agent untuk penulisan.*

#### Cocok untuk keadaan berikut:

- Sedang menulis novel panjang atau menengah dan perlu merawat latar dunia, tokoh, petunjuk awal, serta informasi bab dalam jangka panjang
- Ingin Agent membantu Anda mengembangkan gagasan, memeriksa keterkaitan teks, dan melengkapi detail
- Menyediakan latar, gaya tulisan, dan arah alur cerita yang lengkap, lalu ingin Agent membantu mengubah inspirasi menjadi teks
- Anda punya alur kerja menulis sendiri dan ingin menyesuaikan Prompt, Agent, serta alur kerja sesuai kebutuhan
- Mementingkan penyimpanan data lokal, pengelolaan konteks, dan kolaborasi penulisan yang berkelanjutan

#### Tidak cocok untuk keadaan berikut:

- Memasukkan satu kalimat prompt lalu otomatis mendapat satu novel utuh; ini tidak realistis
- Terutama membutuhkan naskah pendek, konten media sosial, atau pembuatan teks umum sekali pakai
- Anda tidak berencana merawat informasi latar yang rumit, dan tidak membutuhkan konteks jangka panjang maupun pengelolaan alur kerja penulisan


## Fitur

- 🚀**Siap pakai**: pasang cepat dengan Docker atau pip, atau langsung pakai versi desktop, tanpa konfigurasi yang rumit
- ✒️**Dibuat khusus untuk menulis**: editor yang dioptimalkan dan dirancang untuk penulisan novel, memberi pengalaman mengetik yang praktis dan nyaman
- 🤝**Dukungan model yang menyeluruh**: terintegrasi mulus dengan model dari berbagai penyedia, atau model apa pun yang kompatibel dengan OpenAI API
- 📱**Antarmuka responsif**: antarmuka yang dirancang untuk berbagai platform, nikmati pengalaman mulus di desktop, seluler, dan peramban
- 🧩**Alur kerja yang dapat disesuaikan**: sistem Agent yang sangat dapat dikonfigurasi, ubah Prompt apa pun secara bebas, dan bangun alur kerja milik Anda
- 🤖**Penulisan kolaboratif manusia dan mesin**: penulisan berbantuan yang terintegrasi mendalam dengan Agent untuk mengembangkan gagasan, membangun alur, dan menyunting bersama, bukan pembuatan sekali klik yang bergantung keberuntungan
- 💾**Persistensi lokal**: semua data proyek disimpan di lokal, tanpa ketergantungan penyimpanan awan, sehingga data privat tetap aman
- 🧠**Pencarian semantik**: Agentic RAG berbasis vektor yang membuat Agent dapat mencari informasi lampau secara efisien pada proyek berskala jutaan kata
- ⚖️**Biaya jadi prioritas**: pengelolaan konteks berlapis dengan pemadatan cerdas, pemotongan dinamis, dan cache yang stabil untuk menekan biaya penggunaan sejauh mungkin


## Mulai Cepat

### 🐳 Docker (disarankan)

Pemasangan dengan cara kontainer untuk hosting sendiri adalah cara pemasangan yang disarankan.

```bash
docker run -d -p 8000:8000 -v "openfic:/data" --name openfic ghcr.io/syrizelink/openfic:latest
```


### 🐍 Python pip

> [!Warning]  
> Sebelum mulai, pastikan Anda sudah memasang Python 3.12+

#### 1. Pasang OpenFic

```bash
pip install openfic
```

#### 2. Jalankan layanan

```bash
openfic serve
```


### 🖥Aplikasi Desktop

Buka [Release Page](https://github.com/syrizelink/OpenFic/releases) untuk mengunduh aplikasi desktop, lalu jalankan secara native di sistem Anda tanpa langkah tambahan.

## Konfigurasi

Konfigurasi dibaca dari `<OPENFIC_DATA_DIR>/.env`, dengan bawaan `backend/data/.env`.
Lihat [`backend/.env.example`](.env.example) untuk daftar lengkapnya.

### Mesin retrieval dan CPU tanpa AVX

Pencarian bab bawaan memakai LanceDB, yang menuntut dukungan CPU x86-64-v2 (AVX)
lewat numpy dan pyarrow. Pada CPU yang hanya mendukung SSE2 — umum pada VPS
murah — proses akan mati dengan SIGILL.

Untuk lingkungan seperti itu, setel:

```bash
OPENFIC_CLOUD_ONLY=true
```

Nilai ini mengalihkan retrieval ke adapter SQLite FTS5 yang murni Python, tanpa
memuat pustaka native sama sekali. Konsekuensinya pencarian menjadi berbasis
kata kunci (BM25), bukan semantik: kueri "sebutkan pedang" berfungsi, sedangkan
"adegan bernuansa perpisahan" tidak.

Peralihan nilai ini mengubah bentuk kontrak indeks, sehingga indeks yang sudah
ada ditandai `needs_rebuild` lalu dibangun ulang otomatis.

## Kontribusi

Kontribusi dalam bentuk apa pun kami sambut! Jika Anda punya gagasan, saran, atau perbaikan kode, silakan kirim Issue atau Pull Request.

- **Melaporkan Bug**: jika Anda menemukan masalah apa pun, jelaskan keadaannya secara rinci di Issues
- **Mengajukan kebutuhan fitur**: punya gagasan fitur yang lebih baik? Bagikan kebutuhan Anda di Issues
- **Mengirim kode**: fork repositori ini, ubah kodenya, lalu kirim Pull Request

Lihat [CONTRIBUTING.md](./CONTRIBUTING.md) untuk panduan kontribusi yang lebih rinci.

## Star History

<a href="https://www.star-history.com/?repos=syrizelink%2FOpenFic&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=syrizelink/OpenFic&type=date&theme=dark&legend=top-left&sealed_token=JHQpP1A05gPA9RleC2GLLnXJ5mg_nQHq_VosoaeQPU2yPGneRUJNEyxaEy--2atezknlCUb5HxLE0HB31gJAOr1ezJZHYW92VUSlWh0Ej0bkt4Q3AWVUHQ" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=syrizelink/OpenFic&type=date&legend=top-left&sealed_token=JHQpP1A05gPA9RleC2GLLnXJ5mg_nQHq_VosoaeQPU2yPGneRUJNEyxaEy--2atezknlCUb5HxLE0HB31gJAOr1ezJZHYW92VUSlWh0Ej0bkt4Q3AWVUHQ" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=syrizelink/OpenFic&type=date&legend=top-left&sealed_token=JHQpP1A05gPA9RleC2GLLnXJ5mg_nQHq_VosoaeQPU2yPGneRUJNEyxaEy--2atezknlCUb5HxLE0HB31gJAOr1ezJZHYW92VUSlWh0Ej0bkt4Q3AWVUHQ" />
 </picture>
</a>

## Repobeats

![Repobeats](https://repobeats.axiom.co/api/embed/a3b67d74bb71044ef2385d65bc469090ee3e0fe6.svg "Repobeats analytics image")

## Ucapan Terima Kasih

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) - sumber inspirasi
- [oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) - rujukan Skill penulisan bawaan

## Komunitas

[LINUX DO](https://linux.do/)

QQ Group: [1105304435](https://qun.qq.com/universal-share/share?ac=1&authKey=XxKBo33K1IAy%2FejDsGPWOn51pCNk1Bu1%2F2dtldtWCWSdPGor4tZkaboxgrGkz2BS&busi_data=eyJncm91cENvZGUiOiIxMTA1MzA0NDM1IiwidG9rZW4iOiJCY1NuV2s5d1B2QmI2R0ZiMldMbDE4MVRPV1puMFJlWjZIRlZrRjk4WGUwY2wvdUlaWEFPZ1cvV0lLbWl6d3JwIiwidWluIjoiMjUzMjEyNDQwNCJ9&data=B2VDUuvIYSScsKPwMeFB6txn6fj8I18zG6EKsmsrZDwPpmNCoJ7r5NTLtmUUf58MK3Lw9evkkPg28EglHJNONA&svctype=4&tempid=h5_group_info)


## Lisensi

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
