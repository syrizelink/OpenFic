## Berkontribusi Kode untuk OpenFic

### Tentang Bug

Jika Anda menemukan sebuah bug dan berniat menulis patch untuk memperbaikinya, sebelum mulai mengerjakan Anda harus memastikan:
- Versi yang Anda pakai saat mereproduksi bug adalah versi terbaru
- Bug yang bersangkutan belum ditangani di antara perubahan yang sudah di-commit ke branch utama tetapi belum dirilis
- Tidak ada PR berstatus Open atau Draft yang menangani bug tersebut

Setelah patch Anda selesai, Anda harus:
- Membuat sebuah PR
- Memastikan deskripsi PR sesuai [ketentuan](./.github/PULL_REQUEST_TEMPLATE.md), sehingga penyebab masalah dan solusinya dapat dijelaskan dengan jernih
- Menentukan Reviewers lalu menunggu telaah

## Tentang Fitur Baru

Jika Anda berencana menambahkan fitur baru, atau membuat perbaikan atas fitur yang sudah ada, ada beberapa hal yang perlu diperhatikan:
- Perubahan yang menyentuh modul inti Harness (misalnya `backend/app/agent_runtime`) umumnya akan ditolak. Perubahan semacam itu cenderung berdampak luas dan sangat mungkin memunculkan masalah tersembunyi di luar dugaan
- Perubahan yang menyentuh frontend, terutama perubahan UI, harus memastikan beberapa hal berikut. Jika tidak, perubahan biasanya tidak akan diterima. Karena alasan ini, PR jenis ini umumnya punya siklus telaah dan revisi yang lebih panjang dibanding jenis lain
    - Sesuai dengan gaya keseluruhan
    - Memiliki penyesuaian tata letak seluler yang lengkap
    - Sudah mempertimbangkan rancangan UX secara memadai (termasuk seluler)
    - Tidak berdampak pada tata letak lain
- Perlu diketahui, PR perubahan fitur baru yang Anda ajukan bisa saja langsung ditolak alih-alih diminta diperbaiki. Ini biasanya karena perubahannya tidak sesuai harapan. Kami menghargai gagasan setiap orang, tetapi memilih fitur yang sesuai gagasan dasar proyek secara saksama itu sangat penting. Tentu saja, Anda juga boleh melakukan Fork atas repositori ini dan mengubahnya secara bebas. Jika Anda tidak yakin apakah fitur baru itu sesuai, Anda juga boleh membuat sebuah Discussion untuk berdiskusi dengan kami.

## Perhatikan

Jika perubahan yang Anda kirimkan hanya menyesuaikan format kode, menangani hal yang tidak berdampak pada bisnis dan UX yang sebenarnya, atau melakukan perbaikan fitur yang bersifat permukaan, maka perubahan yang tidak membawa peningkatan nyata bagi kestabilan dan fungsionalitas sistem itu tidak bermakna. Dalam keadaan seperti itu, PR Anda akan ditutup.


Iterasi dan pembaruan OpenFic tidak terlepas dari dukungan komunitas. Terima kasih kepada semua kontributor yang telah mengajukan Issue dan PR ♥️♥️♥️
