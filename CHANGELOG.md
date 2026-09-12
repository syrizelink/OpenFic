# Changelog

## [0.11.1](https://github.com/syrizelink/OpenFic/compare/v0.11.0...v0.11.1) (2026-09-09)


### 🐛 Perbaikan Masalah

* **backend:** memperbaiki masalah event loop terblokir akibat cache tabel kata tiktoken ditulis ulang berulang ([#376](https://github.com/syrizelink/OpenFic/issues/376)) ([5a7c73b](https://github.com/syrizelink/OpenFic/commit/5a7c73b639b6e68bcc41f34e3704450a7d7dc7d5))
* **backend:** memperbaiki masalah endpoint kompatibel tidak dapat membaca konten penalaran ([#382](https://github.com/syrizelink/OpenFic/issues/382)) ([63418de](https://github.com/syrizelink/OpenFic/commit/63418de575d189e61ab3bc770748983ddf28075d))
* **desktop:** memperbaiki error direktori lingkungan runtime yang hilang saat uninstall ([#384](https://github.com/syrizelink/OpenFic/issues/384)) ([349f154](https://github.com/syrizelink/OpenFic/commit/349f154a55aaef9a9ec6a2a0ae12ada253236645))
* **frontend:** memperbaiki masalah pengaturan tidak tersimpan setelah pergantian tema pada sidebar ([#379](https://github.com/syrizelink/OpenFic/issues/379)) ([8f90d91](https://github.com/syrizelink/OpenFic/commit/8f90d91dbc855154edff2585a36f39ee353e54d0))
* **frontend:** memperbaiki masalah input pencarian dan Toast tidak memakai font proyek ([#392](https://github.com/syrizelink/OpenFic/issues/392)) ([6d8ab17](https://github.com/syrizelink/OpenFic/commit/6d8ab175ad9f7ec5c27eb21e9c31da927d953788))
* **frontend:** memperbaiki masalah konten tidak tampil akibat bahasa blok kode yang tidak dikenal ([#394](https://github.com/syrizelink/OpenFic/issues/394)) ([87d1292](https://github.com/syrizelink/OpenFic/commit/87d12921d6b0074e4b1f1d449c5ad17dd4dbe74b))
* **frontend:** memperbaiki masalah animasi pergantian sidebar kiri pada mobile yang tersendat ([#390](https://github.com/syrizelink/OpenFic/issues/390)) ([55b2513](https://github.com/syrizelink/OpenFic/commit/55b2513c893922443587e082abc756fd18832a9f))


### ⚡ Optimalisasi Performa

* **chapter:** optimalisasi performa pengurutan bab berskala besar ([#393](https://github.com/syrizelink/OpenFic/issues/393)) ([c9ef20f](https://github.com/syrizelink/OpenFic/commit/c9ef20f887ca0b26745f0bc39d07acb34a3f4e18))


### 📚 Dokumentasi

* **contributing:** melengkapi CONTRIBUTING.md ([#389](https://github.com/syrizelink/OpenFic/issues/389)) ([6fad139](https://github.com/syrizelink/OpenFic/commit/6fad139d8111d71ab48e88d08aecc5e71b257c65))


### 🔧 Lain-lain

* **agent:** optimalisasi deskripsi alat Agent ([#372](https://github.com/syrizelink/OpenFic/issues/372)) ([4361650](https://github.com/syrizelink/OpenFic/commit/436165018f73d7ab77c15f3865810b5aa08f1385))
* **config:** melengkapi opsi pengaturan pencarian daring ([#383](https://github.com/syrizelink/OpenFic/issues/383)) ([3d22ece](https://github.com/syrizelink/OpenFic/commit/3d22ece133a5b024e3bb501f3f04cb5e8a5adca1))
* **frontend:** menambahkan penyesuaian mobile untuk toolbar editor ([#388](https://github.com/syrizelink/OpenFic/issues/388)) ([b965128](https://github.com/syrizelink/OpenFic/commit/b9651283bb8d8dc46514d4960d3f3db9773a2520))
* **frontend:** melengkapi toolbar editor Markdown ([#373](https://github.com/syrizelink/OpenFic/issues/373)) ([8d4bc4e](https://github.com/syrizelink/OpenFic/commit/8d4bc4e7fc1c2cccd71cbb24a4ed392456180d0d))
* **frontend:** melengkapi toolbar editor bab ([#374](https://github.com/syrizelink/OpenFic/issues/374)) ([809a071](https://github.com/syrizelink/OpenFic/commit/809a071e34ed651e5177f31ac1b8a461a589edab))
* **frontend:** menambahkan gestur geser sidebar kiri pada mobile ([#391](https://github.com/syrizelink/OpenFic/issues/391)) ([39f9557](https://github.com/syrizelink/OpenFic/commit/39f9557cd386f2bac959386cc7fc8b75597a7d21))
* **notes:** menambahkan fitur impor-ekspor catatan ([#370](https://github.com/syrizelink/OpenFic/issues/370)) ([2eae5db](https://github.com/syrizelink/OpenFic/commit/2eae5dbe08dee4f2c2eae801a18ec41e7e576ff1))

## [0.11.0](https://github.com/syrizelink/OpenFic/compare/v0.10.2...v0.11.0) (2026-08-30)


### ✨ Fitur Baru

* **agent:** menambahkan panel rangkuman perubahan pada level sesi/giliran ([#366](https://github.com/syrizelink/OpenFic/issues/366)) ([e4344c3](https://github.com/syrizelink/OpenFic/commit/e4344c39fff0f4b51a727f29435cf5c3eb17e751))
* **agent:** menambahkan kemampuan pencarian daring dan pembacaan halaman web ([#354](https://github.com/syrizelink/OpenFic/issues/354)) ([d6bbca7](https://github.com/syrizelink/OpenFic/commit/d6bbca7eb848ff2a7632602550488138a26776c5))


### 🐛 Perbaikan Masalah

* **agent:** menstandarkan hasil write_plan dan memperbaiki masalah rencana hilang saat dikompresi ([#358](https://github.com/syrizelink/OpenFic/issues/358)) ([a6e419a](https://github.com/syrizelink/OpenFic/commit/a6e419ace227fb4ae69c7055b2ded09ffbe32c93))
* **backend:** memperbaiki pembacaan informasi versi pada deployment Docker ([#367](https://github.com/syrizelink/OpenFic/issues/367)) ([d475639](https://github.com/syrizelink/OpenFic/commit/d47563946cd823044851dfe2817a78d35f61c9ef))
* **desktop:** melengkapi pemeriksaan direktori instance lokal dan pembersihan pembaruan ([#364](https://github.com/syrizelink/OpenFic/issues/364)) ([b5c2e0b](https://github.com/syrizelink/OpenFic/commit/b5c2e0bbc38e08b7d525997a47797165d40648e4))


### ⚡ Optimalisasi Performa

* **backend:** optimalisasi performa kueri alat bab ([#356](https://github.com/syrizelink/OpenFic/issues/356)) ([c0a42a3](https://github.com/syrizelink/OpenFic/commit/c0a42a39925b9dbd8d54c6f748e2d983b90ede21))
* **storage:** optimalisasi performa kueri dashboard ([#355](https://github.com/syrizelink/OpenFic/issues/355)) ([87bdfb2](https://github.com/syrizelink/OpenFic/commit/87bdfb2a934a7bd86be18b6db8903f22cb443e20))


### 🔧 Lain-lain

* **agent:** menambahkan alat untuk menampilkan daftar sub-agen ([#359](https://github.com/syrizelink/OpenFic/issues/359)) ([945aebb](https://github.com/syrizelink/OpenFic/commit/945aebb7fc5a1a9ee301379082d18ca3ff7150b1))
* **api:** mendukung header permintaan provider kustom ([#352](https://github.com/syrizelink/OpenFic/issues/352)) ([4117498](https://github.com/syrizelink/OpenFic/commit/41174980b6b8477dca977f86a724f26023dafcf3))
* **editor:** mendukung tampilan nomor baris opsional pada editor bab ([#357](https://github.com/syrizelink/OpenFic/issues/357)) ([3991edf](https://github.com/syrizelink/OpenFic/commit/3991edf15320913776959d7575eff736a2080650))
* **import:** memperkuat alur impor file proyek ([#363](https://github.com/syrizelink/OpenFic/issues/363)) ([9288a24](https://github.com/syrizelink/OpenFic/commit/9288a24245d8952f2231b47281c1810dc6b0887a))
* **models:** optimalisasi pengalaman panel pengaturan provider dan model ([#362](https://github.com/syrizelink/OpenFic/issues/362)) ([1ef8c09](https://github.com/syrizelink/OpenFic/commit/1ef8c091d3ca30f08bd90892515e46dd8368aa7b))
* **model:** menambahkan provider OpenAI Compatible (Responses) ([#349](https://github.com/syrizelink/OpenFic/issues/349)) ([9a14ae2](https://github.com/syrizelink/OpenFic/commit/9a14ae2513422cdeda6417b3386cdf025fc0c175))
* **provider:** menambahkan provider Gemini Compatible ([#360](https://github.com/syrizelink/OpenFic/issues/360)) ([b6b2915](https://github.com/syrizelink/OpenFic/commit/b6b29157897ab989dc0e36d779d9c2a4b1204cf0))

## [0.10.2](https://github.com/syrizelink/OpenFic/compare/v0.10.1...v0.10.2) (2026-08-25)


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki batas jumlah persetujuan alat secara massal ([#347](https://github.com/syrizelink/OpenFic/issues/347)) ([832fc5c](https://github.com/syrizelink/OpenFic/commit/832fc5cf59ee6940b6a5f553cec5a972e9cd7f35))
* **agent:** menyeragamkan penanganan error alat ([#346](https://github.com/syrizelink/OpenFic/issues/346)) ([76a2038](https://github.com/syrizelink/OpenFic/commit/76a203868832932f29b175910c869596b1f56774))
* **agent:** mencegah ask_user menerima pertanyaan kosong yang menyebabkan interupsi ([#342](https://github.com/syrizelink/OpenFic/issues/342)) ([246c909](https://github.com/syrizelink/OpenFic/commit/246c909caf2c56958f2959ffb5c3095ab9d0ecbf))
* **backend:** memperbaiki URL penemuan model pada endpoint kompatibel ([#343](https://github.com/syrizelink/OpenFic/issues/343)) ([ea2b76d](https://github.com/syrizelink/OpenFic/commit/ea2b76dc2fc60ef70722c711f1da45788e8b6803))
* **desktop:** memperbaiki masalah webview preload tidak dapat dimuat pada sistem Linux ([#341](https://github.com/syrizelink/OpenFic/issues/341)) ([8ecbf62](https://github.com/syrizelink/OpenFic/commit/8ecbf620ac4e099ea8e0a89877de81d4953d29ce))
* **frontend:** memperbaiki konflik konversi tanda baca pada input komposisi IME ([#333](https://github.com/syrizelink/OpenFic/issues/333)) ([70e63e8](https://github.com/syrizelink/OpenFic/commit/70e63e81bf022e82a806d065cfe0ee78fcf495ff))


### ⚡ Optimalisasi Performa

* **test:** mempercepat eksekusi pengujian backend ([#331](https://github.com/syrizelink/OpenFic/issues/331)) ([338df55](https://github.com/syrizelink/OpenFic/commit/338df55405f3342e7585bcfdd5d793bb4b40790d))


### 🔧 Lain-lain

* **agent:** mendukung referensi Skill Command ([#329](https://github.com/syrizelink/OpenFic/issues/329)) ([82ed254](https://github.com/syrizelink/OpenFic/commit/82ed254d4c9ea622d55b114f688b7526afeba067))
* **auth:** menambahkan autentikasi kata sandi aplikasi yang opsional ([#339](https://github.com/syrizelink/OpenFic/issues/339)) ([d5f305e](https://github.com/syrizelink/OpenFic/commit/d5f305e8694c5b8cf51cd08d4fe0daa933e86a07))
* **openrouter:** menambahkan atribusi aplikasi ([#332](https://github.com/syrizelink/OpenFic/issues/332)) ([a883a36](https://github.com/syrizelink/OpenFic/commit/a883a369707af3fe688616e4d118f754cb3f2dbb))
* mengizinkan pilihan abaikan saat menjawab alat ask_user ([#334](https://github.com/syrizelink/OpenFic/issues/334)) ([be518ed](https://github.com/syrizelink/OpenFic/commit/be518ed9a4490cf65caf94c65998be84594ae95d))
* melengkapi statistik biaya model dan konfigurasi metadata ([#335](https://github.com/syrizelink/OpenFic/issues/335)) ([546ef3a](https://github.com/syrizelink/OpenFic/commit/546ef3af15beaefb08a333172373407f48057857))

## [0.10.1](https://github.com/syrizelink/OpenFic/compare/v0.10.0...v0.10.1) (2026-08-20)


### 🐛 Perbaikan Masalah

* **desktop:** memperbaiki masalah kegagalan pembaruan desktop akibat error 403 pada file wheel mirror PyPI ([#315](https://github.com/syrizelink/OpenFic/issues/315)) ([fd99c8b](https://github.com/syrizelink/OpenFic/commit/fd99c8b157be8251c3b3e4a21bfe4899b56c2fbe))
* **desktop:** membatasi tinggi konten error setup ([#314](https://github.com/syrizelink/OpenFic/issues/314)) ([adaefb9](https://github.com/syrizelink/OpenFic/commit/adaefb9b1b489597929654886807487a64cb7821))
* **openrouter:** memperbaiki masalah permintaan tersangkut akibat satuan timeout SDK OpenRouter yang tertukar ([#319](https://github.com/syrizelink/OpenFic/issues/319)) ([422b951](https://github.com/syrizelink/OpenFic/commit/422b951204e25538e6df752573f5e2f3b4fc327a))


### ⚡ Optimalisasi Performa

* **desktop:** memperkecil ukuran paket instalasi desktop ([#313](https://github.com/syrizelink/OpenFic/issues/313)) ([0ecbc54](https://github.com/syrizelink/OpenFic/commit/0ecbc5440c7bf24585886f4743dfb037109460ee))


### 📚 Dokumentasi

* memperbarui dokumentasi proyek ([#320](https://github.com/syrizelink/OpenFic/issues/320)) ([54f18e1](https://github.com/syrizelink/OpenFic/commit/54f18e1b1aa0bad44d178f68cd01fdeab0149e60))


### 🔧 Lain-lain

* **agent:** mengizinkan sesi Agent mengingat riwayat input dan draf yang belum terkirim ([#316](https://github.com/syrizelink/OpenFic/issues/316)) ([7c0b8f2](https://github.com/syrizelink/OpenFic/commit/7c0b8f27dbb52f895492a24ca1c799e8cd7a9823))
* **branding:** memperbarui ikon merek dan identitas aplikasi ([#321](https://github.com/syrizelink/OpenFic/issues/321)) ([e73b900](https://github.com/syrizelink/OpenFic/commit/e73b900ccb8bd2486a7f1920cacc598cf6bf141a))
* **desktop:** mendukung penghapusan instance ([#324](https://github.com/syrizelink/OpenFic/issues/324)) ([128b057](https://github.com/syrizelink/OpenFic/commit/128b0576b1e94e93bde7ff9a51c9ce727f4751e1))
* **desktop:** menambahkan navigasi maju-mundur pada aplikasi desktop ([#323](https://github.com/syrizelink/OpenFic/issues/323)) ([70b4af7](https://github.com/syrizelink/OpenFic/commit/70b4af7ced68bf43c086def2ddd37a8a36fda2f2))
* **editor:** menambahkan pengaturan pelengkapan otomatis simbol berpasangan ([#317](https://github.com/syrizelink/OpenFic/issues/317)) ([d5322ca](https://github.com/syrizelink/OpenFic/commit/d5322ca5435ead0ff3d6624e55d6af436b05129e))
* **editor:** menambahkan pengaturan indentasi otomatis paragraf ([#311](https://github.com/syrizelink/OpenFic/issues/311)) ([4024a67](https://github.com/syrizelink/OpenFic/commit/4024a67de7afc02048420ab374143c75997928ea))
* **editor:** menambahkan pengaturan konversi otomatis simbol setengah lebar ([#312](https://github.com/syrizelink/OpenFic/issues/312)) ([30fb71e](https://github.com/syrizelink/OpenFic/commit/30fb71e2ee050cc384c1635193db489f35582568))
* **frontend:** mendukung pelipatan panel pertanyaan ([#322](https://github.com/syrizelink/OpenFic/issues/322)) ([1b0b253](https://github.com/syrizelink/OpenFic/commit/1b0b253e0415a2e6847a787a7f3cdcd6b80dff0d))
* **vscode:** menambahkan konfigurasi task pengembangan VS Code ([#309](https://github.com/syrizelink/OpenFic/issues/309)) ([94503b9](https://github.com/syrizelink/OpenFic/commit/94503b921f42ab8a61b98365889929d4979477b6))

## [0.10.0](https://github.com/syrizelink/OpenFic/compare/v0.9.2...v0.10.0) (2026-08-16)


### ✨ Fitur Baru

* **agent:** mendukung identitas kustom untuk Agent utama (warna dan ikon) ([#282](https://github.com/syrizelink/OpenFic/issues/282)) ([b802c4d](https://github.com/syrizelink/OpenFic/commit/b802c4d2543938a6fc61fc92c03754d3e9f8ae55))
* **agent:** mendukung cakupan aturan global dan proyek ([#269](https://github.com/syrizelink/OpenFic/issues/269)) ([0fb578a](https://github.com/syrizelink/OpenFic/commit/0fb578aa9c7ace66436f71331029dc82a76b316f))
* **desktop:** mendukung pencadangan, migrasi, pemulihan data, dan direktori data kustom ([#275](https://github.com/syrizelink/OpenFic/issues/275)) ([23a1fac](https://github.com/syrizelink/OpenFic/commit/23a1fac7e14d9184ebf2e583a8d451ef068cb80a))
* **fonts:** memperkenalkan dukungan font fontsource ([#294](https://github.com/syrizelink/OpenFic/issues/294)) ([c135ee3](https://github.com/syrizelink/OpenFic/commit/c135ee338975bf3330f179e3eba360ad12727a22))
* **settings:** mendukung ukuran font dasar dan ukuran font editor kustom ([#300](https://github.com/syrizelink/OpenFic/issues/300)) ([ac6da38](https://github.com/syrizelink/OpenFic/commit/ac6da382907886940fb17121d4a2b5bf6742cbcc))
* **telemetry:** mengintegrasikan telemetri error jarak jauh PostHog ([#305](https://github.com/syrizelink/OpenFic/issues/305)) ([08d47ae](https://github.com/syrizelink/OpenFic/commit/08d47aef1bd421993c3b2a952b69a2b468cbd8eb))


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki masalah anomali pembatalan dan pemulihan akibat race condition siklus hidup sesi ([#307](https://github.com/syrizelink/OpenFic/issues/307)) ([c1430df](https://github.com/syrizelink/OpenFic/commit/c1430df5a6a6181942f7327206bf51e3c5ba5bc2))
* **agent:** memperbaiki masalah konflik unique constraint saat pemanggilan alat paralel ([#271](https://github.com/syrizelink/OpenFic/issues/271)) ([5dbe377](https://github.com/syrizelink/OpenFic/commit/5dbe3772a78ac56be85ae19ae23881185c20e4b4))
* **agent:** jumlah alat yang melebihi batas tidak lagi menghentikan sesi dan mengembalikan hasil error ([#293](https://github.com/syrizelink/OpenFic/issues/293)) ([b35a744](https://github.com/syrizelink/OpenFic/commit/b35a744e702e30a02b488f9948c433602ae3ff2a))
* **backend:** memperbaiki masalah respons panjang LLM terputus oleh timeout ([#277](https://github.com/syrizelink/OpenFic/issues/277)) ([3259325](https://github.com/syrizelink/OpenFic/commit/32593253ba58143731dba5eb8f359b82234353c1))
* **db:** memperbaiki masalah gagal start akibat ukuran checkpoints.db membengkak ([#303](https://github.com/syrizelink/OpenFic/issues/303)) ([8c7cc10](https://github.com/syrizelink/OpenFic/commit/8c7cc1000ee2566845439be409eb4157c49e48cd))
* **desktop:** coba ulang otomatis saat instalasi uv mengalami error sertifikat TLS ([#292](https://github.com/syrizelink/OpenFic/issues/292)) ([79bad9b](https://github.com/syrizelink/OpenFic/commit/79bad9b56e3a149aa0e66b3ba842ba8a9abe4736))
* **frontend:** memperbaiki masalah crash maximum update depth pada rendering streaming streamdown ([#272](https://github.com/syrizelink/OpenFic/issues/272)) ([ab4b9f5](https://github.com/syrizelink/OpenFic/commit/ab4b9f55c0e108998252747b0f54be6a5b62d2b4))
* **frontend:** memperbaiki masalah inisialisasi yang tersangkut dan memperkuat informasi diagnostik kegagalan koneksi ([#287](https://github.com/syrizelink/OpenFic/issues/287)) ([04acb43](https://github.com/syrizelink/OpenFic/commit/04acb43764c2b1261a2de7b4ee2a27acfed4e03b))
* **frontend:** memperbaiki masalah toolbar giliran Assistant sebelumnya hilang setelah mengirim pesan baru ([#273](https://github.com/syrizelink/OpenFic/issues/273)) ([ae8eda2](https://github.com/syrizelink/OpenFic/commit/ae8eda2d162e6e65057f20ecc1582055548789f7))
* **frontend:** menutup dropdown tidak lagi ikut menutup panel pengaturan ([#297](https://github.com/syrizelink/OpenFic/issues/297)) ([c4e0b47](https://github.com/syrizelink/OpenFic/commit/c4e0b479a5642c7804dbdf68d448b913605284a1))
* **projects:** memperbaiki masalah paginasi, pencarian, dan pengurutan tidak berfungsi akibat daftar proyek tidak termuat sepenuhnya ([#284](https://github.com/syrizelink/OpenFic/issues/284)) ([82af99e](https://github.com/syrizelink/OpenFic/commit/82af99e687ff0d57842a70489d39146eb5191059))


### ⚡ Optimalisasi Performa

* **backend:** optimalisasi performa endpoint status indeks pencarian dan daftar provider model ([#291](https://github.com/syrizelink/OpenFic/issues/291)) ([c77b264](https://github.com/syrizelink/OpenFic/commit/c77b264eafc2c15e78793bd01d5cc32f6d7e4437))


### ✅ Pengujian

* **desktop:** menambahkan mode pengembangan lokal berbasis backend dari kode sumber ([#304](https://github.com/syrizelink/OpenFic/issues/304)) ([84d63f1](https://github.com/syrizelink/OpenFic/commit/84d63f1aa6905896596818427f3f3275bcebc40e))
* **frontend:** menambahkan pengujian E2E siklus hidup sesi Agent ([#308](https://github.com/syrizelink/OpenFic/issues/308)) ([9478baf](https://github.com/syrizelink/OpenFic/commit/9478baf2f46317bd859deb21042c0bb02ce55441))

## [0.9.2](https://github.com/syrizelink/OpenFic/compare/v0.9.1...v0.9.2) (2026-08-08)


### 🐛 Perbaikan Masalah

* **agent_runtime:** memperbaiki masalah sesi macet akibat pemanggilan LLM tanpa proteksi timeout dan percobaan ulang tanpa kendali ([#261](https://github.com/syrizelink/OpenFic/issues/261)) ([46535a0](https://github.com/syrizelink/OpenFic/commit/46535a0dbd652aad50369657d8e297aad3f4b48f))
* **agent:** memperbaiki masalah sesi berstatus terhenti dan tertunda tidak dapat dilanjutkan ([#267](https://github.com/syrizelink/OpenFic/issues/267)) ([6029bc3](https://github.com/syrizelink/OpenFic/commit/6029bc37a53cff4054ed08f7dcca626b29398453))
* **agent:** memperbaiki masalah pemanggilan alat tidak dieksekusi secara paralel ([#266](https://github.com/syrizelink/OpenFic/issues/266)) ([aefcd90](https://github.com/syrizelink/OpenFic/commit/aefcd90f1004f2bf8af887ff785d8532eb982492))
* **agent:** membatasi tinggi daftar agen dan mendukung scroll ([#268](https://github.com/syrizelink/OpenFic/issues/268)) ([fa44696](https://github.com/syrizelink/OpenFic/commit/fa44696ea94d7b65c16e6d07f7a88642e3e8a7b2))
* **frontend:** memperbaiki masalah rentang tanggal dan label grafik dasbor yang saling bertumpuk ([#264](https://github.com/syrizelink/OpenFic/issues/264)) ([e3996ba](https://github.com/syrizelink/OpenFic/commit/e3996ba34703bb7e92b86b7e03f3feb6e98fe3c8))
* **frontend:** memperbaiki masalah teks yang ditempel dalam satu baris terpecah menjadi baris baru ([#258](https://github.com/syrizelink/OpenFic/issues/258)) ([45c3d6a](https://github.com/syrizelink/OpenFic/commit/45c3d6a19950dfd9f57c4d9bd3164f428453bba5))
* **frontend:** memperbaiki masalah salin-tempel tidak dapat dipakai akibat klik menu editor mobile tidak berfungsi ([#260](https://github.com/syrizelink/OpenFic/issues/260)) ([ba4ba07](https://github.com/syrizelink/OpenFic/commit/ba4ba07c0e00723e400ec476d714abc476492174))


### ⚡ Optimalisasi Performa

* **frontend:** virtualisasi daftar pesan Agent dan penggabungan rendering inkremental streaming ([#257](https://github.com/syrizelink/OpenFic/issues/257)) ([87aa448](https://github.com/syrizelink/OpenFic/commit/87aa448add26bce1dfb9dc925a6db72473d63ebd))
* **world-info:** virtualisasi daftar entri buku dunia dan optimalisasi pengurutan seret ([#254](https://github.com/syrizelink/OpenFic/issues/254)) ([ad94f34](https://github.com/syrizelink/OpenFic/commit/ad94f340c043999d5f8d6dc25580c559cec7edb0))


### 🔧 Lain-lain

* **agent:** menambahkan penghitung waktu sesi ([#262](https://github.com/syrizelink/OpenFic/issues/262)) ([70e9652](https://github.com/syrizelink/OpenFic/commit/70e96528066389d7cb30329be6bbcd2d455f34e3))
* menambahkan opsi kompresi prompt sistem ([#263](https://github.com/syrizelink/OpenFic/issues/263)) ([5dbc83d](https://github.com/syrizelink/OpenFic/commit/5dbc83d2ef45ef341cd71b295664194a1934642d))

## [0.9.1](https://github.com/syrizelink/OpenFic/compare/v0.9.0...v0.9.1) (2026-08-05)


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki masalah konten panel pertanyaan ask_user tidak dapat di-scroll ([#249](https://github.com/syrizelink/OpenFic/issues/249)) ([2921d0a](https://github.com/syrizelink/OpenFic/commit/2921d0aa743aaf418d07277bed9f59af67508f57))
* **backend:** memperbaiki masalah pengujian backend terlalu lama akibat fixture uji diinisialisasi berulang ([#241](https://github.com/syrizelink/OpenFic/issues/241)) ([a355e7f](https://github.com/syrizelink/OpenFic/commit/a355e7f16a5afc14da98cc238fc4a021a9e73973))
* **desktop:** memperbaiki masalah startup terhenti akibat kegagalan koneksi Socket pertama ([#248](https://github.com/syrizelink/OpenFic/issues/248)) ([7b84765](https://github.com/syrizelink/OpenFic/commit/7b847652037b165f3f7129e59c3564ce617a290c))
* **desktop:** memperbaiki masalah jendela tampil terlambat saat startup ([#246](https://github.com/syrizelink/OpenFic/issues/246)) ([6d0e05f](https://github.com/syrizelink/OpenFic/commit/6d0e05f97753a3bcdd329be6f9a311b07714b4b6))
* **desktop:** memperbaiki masalah error pemeriksaan akibat metadata pembaruan yang hilang ([#239](https://github.com/syrizelink/OpenFic/issues/239)) ([3b77aab](https://github.com/syrizelink/OpenFic/commit/3b77aabe38134b34f46331d687fd0ca7ba4e8217))
* **index:** memperbaiki masalah penyimpanan konfigurasi chunking memakai nilai input lama ([#250](https://github.com/syrizelink/OpenFic/issues/250)) ([ed75ce4](https://github.com/syrizelink/OpenFic/commit/ed75ce46a9be88a6044277d74abf5fe11123bf16))


### 👷 CI/CD

* **desktop:** memperbaiki masalah paket rilis rusak akibat build multi-arsitektur ([#247](https://github.com/syrizelink/OpenFic/issues/247)) ([7ffe8cd](https://github.com/syrizelink/OpenFic/commit/7ffe8cd1a254e2c2b892bb806d6c83e75edd156f))

## [0.9.0](https://github.com/syrizelink/OpenFic/compare/v0.8.1...v0.9.0) (2026-08-04)


### ✨ Fitur Baru

* **agent:** mendukung input lampiran gambar pada pesan pengguna ([#229](https://github.com/syrizelink/OpenFic/issues/229)) ([2c12697](https://github.com/syrizelink/OpenFic/commit/2c126978b101dc3c76b43556e7017084f27f97f2))
* **desktop:** menambahkan dukungan internasionalisasi lapisan shell ([#223](https://github.com/syrizelink/OpenFic/issues/223)) ([90f26c1](https://github.com/syrizelink/OpenFic/commit/90f26c16a764c941124a3e70c8b2693b32a5f1d9))


### 🐛 Perbaikan Masalah

* **editor:** memperbaiki masalah klik pada isi utama di mobile memanggil keyboard berulang ([#226](https://github.com/syrizelink/OpenFic/issues/226)) ([79d03fa](https://github.com/syrizelink/OpenFic/commit/79d03fa3c9f32dc8183e7b2ce234d747c12bef5d))
* **providers:** memperbaiki masalah URL endpoint sebagian provider hilang di dalam direktori ([#230](https://github.com/syrizelink/OpenFic/issues/230)) ([0006c90](https://github.com/syrizelink/OpenFic/commit/0006c906b8c878c07859d3e2b7afda02f4b2e2a1))
* **storage:** membersihkan data runtime terkait basis data ([#238](https://github.com/syrizelink/OpenFic/issues/238)) ([b8d2ca5](https://github.com/syrizelink/OpenFic/commit/b8d2ca5d58d64ecaf2acee919a0638104b0dce72))
* **summary:** memperbaiki masalah ringkasan rentang hilang akibat penghapusan bab lintas volume ([#225](https://github.com/syrizelink/OpenFic/issues/225)) ([9ecaa07](https://github.com/syrizelink/OpenFic/commit/9ecaa07fb38e9eb845135aabe0336d21adc0966c))


### 🔧 Lain-lain

* **desktop:** menambahkan menu bar aplikasi desktop ([#221](https://github.com/syrizelink/OpenFic/issues/221)) ([0d9bbe8](https://github.com/syrizelink/OpenFic/commit/0d9bbe8dc9f5cfb186cf2a196b40b4d577c113b1))

## [0.8.1](https://github.com/syrizelink/OpenFic/compare/v0.8.0...v0.8.1) (2026-07-31)


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki masalah konfigurasi sesi lama tidak dapat dipulihkan ([#202](https://github.com/syrizelink/OpenFic/issues/202)) ([ac9a59b](https://github.com/syrizelink/OpenFic/commit/ac9a59bea251a6bed4fb4ffcde005e74ee665151))
* **agent:** memperbaiki masalah kegagalan pencocokan escape spasi pada alat edit ([#214](https://github.com/syrizelink/OpenFic/issues/214)) ([649b87b](https://github.com/syrizelink/OpenFic/commit/649b87b801458bfd3b1c44e84215a299b8eaa174))
* **agent:** memperbaiki masalah pengaturan sesi tetap terkunci setelah restart ([#216](https://github.com/syrizelink/OpenFic/issues/216)) ([33555ff](https://github.com/syrizelink/OpenFic/commit/33555ff2c4d3a369938fd95e22fe64f276320a64))
* **dashboard:** memperbaiki masalah waktu catatan pemanggilan tidak dikonversi ke zona waktu ([#204](https://github.com/syrizelink/OpenFic/issues/204)) ([da977a8](https://github.com/syrizelink/OpenFic/commit/da977a8311b8effbed9506f204bb97eb2d8af6d7))
* **desktop:** memperbaiki anomali verifikasi runtime dan paket instalasi macOS ([#215](https://github.com/syrizelink/OpenFic/issues/215)) ([8ebac44](https://github.com/syrizelink/OpenFic/commit/8ebac44ab083b00b2de394f740badcc45c8773a0))
* **desktop:** memperbaiki masalah kegagalan koneksi proxy Socket backend lokal ([#209](https://github.com/syrizelink/OpenFic/issues/209)) ([7ffbd78](https://github.com/syrizelink/OpenFic/commit/7ffbd78ea937e45a93d4faa571ef1434050f9f98))
* **frontend:** beralih tab secara otomatis setelah membuat tokoh baru ([#191](https://github.com/syrizelink/OpenFic/issues/191)) ([8f35b51](https://github.com/syrizelink/OpenFic/commit/8f35b51b38670982764b7615d64106d9944329ee))


### 🔧 Lain-lain

* **editor:** optimalisasi pengalaman editor ([#219](https://github.com/syrizelink/OpenFic/issues/219)) ([f3554d4](https://github.com/syrizelink/OpenFic/commit/f3554d47ea549dffebda9ad4f2289dc904cdfa6f))
* **provider:** menambahkan provider Anthropic Compatible ([#208](https://github.com/syrizelink/OpenFic/issues/208)) ([2000f79](https://github.com/syrizelink/OpenFic/commit/2000f79d522bd4140994bc3ce1c59799f85baa30))
* **skills:** optimalisasi pengalaman konfigurasi skill ([#218](https://github.com/syrizelink/OpenFic/issues/218)) ([d7976c5](https://github.com/syrizelink/OpenFic/commit/d7976c583bdd3bf6d3a67c9efc3231b941d4c167))
* optimalisasi pengalaman daftar tokoh dan buku dunia ([#212](https://github.com/syrizelink/OpenFic/issues/212)) ([191ed05](https://github.com/syrizelink/OpenFic/commit/191ed05888ced345ca4a0b78f58dfacc8b832ab4))

## [0.8.0](https://github.com/syrizelink/OpenFic/compare/v0.7.6...v0.8.0) (2026-07-29)


### ✨ Fitur Baru

* **backend:** memperkenalkan mekanisme pencocokan fuzzy dan normalisasi untuk alat edit ([#165](https://github.com/syrizelink/OpenFic/issues/165)) ([5805078](https://github.com/syrizelink/OpenFic/commit/580507862debbe66d7ea221fc6deb339da71c211))
* **import:** mendukung impor TXT per volume ([#197](https://github.com/syrizelink/OpenFic/issues/197)) ([4c781ce](https://github.com/syrizelink/OpenFic/commit/4c781ce36a2baa4b5b1f8d2e82e51b72b659f28f))
* **writing:** mendukung ekspor bab ([#195](https://github.com/syrizelink/OpenFic/issues/195)) ([44171e8](https://github.com/syrizelink/OpenFic/commit/44171e86010c858540b2a23e78e11d01e1ef5532))


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki masalah penyegaran alat yang tidak berfungsi ([#185](https://github.com/syrizelink/OpenFic/issues/185)) ([905aae2](https://github.com/syrizelink/OpenFic/commit/905aae2574d2dd2dc15ffd771d0aa00f0cdc0c3e))
* **agent:** memperbaiki masalah status sidebar hilang akibat perpindahan antar halaman ([#178](https://github.com/syrizelink/OpenFic/issues/178)) ([22b9a37](https://github.com/syrizelink/OpenFic/commit/22b9a37c018ab64828cc7fdb97cbc1fa2b923d7e))
* **agent:** membersihkan checkpoint sesi yang tidak terjangkau ([#184](https://github.com/syrizelink/OpenFic/issues/184)) ([8908120](https://github.com/syrizelink/OpenFic/commit/890812052a3542dd5a1e799753206d67f108cf54))
* **agent:** menghindari konflik status pesan biasa pada sesi yang terhenti ([#177](https://github.com/syrizelink/OpenFic/issues/177)) ([787669b](https://github.com/syrizelink/OpenFic/commit/787669b51dc6a6a1e6b34184a6acf3e38504d854))
* **backend:** memperbaiki masalah kegagalan pemuatan tabel tokenisasi pada lingkungan offline ([#187](https://github.com/syrizelink/OpenFic/issues/187)) ([169d40b](https://github.com/syrizelink/OpenFic/commit/169d40b7410ef238f18cb669936e17473b7696cd))
* **ci:** menghapus validasi wajib daftar periksa mandiri PR ([#180](https://github.com/syrizelink/OpenFic/issues/180)) ([54df8c1](https://github.com/syrizelink/OpenFic/commit/54df8c1635f8ff1d7ba37f2289649ab0758af9bd))
* **ci:** melewati pemeriksaan PR rilis ([#174](https://github.com/syrizelink/OpenFic/issues/174)) ([2286422](https://github.com/syrizelink/OpenFic/commit/22864220d8f9732255587c3c921e0b21132a5d2d))
* **desktop:** optimalisasi alur koneksi runtime ([#199](https://github.com/syrizelink/OpenFic/issues/199)) ([83c78ad](https://github.com/syrizelink/OpenFic/commit/83c78ad119f3cc0c083fb15312af19673d3b4340))
* **desktop:** memperbaiki masalah kegagalan instalasi lingkungan runtime akibat tar tidak ada pada sistem ([#188](https://github.com/syrizelink/OpenFic/issues/188)) ([9685c19](https://github.com/syrizelink/OpenFic/commit/9685c19d4058a3083a29d54dc00455110ab768de))
* **desktop:** melengkapi penanganan informasi debug lingkungan runtime ([#196](https://github.com/syrizelink/OpenFic/issues/196)) ([39f3e55](https://github.com/syrizelink/OpenFic/commit/39f3e55653e30d2cba7dece7425839a4ebae4d75))
* **frontend:** memperbaiki penanganan baris baru pada papan klip editor ([#189](https://github.com/syrizelink/OpenFic/issues/189)) ([95daf32](https://github.com/syrizelink/OpenFic/commit/95daf32c59fc4931dd52dec07f7737e76661b676))
* **providers:** menghindari permintaan ikon memblokir operasi koneksi ([#183](https://github.com/syrizelink/OpenFic/issues/183)) ([70d9419](https://github.com/syrizelink/OpenFic/commit/70d9419832496b519ad629abf062fde3063d7b70))


### 🔧 Lain-lain

* **agent:** melengkapi sidebar Agent pada halaman tokoh ([#176](https://github.com/syrizelink/OpenFic/issues/176)) ([ad4988e](https://github.com/syrizelink/OpenFic/commit/ad4988e85adedcc96911fca85338eff48daad488))
* **backend:** menambahkan dukungan intensitas berpikir untuk provider OpenAI Compatible ([#192](https://github.com/syrizelink/OpenFic/issues/192)) ([195615f](https://github.com/syrizelink/OpenFic/commit/195615f4e22f0c33442e96d072a726de7363599d))
* **editor:** menambahkan batas panjang untuk satu konten isi utama ([#193](https://github.com/syrizelink/OpenFic/issues/193)) ([cb87f42](https://github.com/syrizelink/OpenFic/commit/cb87f42a8803584e664519696ddce6aca6883def))


### 👷 CI/CD

* menambahkan alur kerja pemeriksaan PR ([#172](https://github.com/syrizelink/OpenFic/issues/172)) ([17ce3f7](https://github.com/syrizelink/OpenFic/commit/17ce3f752348dd0c965ae9b6c360b48cedd7e22d))

## [0.7.6](https://github.com/syrizelink/OpenFic/compare/v0.7.5...v0.7.6) (2026-07-26)


### 🐛 Perbaikan Masalah

* **backend:** memperbaiki masalah event tugas latar belakang pada Windows tidak tersinkronisasi secara real-time ([#148](https://github.com/syrizelink/OpenFic/issues/148)) ([f4e83e1](https://github.com/syrizelink/OpenFic/commit/f4e83e1c2e8affb07029750c64d2d6bd0f1779b3))
* **backend:** memperbaiki anomali konfigurasi runtime server pengembangan ([#152](https://github.com/syrizelink/OpenFic/issues/152)) ([e5e93ec](https://github.com/syrizelink/OpenFic/commit/e5e93ec324ca28ae0e6e06e698c59e97367da7b8))
* **backend:** memperbaiki masalah penggunaan token streaming sebagian provider yang hilang ([#158](https://github.com/syrizelink/OpenFic/issues/158)) ([16376e9](https://github.com/syrizelink/OpenFic/commit/16376e9baa618cc91ce74217f5a354e74ec01d9f))
* **desktop:** memperbaiki masalah tema dan font aplikasi desktop tidak dapat tersinkronisasi dengan frontend ([#157](https://github.com/syrizelink/OpenFic/issues/157)) ([a2f8ebf](https://github.com/syrizelink/OpenFic/commit/a2f8ebf495a67fa68d30c181fcdcdc6bd4afe70f))


### 📚 Dokumentasi

* memperbarui struktur bab README ([#155](https://github.com/syrizelink/OpenFic/issues/155)) ([154fab7](https://github.com/syrizelink/OpenFic/commit/154fab748fd17b448cba173821234b7bc0acf70c))


### 🔧 Lain-lain

* **desktop:** menambahkan kemampuan mengingat status jendela ([#159](https://github.com/syrizelink/OpenFic/issues/159)) ([eb0e1a4](https://github.com/syrizelink/OpenFic/commit/eb0e1a4816bcd6d9b0682a8c96190eb52e3fc3a6))
* menambahkan templat Issue terstruktur ([#156](https://github.com/syrizelink/OpenFic/issues/156)) ([9e3b8ad](https://github.com/syrizelink/OpenFic/commit/9e3b8ad04912331507efa742d9963b7f1ed72883))

## [0.7.5](https://github.com/syrizelink/OpenFic/compare/v0.7.4...v0.7.5) (2026-07-26)


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki masalah pengaturan tetap terkunci setelah sesi berakhir ([#137](https://github.com/syrizelink/OpenFic/issues/137)) ([103c392](https://github.com/syrizelink/OpenFic/commit/103c392043f2eb246a974e431e40d0e15058a391))
* **backend:** memperbaiki masalah kegagalan pemanggilan model akibat penimpaan alamat Ollama Cloud ([#146](https://github.com/syrizelink/OpenFic/issues/146)) ([b5d116d](https://github.com/syrizelink/OpenFic/commit/b5d116d065dfa9db24ee8635a8d97b6cb8e2e9cd))
* **backend:** memperbaiki masalah antrean tugas latar belakang Windows terblokir ([#147](https://github.com/syrizelink/OpenFic/issues/147)) ([cf1ffa1](https://github.com/syrizelink/OpenFic/commit/cf1ffa1e0c7b47e1c38c7a7019bcb8e91f38791f))
* **desktop:** menambahkan sumber unduhan lokal untuk lingkungan runtime aplikasi desktop ([#126](https://github.com/syrizelink/OpenFic/issues/126)) ([5ba142e](https://github.com/syrizelink/OpenFic/commit/5ba142e50d5fef9f6f425d56cc5612264fe09d14))
* **frontend:** memperbaiki masalah status sakelar buku dunia yang kacau ([#138](https://github.com/syrizelink/OpenFic/issues/138)) ([7d5eb27](https://github.com/syrizelink/OpenFic/commit/7d5eb27da67edb5fdb3cc0aed4649a10892c08ae))
* **frontend:** memperbaiki masalah proyek yang sudah dihapus masih dapat dibuka ([#129](https://github.com/syrizelink/OpenFic/issues/129)) ([0542e8f](https://github.com/syrizelink/OpenFic/commit/0542e8faeab65ae34292ac6d329a61e7772a4e68))
* **frontend:** memperbaiki masalah konten editan prompt hilang dan tidak adanya notifikasi perubahan lokal ([#140](https://github.com/syrizelink/OpenFic/issues/140)) ([954d552](https://github.com/syrizelink/OpenFic/commit/954d5529c5941ac3172cf5a3b6b1d1cb636431db))
* **frontend:** memperbaiki anomali resolusi alamat sumber daya backend pada aplikasi desktop ([#136](https://github.com/syrizelink/OpenFic/issues/136)) ([09c570f](https://github.com/syrizelink/OpenFic/commit/09c570f4ac0b96b88427eed48de76da80ef9e525))
* **frontend:** membatalkan penyaringan tipe tugas provider ([#143](https://github.com/syrizelink/OpenFic/issues/143)) ([f582c8e](https://github.com/syrizelink/OpenFic/commit/f582c8ef1b4bd98e3e3ee4f461fb4e0341f7ed23))
* **storage:** memperbaiki konflik pembaruan pengurutan bab ([#141](https://github.com/syrizelink/OpenFic/issues/141)) ([dade8e8](https://github.com/syrizelink/OpenFic/commit/dade8e899dbddf6ae8ab8eae190aa1a3e81be034))


### 🔧 Lain-lain

* **frontend:** menambahkan opsi font bawaan sistem ([#128](https://github.com/syrizelink/OpenFic/issues/128)) ([3980ee2](https://github.com/syrizelink/OpenFic/commit/3980ee2af3d85c66016b0d2ada45c7058596ef8c))

## [0.7.4](https://github.com/syrizelink/OpenFic/compare/v0.7.3...v0.7.4) (2026-07-25)


### 🐛 Perbaikan Masalah

* **agent:** optimalisasi indikator status berjalan sesi ([#122](https://github.com/syrizelink/OpenFic/issues/122)) ([04c6e2e](https://github.com/syrizelink/OpenFic/commit/04c6e2e6639c21594a90c9d5d9a5fe607c7a9dcc))
* **agent:** optimalisasi animasi perluasan pesan pengguna ([#120](https://github.com/syrizelink/OpenFic/issues/120)) ([00d9cc8](https://github.com/syrizelink/OpenFic/commit/00d9cc89a12984462f5a8eb80d0b3d372aa22446))
* **agent:** memperbaiki masalah jumlah bab volume tidak tersinkronisasi saat rollback ([#117](https://github.com/syrizelink/OpenFic/issues/117)) ([0e9bf90](https://github.com/syrizelink/OpenFic/commit/0e9bf908fb4f323f8737bcd7866ac54c4130e669))
* **agent:** memperbaiki sesi zombi yang disebabkan pesan anomali ([#123](https://github.com/syrizelink/OpenFic/issues/123)) ([84b95fe](https://github.com/syrizelink/OpenFic/commit/84b95fec91a65679d4f7a729515c4012b011af06))
* **agent:** memperbaiki masalah gulir otomatis ke bawah pada pesan streaming yang tidak berfungsi ([#119](https://github.com/syrizelink/OpenFic/issues/119)) ([d79d3ed](https://github.com/syrizelink/OpenFic/commit/d79d3edc1e6e967dd20752645bc52c0e95fe6bb8))
* **agent:** melengkapi tampilan status alat sub-agen ([#118](https://github.com/syrizelink/OpenFic/issues/118)) ([a908536](https://github.com/syrizelink/OpenFic/commit/a9085361cc32b46cc689c51a8d400c03ba0a1592))
* **frontend:** mencegah konten editan penulisan hilang ([#116](https://github.com/syrizelink/OpenFic/issues/116)) ([06698db](https://github.com/syrizelink/OpenFic/commit/06698dbb1a400b3cebadc7f237527dc53aa0e0e5))


### 📚 Dokumentasi

* **readme:** sinkronisasi konten dokumentasi proyek ([#124](https://github.com/syrizelink/OpenFic/issues/124)) ([736779c](https://github.com/syrizelink/OpenFic/commit/736779cebea82f1c69e699d887a6a76c9cda2ef8))


### 🔧 Lain-lain

* **agent:** menyesuaikan definisi agen bawaan ([#115](https://github.com/syrizelink/OpenFic/issues/115)) ([3dcdbb8](https://github.com/syrizelink/OpenFic/commit/3dcdbb82255e79a10059b69f8c3a41d966a8ed5e))
* **agent:** menyesuaikan prompt agen bawaan ([#121](https://github.com/syrizelink/OpenFic/issues/121)) ([211c7b0](https://github.com/syrizelink/OpenFic/commit/211c7b04f687bac675c6700ebe503fb598b4e73a))
* **skill:** menambahkan skill penulisan bawaan ([#113](https://github.com/syrizelink/OpenFic/issues/113)) ([664d126](https://github.com/syrizelink/OpenFic/commit/664d12632b63b8c363bc3ead66a1197a8ff56826))

## [0.7.3](https://github.com/syrizelink/OpenFic/compare/v0.7.2...v0.7.3) (2026-07-19)


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki konfigurasi pengiriman sub-agen ([#111](https://github.com/syrizelink/OpenFic/issues/111)) ([8906741](https://github.com/syrizelink/OpenFic/commit/89067410aee4246a7a912e61bfba46f50aeef946))
* **backend:** memperbaiki anomali pembuatan judul sesi ([#108](https://github.com/syrizelink/OpenFic/issues/108)) ([429ee53](https://github.com/syrizelink/OpenFic/commit/429ee53f10f6f9cd3723b758259c833b4d708316))


### ♻️ Refaktor Kode

* **agent:** refaktor konteks alat Agent dan jalur pemulihan interupsi ([#110](https://github.com/syrizelink/OpenFic/issues/110)) ([5ab5a2b](https://github.com/syrizelink/OpenFic/commit/5ab5a2bc722267ff0e7af7e13e5b1f1c4bc2de78))
* **dashboard:** optimalisasi penyimpanan detail catatan pemanggilan dan pencatatan referensi alat ([#107](https://github.com/syrizelink/OpenFic/issues/107)) ([c25b2c1](https://github.com/syrizelink/OpenFic/commit/c25b2c16673e860e8e0df3d614cec5169f3a2ff7))
* **model:** menyeragamkan konfigurasi parameter lanjutan ([#109](https://github.com/syrizelink/OpenFic/issues/109)) ([f672970](https://github.com/syrizelink/OpenFic/commit/f672970f13567721b2ce6d731419e0ee1214a2e4))


### 🔧 Lain-lain

* **agent:** pelokalan teks tampilan izin alat ([#112](https://github.com/syrizelink/OpenFic/issues/112)) ([362c129](https://github.com/syrizelink/OpenFic/commit/362c12903beee21373e9db124f6fafb5b08dfb41))
* **backend:** menyesuaikan struktur konteks ringkasan ([#106](https://github.com/syrizelink/OpenFic/issues/106)) ([6b2cf6d](https://github.com/syrizelink/OpenFic/commit/6b2cf6d8376e61daee7902a796dcda73342ade28))
* **frontend:** menambahkan entri proyek yang baru dibuka ([#104](https://github.com/syrizelink/OpenFic/issues/104)) ([16d6f4b](https://github.com/syrizelink/OpenFic/commit/16d6f4bb5b45edee3e1876c95e0783aea15a2f91))

## [0.7.2](https://github.com/syrizelink/OpenFic/compare/v0.7.1...v0.7.2) (2026-07-15)


### 🐛 Perbaikan Masalah

* **desktop:** memperbaiki rendering changelog ([#102](https://github.com/syrizelink/OpenFic/issues/102)) ([2b75f25](https://github.com/syrizelink/OpenFic/commit/2b75f25b1d08ecccbc4e9b7bee1e727b21fe24bf))

## [0.7.1](https://github.com/syrizelink/OpenFic/compare/v0.7.0...v0.7.1) (2026-07-14)


### 🐛 Perbaikan Masalah

* **release:** menyeragamkan penamaan artefak lintas platform ([#100](https://github.com/syrizelink/OpenFic/issues/100)) ([56def22](https://github.com/syrizelink/OpenFic/commit/56def22bf42fa660b0b1459929c7f928f1e02c09))

## [0.7.0](https://github.com/syrizelink/OpenFic/compare/v0.6.2...v0.7.0) (2026-07-14)


### ✨ Fitur Baru

* **desktop:** mendukung pembaruan otomatis di dalam aplikasi ([#99](https://github.com/syrizelink/OpenFic/issues/99)) ([bcd6eb9](https://github.com/syrizelink/OpenFic/commit/bcd6eb94fe846c4237b89ffdad87d620ec7706b0))


### 🔧 Lain-lain

* **build:** migrasi build frontend dan aplikasi desktop ke Vite+ ([#97](https://github.com/syrizelink/OpenFic/issues/97)) ([c77fd90](https://github.com/syrizelink/OpenFic/commit/c77fd907ce9a0a55eac24e3fc49094c03c188a25))

## [0.6.2](https://github.com/syrizelink/OpenFic/compare/v0.6.1...v0.6.2) (2026-07-13)


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki pergantian model pada sesi yang tidak berlaku ([#91](https://github.com/syrizelink/OpenFic/issues/91)) ([26ef7f3](https://github.com/syrizelink/OpenFic/commit/26ef7f3beb202eb182b56ed483c144852be6d9c6))
* **agent:** memperbaiki event streaming yang hilang setelah sesi tersambung ulang ([#94](https://github.com/syrizelink/OpenFic/issues/94)) ([018749c](https://github.com/syrizelink/OpenFic/commit/018749caeea11f98d5f8405f17f7868949b3dbba))
* **agent:** mencegah checkpoint sesi membocorkan kunci model ([#92](https://github.com/syrizelink/OpenFic/issues/92)) ([0342427](https://github.com/syrizelink/OpenFic/commit/034242754890db39d2296f3b489c2c2317eb37e7))
* **mobile:** memperbaiki masalah penyesuaian tata letak mobile ([#96](https://github.com/syrizelink/OpenFic/issues/96)) ([f396b34](https://github.com/syrizelink/OpenFic/commit/f396b34066577be9a9a3e5bbef4ace3192b7b1f4))
* **settings:** mengunci konfigurasi agen selama masa berjalan ([#93](https://github.com/syrizelink/OpenFic/issues/93)) ([6afd4b0](https://github.com/syrizelink/OpenFic/commit/6afd4b0e9fa8c106917e8d3ec07f32255c30f7e4))


### ♻️ Refaktor Kode

* **prompt-chains:** refaktor halaman manajemen prompt ([#95](https://github.com/syrizelink/OpenFic/issues/95)) ([73db522](https://github.com/syrizelink/OpenFic/commit/73db52232f506edb9bda8e76156382aef4508310))


### 🔧 Lain-lain

* **agent:** membatasi kemampuan delegasi dan bertanya sub-agen ([#90](https://github.com/syrizelink/OpenFic/issues/90)) ([9999283](https://github.com/syrizelink/OpenFic/commit/999928376012548bfca968aab270f38e7bcd3a83))
* **models:** optimalisasi pemilih model dan penghapusan unggah ikon Provider ([#87](https://github.com/syrizelink/OpenFic/issues/87)) ([436f761](https://github.com/syrizelink/OpenFic/commit/436f761611ee57c67bcf0cdad72284b85a9fafaf))
* **providers:** optimalisasi pemilihan, penyegaran, dan pemanggilan provider bawaan ([#89](https://github.com/syrizelink/OpenFic/issues/89)) ([0fe4188](https://github.com/syrizelink/OpenFic/commit/0fe418852730254789473fdcd96993136f7dabc2))

## [0.6.1](https://github.com/syrizelink/OpenFic/compare/v0.6.0...v0.6.1) (2026-07-11)


### 🐛 Perbaikan Masalah

* **backend:** menghilangkan duplikasi tugas latar belakang judul sesi ([#82](https://github.com/syrizelink/OpenFic/issues/82)) ([afd9650](https://github.com/syrizelink/OpenFic/commit/afd96506fff12d006383bedaae83c8273349a8c6))
* **background:** memperbaiki masalah tugas latar belakang yatim tidak dapat dibersihkan otomatis ([#83](https://github.com/syrizelink/OpenFic/issues/83)) ([643531d](https://github.com/syrizelink/OpenFic/commit/643531d73f86a860832305651bdc03a829ba136b))
* **frontend:** memperbaiki tata letak area edit aturan ([#85](https://github.com/syrizelink/OpenFic/issues/85)) ([025efad](https://github.com/syrizelink/OpenFic/commit/025efad2f6ddf624b7d37242bfd180f8fa1ad4e2))
* **index:** memperbaiki masalah performa akibat pembersihan pembatalan indeks dan polling ([#86](https://github.com/syrizelink/OpenFic/issues/86)) ([73fa08e](https://github.com/syrizelink/OpenFic/commit/73fa08e0f2c7e8049058e085837a45feb5cfeb28))


### ♻️ Refaktor Kode

* **agent:** refaktor jalur aliran XML mention ([#78](https://github.com/syrizelink/OpenFic/issues/78)) ([28e7b16](https://github.com/syrizelink/OpenFic/commit/28e7b16aeb6c9d8288cd2d27210f075883a5d0ac))
* **agent:** refaktor fitur Skill ([#77](https://github.com/syrizelink/OpenFic/issues/77)) ([97e1f5e](https://github.com/syrizelink/OpenFic/commit/97e1f5e20083de7b2f1ca22073bbbd42314abe9c))
* **index:** refaktor panel indeks dan tampilan progres ([#80](https://github.com/syrizelink/OpenFic/issues/80)) ([eff0886](https://github.com/syrizelink/OpenFic/commit/eff0886281ac277ccc49e03ab6cba8c3ec0c2eb3))
* **summary:** refaktor panel pembuatan ringkasan dan pengalaman interaksi ([#84](https://github.com/syrizelink/OpenFic/issues/84)) ([8e16a19](https://github.com/syrizelink/OpenFic/commit/8e16a19204ff9718fcf7a25b38719a80c9c2cf52))


### 📚 Dokumentasi

* memperbarui README ([#79](https://github.com/syrizelink/OpenFic/issues/79)) ([869b98c](https://github.com/syrizelink/OpenFic/commit/869b98c248dd442c96165a47883b2ff011d697df))


### 🔧 Lain-lain

* **frontend:** menyesuaikan bilah atas mobile untuk tokoh dan buku dunia ([#74](https://github.com/syrizelink/OpenFic/issues/74)) ([1824117](https://github.com/syrizelink/OpenFic/commit/1824117893de708fe7c802379021885236e2ea2b))
* **status-bar:** menambahkan tampilan progres indeks ([#81](https://github.com/syrizelink/OpenFic/issues/81)) ([84f94c7](https://github.com/syrizelink/OpenFic/commit/84f94c725854e42d1e3a80cff82c707ebe30b643))

## [0.6.0](https://github.com/syrizelink/OpenFic/compare/v0.5.0...v0.6.0) (2026-07-07)


### ✨ Fitur Baru

* **agent:** menambahkan alat tokoh dan dukungan rollback ([#70](https://github.com/syrizelink/OpenFic/issues/70)) ([4d2bbf0](https://github.com/syrizelink/OpenFic/commit/4d2bbf06bef79b9fd97f2be414c6a5b779c5c865))
* **characters:** menambahkan fitur manajemen tokoh ([#64](https://github.com/syrizelink/OpenFic/issues/64)) ([1d1626a](https://github.com/syrizelink/OpenFic/commit/1d1626a316c5bcd0471f54807ae29a1ee81df918))
* **frontend:** menambahkan status bar global ([#71](https://github.com/syrizelink/OpenFic/issues/71)) ([d584d56](https://github.com/syrizelink/OpenFic/commit/d584d560a6e05747655a4538593da48eaee87fbe))


### ♻️ Refaktor Kode

* **frontend:** mengganti pustaka grafik dasbor menjadi Nivo ([#72](https://github.com/syrizelink/OpenFic/issues/72)) ([3cbd4b7](https://github.com/syrizelink/OpenFic/commit/3cbd4b7389e39bf80d26d7ac8a24a85ae1a39a05))


### 🔧 Lain-lain

* **api:** buku dunia diubah menjadi terikat kuat ke proyek ([#73](https://github.com/syrizelink/OpenFic/issues/73)) ([393add6](https://github.com/syrizelink/OpenFic/commit/393add677c755ddd60bf1019ebd6110b75b462b3))
* **backend:** menambahkan pembungkus perintah backend justfile ([#69](https://github.com/syrizelink/OpenFic/issues/69)) ([d66b128](https://github.com/syrizelink/OpenFic/commit/d66b1282ef7a4934a11827e793b894937f0cfc86))
* **backend:** migrasi pemeriksaan tipe ke ty ([#68](https://github.com/syrizelink/OpenFic/issues/68)) ([d404696](https://github.com/syrizelink/OpenFic/commit/d40469688379706a176958cf6407d747a8c6b85c))
* **frontend:** menambahkan dukungan pemformatan Oxfmt ([#67](https://github.com/syrizelink/OpenFic/issues/67)) ([40e2efd](https://github.com/syrizelink/OpenFic/commit/40e2efd7890749378e76958d85a9da0819789fdf))
* **frontend:** migrasi pemeriksaan frontend ke Oxlint ([#66](https://github.com/syrizelink/OpenFic/issues/66)) ([7c10648](https://github.com/syrizelink/OpenFic/commit/7c10648bcd31ab6f71248e8af5aa4d0f7414ac51))

## [0.5.0](https://github.com/syrizelink/OpenFic/compare/v0.4.9...v0.5.0) (2026-07-04)


### ✨ Fitur Baru

* **agent:** mendukung entri buku dunia dan rollback ([#59](https://github.com/syrizelink/OpenFic/issues/59)) ([b02549d](https://github.com/syrizelink/OpenFic/commit/b02549d8ab8dc050478f98d8e95601c95ade3295))
* **frontend:** menambahkan dukungan PWA untuk mewujudkan aplikasi yang dapat diinstal ([#56](https://github.com/syrizelink/OpenFic/issues/56)) ([bd623fb](https://github.com/syrizelink/OpenFic/commit/bd623fb73c87733a58e3d521cf9f066bcc0ccde7))


### 🐛 Perbaikan Masalah

* **agent:** memperbaiki pemulihan status rollback subagent ([#60](https://github.com/syrizelink/OpenFic/issues/60)) ([b5fa608](https://github.com/syrizelink/OpenFic/commit/b5fa60852a1031f9626e0fff201b719da77cb4c0))
* **frontend:** memperbaiki masalah pesan Agent dipasang ulang setelah selesai ([#61](https://github.com/syrizelink/OpenFic/issues/61)) ([10e2e53](https://github.com/syrizelink/OpenFic/commit/10e2e53811853d2b26c1bcdec5dd1152a02f1223))
* **frontend:** memperbaiki urutan tampilan streaming pesan Agent ([#63](https://github.com/syrizelink/OpenFic/issues/63)) ([9b4ee74](https://github.com/syrizelink/OpenFic/commit/9b4ee74f4e0f0481cba5f5c021ca0b61aa06c0f9))
* **frontend:** menyesuaikan tampilan pesan alat Agent ([#62](https://github.com/syrizelink/OpenFic/issues/62)) ([f6ccfbb](https://github.com/syrizelink/OpenFic/commit/f6ccfbb2d853ac009a13def1b96d5cad1043cffa))


### 🔧 Lain-lain

* menyesuaikan penamaan sesi Agent dan interaksi daftar tugas ([#58](https://github.com/syrizelink/OpenFic/issues/58)) ([741d2e3](https://github.com/syrizelink/OpenFic/commit/741d2e369a37c11d28f3831fd5eb5d777b09ab46))

## [0.4.9](https://github.com/syrizelink/OpenFic/compare/v0.4.8...v0.4.9) (2026-07-02)


### 🐛 Perbaikan Masalah

* **assistant:** menggunakan diff section type yang stabil ([#50](https://github.com/syrizelink/OpenFic/issues/50)) ([27decdc](https://github.com/syrizelink/OpenFic/commit/27decdcdf4bfe1fb6404d73a552fa1cc53958876))
* **frontend:** memperbaiki tampilan ikon model pada sidebar Agent ([#54](https://github.com/syrizelink/OpenFic/issues/54)) ([9eeaaff](https://github.com/syrizelink/OpenFic/commit/9eeaaff74c83a8d492eeb8fd3aa096017a89804c))
* **frontend:** menyelaraskan registrasi pesan alat Agent ([#55](https://github.com/syrizelink/OpenFic/issues/55)) ([b7942f5](https://github.com/syrizelink/OpenFic/commit/b7942f5cab56836dbeb3f837e4e6ad5deff373b3))


### 🔧 Lain-lain

* **frontend:** menyeragamkan perilaku pemuatan panel pengaturan ([#52](https://github.com/syrizelink/OpenFic/issues/52)) ([798e8ad](https://github.com/syrizelink/OpenFic/commit/798e8add8df5d24c93bbf0d1118049f6b4412ea4))
* **frontend:** melengkapi integrasi teks i18n antarmuka frontend ([#51](https://github.com/syrizelink/OpenFic/issues/51)) ([7932bf7](https://github.com/syrizelink/OpenFic/commit/7932bf7e4f3175746677f1be990164ca64e3bc24))
* **frontend:** menyesuaikan status nonaktif model pada panel pengaturan ([#53](https://github.com/syrizelink/OpenFic/issues/53)) ([86449ec](https://github.com/syrizelink/OpenFic/commit/86449ece001aa8dbf210d322d19522ed81d8f620))


### 👷 CI/CD

* **release:** memperbaiki setiap PR yang memicu rilis versi ([#48](https://github.com/syrizelink/OpenFic/issues/48)) ([5668036](https://github.com/syrizelink/OpenFic/commit/5668036edb098c386ec8369867f21e21c9b0bd60))

## [0.4.8](https://github.com/syrizelink/OpenFic/compare/v0.4.7...v0.4.8) (2026-07-01)


### 🔧 Lain-lain

* **frontend:** menyesuaikan penyimpanan otomatis panel pengaturan ([#46](https://github.com/syrizelink/OpenFic/issues/46)) ([a94d0eb](https://github.com/syrizelink/OpenFic/commit/a94d0ebf7683e2b864c5ba3539ede0f38bce66e9))

## [0.4.7](https://github.com/syrizelink/OpenFic/compare/v0.4.6...v0.4.7) (2026-07-01)


### 🐛 Perbaikan Masalah

* **desktop:** memperbaiki startup backend lokal ([#43](https://github.com/syrizelink/OpenFic/issues/43)) ([12440f7](https://github.com/syrizelink/OpenFic/commit/12440f715495a2755c81a7be794426ca2cb7027b))

## [0.4.6](https://github.com/syrizelink/OpenFic/compare/v0.4.5...v0.4.6) (2026-07-01)


### 🐛 Perbaikan Masalah

* **desktop:** memperbaiki instalasi runtime lokal ([#41](https://github.com/syrizelink/OpenFic/issues/41)) ([f77988b](https://github.com/syrizelink/OpenFic/commit/f77988ba27449fb0708bfcce6395027f4e067ea3))

## [0.4.5](https://github.com/syrizelink/OpenFic/compare/v0.4.4...v0.4.5) (2026-07-01)


### 👷 CI/CD

* **package:** optimalisasi penggunaan ulang cache rilis ([#39](https://github.com/syrizelink/OpenFic/issues/39)) ([68f9542](https://github.com/syrizelink/OpenFic/commit/68f954246c1e1f9307313cda7c8e8f6082be2f8b))

## [0.4.4](https://github.com/syrizelink/OpenFic/compare/v0.4.3...v0.4.4) (2026-07-01)


### 🐛 Perbaikan Masalah

* **desktop:** memperbaiki parsing gaya pada build Windows ([#37](https://github.com/syrizelink/OpenFic/issues/37)) ([e837bb1](https://github.com/syrizelink/OpenFic/commit/e837bb14ea17d2a3ef46b0de6d6a72590f3778a9))

## [0.4.3](https://github.com/syrizelink/OpenFic/compare/v0.4.2...v0.4.3) (2026-07-01)


### 👷 CI/CD

* **release:** menunggu PR release dapat digabungkan ([#35](https://github.com/syrizelink/OpenFic/issues/35)) ([6105251](https://github.com/syrizelink/OpenFic/commit/6105251aa84f173ca9eb998dd229e05e5f243ac2))

## [0.4.2](https://github.com/syrizelink/OpenFic/compare/v0.4.1...v0.4.2) (2026-07-01)


### 🐛 Perbaikan Masalah

* **ci:** memperbaiki alur rilis desktop ([#33](https://github.com/syrizelink/OpenFic/issues/33)) ([9f100fc](https://github.com/syrizelink/OpenFic/commit/9f100fc8c4ab75f09f5fd5262cfbe7ca66e62353))

## [0.4.1](https://github.com/syrizelink/OpenFic/compare/v0.4.0...v0.4.1) (2026-07-01)


### 🐛 Perbaikan Masalah

* **ci:** menyesuaikan alur pengemasan rilis ([#31](https://github.com/syrizelink/OpenFic/issues/31)) ([f83451a](https://github.com/syrizelink/OpenFic/commit/f83451a76225daa2c4d1669e93ef9f7f5309f52b))

## [0.4.0](https://github.com/syrizelink/OpenFic/compare/v0.3.3...v0.4.0) (2026-07-01)


### ✨ Fitur Baru

* **desktop:** menambahkan aplikasi desktop ([#29](https://github.com/syrizelink/OpenFic/issues/29)) ([77c7789](https://github.com/syrizelink/OpenFic/commit/77c7789e322b3a7ee029c4837272bf8a7c10df28))

## [0.3.3](https://github.com/syrizelink/OpenFic/compare/v0.3.2...v0.3.3) (2026-06-30)


### 🐛 Perbaikan Masalah

* **backend:** melengkapi build distribusi dan entry point startup backend ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))
* **backend:** melengkapi alur build dan distribusi backend ([#27](https://github.com/syrizelink/OpenFic/issues/27)) ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))
* **backend:** melengkapi alur build dan distribusi backend ([#27](https://github.com/syrizelink/OpenFic/issues/27)) ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))


### ♻️ Refaktor Kode

* **backend:** menyeragamkan keluaran log operasi latar belakang ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))


### 📚 Dokumentasi

* **readme:** memperbarui pengantar proyek dan catatan rilis ([86b3d77](https://github.com/syrizelink/OpenFic/commit/86b3d77baff1a5cc5d57e1617fc6e619eb1090d0))

## [0.3.2](https://github.com/syrizelink/OpenFic/compare/v0.3.1...v0.3.2) (2026-06-29)


### 🐛 Perbaikan Masalah

* **frontend:** melengkapi penyesuaian mobile ([#25](https://github.com/syrizelink/OpenFic/issues/25)) ([a971904](https://github.com/syrizelink/OpenFic/commit/a971904f00466b53203aa87fb146330aad5e710a))

## [0.3.1](https://github.com/syrizelink/OpenFic/compare/v0.3.0...v0.3.1) (2026-06-29)


### 🐛 Perbaikan Masalah

* **ci:** menunggu PR release dapat digabungkan sebelum digabungkan otomatis ([#23](https://github.com/syrizelink/OpenFic/issues/23)) ([d868fc6](https://github.com/syrizelink/OpenFic/commit/d868fc6647d0f5cd8097f3e19c55a4f1c8546233))

## [0.3.0](https://github.com/syrizelink/OpenFic/compare/v0.2.6...v0.3.0) (2026-06-29)


### ✨ Fitur Baru

* **frontend:** melengkapi teks internasionalisasi frontend dan menyelaraskan terjemahan Inggris ([#21](https://github.com/syrizelink/OpenFic/issues/21)) ([59d4249](https://github.com/syrizelink/OpenFic/commit/59d4249bfdfdb2b5867a789a7951e5812de8a011))

## [0.2.6](https://github.com/syrizelink/OpenFic/compare/v0.2.5...v0.2.6) (2026-06-29)


### 🐛 Perbaikan Masalah

* **ci:** sinkronisasi uv.lock dan perbaikan nama paket backend ([#19](https://github.com/syrizelink/OpenFic/issues/19)) ([344bd82](https://github.com/syrizelink/OpenFic/commit/344bd82c5ac43ad85203f8d09ad340e5e4d46e18))

## [0.2.5](https://github.com/syrizelink/OpenFic/compare/v0.2.4...v0.2.5) (2026-06-29)


### 🐛 Perbaikan Masalah

* **ci:** memperbaiki release-please yang tidak memperbarui nomor versi backend dan versi image ([#17](https://github.com/syrizelink/OpenFic/issues/17)) ([de2bbdc](https://github.com/syrizelink/OpenFic/commit/de2bbdc611cfb2615bc5be1987d4a82066dcd6e9))

## [0.2.4](https://github.com/syrizelink/OpenFic/compare/v0.2.3...v0.2.4) (2026-06-29)


### 🐛 Perbaikan Masalah

* **agent:** menghapus dependensi sub-rencana dan beralih memakai kerangka catatan ([#15](https://github.com/syrizelink/OpenFic/issues/15)) ([da97a8b](https://github.com/syrizelink/OpenFic/commit/da97a8be36256a814677a20d540f853713f496f5))

## [0.2.3](https://github.com/syrizelink/OpenFic/compare/v0.2.2...v0.2.3) (2026-06-28)


### 🐛 Perbaikan Masalah

* **build:** memperbaiki konfigurasi electron-builder dan mengaktifkan tampilan penulis changelog ([#13](https://github.com/syrizelink/OpenFic/issues/13)) ([82532ee](https://github.com/syrizelink/OpenFic/commit/82532ee37eb92e6965056b0e56c41c9a37fbbc8b))

## [0.2.2](https://github.com/syrizelink/OpenFic/compare/v0.2.1...v0.2.2) (2026-06-28)


### 🐛 Perbaikan Masalah

* **ci:** memperbaiki error 403 pada push Docker dan sinkronisasi nomor versi yang hilang ([ed002f5](https://github.com/syrizelink/OpenFic/commit/ed002f5e276402f5302675fa4ff6688c2acdc6a4))

## [0.2.1](https://github.com/syrizelink/OpenFic/compare/v0.2.0...v0.2.1) (2026-06-28)


### 🐛 Perbaikan Masalah

* **test:** menghapus pengujian tidak berfungsi yang merujuk jalur termigrasi dan sesekali macet ([eb638df](https://github.com/syrizelink/OpenFic/commit/eb638df74a1754c65351ec924098edabd7c15ebe))

## [0.2.0](https://github.com/syrizelink/OpenFic/compare/v0.1.0...v0.2.0) (2026-06-28)


### ✨ Fitur Baru

* melengkapi dokumen README proyek ([ca919a2](https://github.com/syrizelink/OpenFic/commit/ca919a2f376937da1cd7aa8179a735bf45c8896c))


### 🐛 Perbaikan Masalah

* **ci:** memperbaiki parsing argumen perintah merge PR release ([cf42194](https://github.com/syrizelink/OpenFic/commit/cf421944b77747de1b4c78b8925621d85e74f461))
* **ci:** memperbaiki struktur konfigurasi manifest release-please ([3bf931b](https://github.com/syrizelink/OpenFic/commit/3bf931bdc53f244f01faf8115dca453e3232dd18))
* **ci:** menambahkan checkout sebelum merge PR release ([e1bf61a](https://github.com/syrizelink/OpenFic/commit/e1bf61a01fc477a73076d77b433fd42113bf1c2f))
