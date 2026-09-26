#let pbl_logbook(
  week_number: 5,
  period: "22 September – 26 September 2026",
  sprint_name: "Sprint 1: Core Infrastructure",
  checkpoint_target: "Checkpoint 2 (Minggu ke-8)",
  project_title: "VALENIA (Verifikasi Antrian & Layanan Navigasi Interaktif Aplikasi Poliklinik)",
  institution: "POLITEKNIK NEGERI MALANG",
  department: "JURUSAN TEKNOLOGI INFORMASI",
  study_program: "PROGRAM STUDI D-IV TEKNIK INFORMATIKA",
  class_name: "TI-2H",
  academic_year: "2026/2027",
  activities: (),
  evaluations: (),
  supervisor_name: "Titis Wahyudi, S.Kom., M.Kom.",
  supervisor_nip: "-",
  body
) = {
  set document(title: "Logbook PBL Minggu " + str(week_number) + " - VALENIA", author: "Tim PBL VALENIA")
  set page(
    paper: "a4",
    margin: (top: 2cm, bottom: 2cm, left: 2.2cm, right: 2.2cm),
    header: align(right)[
      #text(size: 8pt, fill: rgb("#64748b"))[
        Logbook Mingguan PBL | #project_title | Minggu ke-#week_number
      ]
    ],
    footer: context {
      let page_num = counter(page).get().first()
      let total_pages = counter(page).final().first()
      align(center)[
        #text(size: 9pt, fill: rgb("#64748b"))[
          Halaman #page_num dari #total_pages
        ]
      ]
    }
  )
  
  set text(font: "Arial", size: 11pt, lang: "id")
  set par(justify: true, leading: 0.8em)
  
  align(center)[
    #text(size: 14pt, weight: "bold")[LOGBOOK MINGGUAN PROJECT BASED LEARNING (PBL)] \
    #v(2pt)
    #text(size: 12pt, weight: "bold")[#project_title] \
    #v(2pt)
    #text(size: 10pt)[
      #study_program | #department | #institution \
      Tahun Akademik #academic_year
    ]
  ]
  
  v(8pt)
  line(length: 100%, stroke: 1pt + rgb("#0f172a"))
  v(6pt)
  
  table(
    columns: (auto, 10pt, 1fr, auto, 10pt, 1fr),
    stroke: none,
    inset: 3pt,
    [Minggu Ke], [:], [*Minggu ke-#week_number*],
    [Target CP], [:], [#checkpoint_target],
    [Periode], [:], [#period],
    [Sprint Aktif], [:], [#sprint_name],
    [Kelas], [:], [#class_name],
    [Dosen Pembimbing], [:], [#supervisor_name]
  )
  
  v(10pt)
  text(size: 11pt, weight: "bold")[1. Susunan Tim Pengembang]
  v(4pt)
  
  table(
    columns: (30pt, 1fr, 100pt, 110pt),
    stroke: 0.5pt + rgb("#94a3b8"),
    fill: (col, row) => if row == 0 { rgb("#f1f5f9") } else { none },
    inset: 6pt,
    align: (col, row) => if row == 0 { center + horizon } else { left + horizon },
    
    [*No*], [*Nama Mahasiswa*], [*NIM*], [*Peran Utama*],
    [1], [Raditya Mahatma Ghosi], [254107020102], [Ketua Tim / Lead Developer],
    [2], [Mohammad Hafidz Rafi' Rabbani], [254107020084], [Technical PM / QA],
    [3], [Galuh Pramudya Ananta], [254107020127], [UI/UX Designer / Frontend],
    [4], [Findi Finanda Aszahra], [254107020016], [Sekretaris / Dokumentator]
  )
  
  v(12pt)
  text(size: 11pt, weight: "bold")[2. Rekapitulasi Aktivitas & Luaran Kerja]
  v(4pt)
  
  if activities.len() > 0 {
    table(
      columns: (58pt, 52pt, 1fr, 72pt, 28pt, 60pt),
      stroke: 0.5pt + rgb("#94a3b8"),
      fill: (col, row) => if row == 0 { rgb("#f1f5f9") } else { none },
      inset: 4pt,
      align: (col, row) => (
        if row == 0 { center + horizon }
        else if col == 0 or col == 4 { center + horizon }
        else { left + horizon }
      ),
      
      table.header(
        [*Tanggal*],
        [*Pelaksana*],
        [*Uraian Aktivitas & Luaran*],
        [*Bukti / Link*],
        [*Jam*],
        [*Kendala & Solusi*],
      ),
      
      ..activities.map(act => (
        act.date,
        act.member,
        [
          *#act.task*
          #if "deliverable" in act and act.deliverable != "" and not act.task.ends-with(act.deliverable) [
            \ #text(size: 8.5pt, fill: rgb("#475569"))[#act.deliverable]
          ]
        ],
        if "link" in act and act.link != "" {
          text(size: 8.5pt)[#link(act.link)[#act.at("evidence_label", default: "Link")]]
        } else {
          text(size: 8.5pt)[#act.at("evidence_label", default: "-")]
        },
        str(act.hours),
        text(size: 8.5pt)[
          #if "issue" in act and act.issue != "" and act.issue != "-" [
            *K:* #act.issue \
            *S:* #act.solution
          ] else [
            -
          ]
        ]
      )).flatten()
    )
  } else {
    text(style: "italic", fill: rgb("#64748b"))[Belum ada entri aktivitas pada minggu ini.]
  }
  
  if body != none {
    v(12pt)
    text(size: 11pt, weight: "bold")[3. Catatan Kemajuan & Rencana Lanjutan]
    v(4pt)
    body
  }
  
  v(12pt)
  text(size: 11pt, weight: "bold")[#if body != none [4] else [3]. Catatan & Evaluasi Dosen Fasilitator / Pembimbing]
  v(4pt)
  
  table(
    columns: (1fr),
    stroke: 0.5pt + rgb("#94a3b8"),
    inset: 10pt,
    if evaluations.len() > 0 {
      evaluations.join("\n\n")
    } else {
      text(style: "italic", fill: rgb("#94a3b8"))[Catatan evaluasi mingguan diisi saat sesi asistensi bersama dosen pembimbing.]
    }
  )
  
  v(12pt)
  
  block(breakable: false)[
    #grid(
      columns: (1fr, 1fr),
      align: center,
      [
        Mengetahui, \
        Dosen Pembimbing / Fasilitator
        #v(38pt)
        *#supervisor_name* \
        NIP. #supervisor_nip
      ],
      [
        Malang, #period.split("–").last().trim() \
        Ketua Tim PBL VALENIA
        #v(38pt)
        *Raditya Mahatma Ghosi* \
        NIM. 254107020102
      ]
    )
  ]
}
