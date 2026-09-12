# Ketentuan Informasi Commit (Conventional Commits 1.0.0)

Proyek ini mengikuti ketentuan [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

## Struktur Informasi Commit

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

- `type` beserta `:` dan spasi setelahnya wajib ada; `scope`, `!`, `body`, `footer` semuanya opsional
- Selain `BREAKING CHANGE` yang wajib huruf kapital, setiap elemen tidak sensitif terhadap huruf besar-kecil

## type

- Wajib dimulai dengan prefiks type, yang terbentuk dari kata benda.
- Tipe yang didefinisikan oleh ketentuan (wajib digunakan sesuai makna berikut):

  | type | Makna |
  | --- | --- |
  | `feat` | Memperkenalkan fitur baru yang utuh |
  | `fix` | Memperbaiki bug |
  | `build` | Perubahan yang memengaruhi sistem build atau dependensi eksternal |
  | `chore` | Perubahan lain-lain, semua perubahan yang tidak termasuk tipe lainnya harus dimasukkan ke kategori ini |
  | `ci` | Perubahan pada file konfigurasi dan skrip CI |
  | `docs` | Perubahan dokumentasi |
  | `style` | Perubahan format atau gaya yang tidak memengaruhi makna kode |
  | `refactor` | Refaktor yang tidak memperbaiki bug maupun menambahkan fitur |
  | `perf` | Perubahan kode yang meningkatkan performa |
  | `test` | Menambahkan atau memperbaiki pengujian |

<!-- Penjelasan mengenai tipe feat, tipe ini tidak boleh digunakan pada kondisi berikut -->
<!-- Jika perubahan tidak mencakup satu fitur yang utuh dan mandiri -->
<!-- Jika perubahan melekat pada suatu fitur yang sudah ada, dan hanya berupa fitur atau perbaikan UX sederhana -->

## scope

- Opsional, diletakkan setelah type dan sebelum `:`, dibungkus tanda kurung
- Wajib berupa kata benda yang mendeskripsikan suatu bagian dari basis kode, misalnya `fix(parser):`

## description

- Wajib, langsung setelah titik dua dan spasi
- Merupakan ringkasan singkat dari perubahan kode
- Untuk tipe perbaikan bug, format yang harus diikuti: `<aksi><masalah><hasil>`, misalnya "memperbaiki masalah xx yang disebabkan oleh xxx", untuk

## body

- Opsional, dimulai setelah satu baris kosong sesudah description
- Format bebas, dapat memuat berapa pun jumlah paragraf (dipisahkan baris kosong)

## footer

- Opsional, dimulai setelah satu baris kosong sesudah body.
- Setiap footer tersusun dari satu token + pemisah + nilai:
  - Pemisahnya adalah `:<space>` atau `<space>#`
  - Spasi di dalam token digantikan dengan `-`, misalnya `Acked-by` (untuk membedakan footer dengan body yang terdiri dari beberapa paragraf)
- `BREAKING CHANGE` adalah pengecualian, dapat dipakai apa adanya sebagai token (tetap huruf kapital); `BREAKING-CHANGE` bersinonim dengan `BREAKING CHANGE`
