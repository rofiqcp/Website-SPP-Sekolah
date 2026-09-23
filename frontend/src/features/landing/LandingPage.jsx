<style>{`
  @keyframes float1 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(30px, -40px) scale(1.05); }
    66% { transform: translate(-20px, 20px) scale(0.95); }
  }
  @keyframes float2 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(-40px, 30px) scale(0.95); }
    66% { transform: translate(20px, -30px) scale(1.05); }
  }
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .animate-on-scroll {
    opacity: 0;
    transform: translateY(30px);
    transition: opacity 0.8s ease-out, transform 0.8s ease-out;
  }
  .animate-on-scroll.visible {
    opacity: 1;
    transform: translateY(0);
  }
`}</style>

import { useEffect, useRef, useState } from 'react';

const features = [
  {
    icon: '📋',
    title: 'Tagihan SPP',
    desc: 'Kelola tagihan dan pembayaran SPP secara digital. Cetak invoice, lacak status, kirim notifikasi otomatis ke wali murid.',
  },
  {
    icon: '💳',
    title: 'Dompet Digital',
    desc: 'Setiap siswa punya dompet digital untuk transaksi sekolah. Top-up mudah, histori transaksi real-time, kontrol orang tua.',
  },
  {
    icon: '📡',
    title: 'E-Kantin RFID',
    desc: 'Kantin cashless dengan kartu RFID. Bayar cepat tanpa uang tunai, pantau jajan siswa, laporan penjualan harian.',
  },
  {
    icon: '🏦',
    title: 'Tabungan',
    desc: 'Fasilitas tabungan siswa dan pegawai. Setor-tarik tercatat rapi, bunga otomatis, laporan mutasi kapan saja.',
  },
  {
    icon: '📊',
    title: 'Laporan Keuangan',
    desc: 'Laporan keuangan lengkap: arus kas, laba rugi, neraca. Jurnal akuntansi otomatis dari setiap transaksi.',
  },
  {
    icon: '📦',
    title: 'Inventaris & Aset',
    desc: 'Catat semua aset dan inventaris yayasan. Lacak lokasi, kondisi, penyusutan. QR code untuk audit cepat.',
  },
];

const stats = [
  { value: '1.000+', label: 'Siswa' },
  { value: '50+', label: 'Guru & Staff' },
  { value: '15+', label: 'Tahun Pengalaman' },
  { value: '99%', label: 'Kepuasan Orang Tua' },
];

const testimonials = [
  {
    name: 'Bapak Ahmad Wijaya',
    role: 'Ketua Yayasan',
    text: 'Sistem ini benar-benar memudahkan pengelolaan keuangan yayasan. Semua transaksi tercatat rapi dan laporannya instan.',
  },
  {
    name: 'Ibu Siti Aminah',
    role: 'Orang Tua Siswa',
    text: 'Saya bisa memantau pengeluaran anak di kantin dan tagihan SPP secara real-time. Rasanya tenang knowing semua tercatat.',
  },
  {
    name: 'Pak Budi Santoso',
    role: 'Bendahara Sekolah',
    text: 'Dulu butuh minggu untuk tutup buku, sekarang cuma hitungan jam. Laporannya akurat dan mudah dipahami.',
  },
];

export default function LandingPage({ onNavigate }) {
  const goLogin = () => {
    if (onNavigate) onNavigate('/login');
    else window.location.href = '/login';
  };

  const observerRef = useRef(null);
  const [counts, setCounts] = useState(stats.map(() => 0));
  const statsRef = useRef(null);

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
          }
        });
      },
      { threshold: 0.15, rootMargin: '0px 0px -50px 0px' }
    );

    const elements = document.querySelectorAll('.animate-on-scroll');
    elements.forEach((el) => observerRef.current?.observe(el));

    return () => {
      observerRef.current?.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!statsRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCounters();
            observer.disconnect();
          }
        });
      },
      { threshold: 0.5 }
    );
    observer.observe(statsRef.current);
    return () => observer.disconnect();
  }, []);

  const animateCounters = () => {
    stats.forEach((stat, idx) => {
      const target = parseInt(stat.value.replace(/[^0-9]/g, ''));
      if (isNaN(target)) return;
      const duration = 2000;
      const start = performance.now();
      const from = 0;
      const step = (now) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(from + (target - from) * eased);
        setCounts((c) => {
          const next = [...c];
          next[idx] = current;
          return next;
        });
        if (progress < 1) requestAnimationFrame(step);
        else setCounts((c) => { const n = [...c]; n[idx] = target; return n; });
      };
      requestAnimationFrame(step);
    });
  };

  const displayStat = (stat, idx) => {
    const suffix = stat.value.replace(/[0-9]/g, '');
    return `${counts[idx]}${suffix}`;
  };

  return (
    <div className="font-sans antialiased text-slate-800 bg-white overflow-x-hidden">
      {/* Hero */}
      <section className="relative min-h-screen flex items-center justify-center px-6 py-24 overflow-hidden bg-gradient-to-br from-teal-600 via-teal-700 to-slate-900 text-white">
        <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
          <div
            className="absolute -top-40 -left-40 w-96 h-96 bg-teal-400/20 rounded-full blur-3xl"
            style={{ animation: 'float1 12s ease-in-out infinite' }}
          />
          <div
            className="absolute top-1/4 right-0 w-[500px] h-[500px] bg-cyan-300/10 rounded-full blur-3xl"
            style={{ animation: 'float2 15s ease-in-out infinite' }}
          />
          <div
            className="absolute -bottom-32 left-1/3 w-80 h-80 bg-teal-500/20 rounded-full blur-3xl"
            style={{ animation: 'float1 18s ease-in-out infinite reverse' }}
          />
        </div>

        <div className="relative z-10 max-w-3xl mx-auto text-center">
          <img
            src="/logo%20yaomy.jpg"
            alt="El Yaomy"
            className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl mx-auto mb-8 object-cover shadow-2xl ring-4 ring-white/10 bg-white/5"
          />
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight mb-6">
            Yayasan Pendidikan <span className="text-teal-200">El Yaomy</span> Klaten
          </h1>
          <p className="text-lg sm:text-xl text-white/80 max-w-2xl mx-auto mb-10 leading-relaxed">
            Sistem manajemen keuangan dan operasional terpadu — SPP, dompet digital, kantin RFID, tabungan, inventaris, dan laporan keuangan dalam satu platform.
          </p>
          <button
            onClick={goLogin}
            className="inline-flex items-center justify-center px-8 py-4 text-lg font-semibold bg-white text-teal-800 rounded-2xl shadow-lg shadow-black/20 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-black/30 focus:outline-none focus:ring-4 focus:ring-white/30"
          >
            Masuk ke Sistem
          </button>
          <p className="mt-8 text-sm text-white/50 animate-bounce">↓ Gulir ke bawah</p>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 sm:py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14 animate-on-scroll">
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">Fitur Utama</h2>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto">
              Semua yang dibutuhkan untuk mengelola keuangan dan operasional yayasan dalam satu aplikasi.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
            {features.map((f, i) => (
              <div
                key={i}
                className="animate-on-scroll group bg-white rounded-3xl p-7 border border-slate-100 shadow-sm transition-all duration-300 hover:shadow-xl hover:-translate-y-1 hover:border-teal-50"
                style={{ transitionDelay: `${i * 80}ms` }}
              >
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl bg-gradient-to-br from-teal-400 to-teal-600 text-white shadow-lg shadow-teal-500/20 mb-5 group-hover:scale-110 transition-transform duration-300">
                  {f.icon}
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">{f.title}</h3>
                <p className="text-slate-500 leading-relaxed text-sm">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section ref={statsRef} className="py-16 sm:py-24 px-6 bg-slate-50">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 sm:gap-12">
          {stats.map((stat, i) => (
            <div key={i} className="text-center animate-on-scroll" style={{ transitionDelay: `${i * 100}ms` }}>
              <div className="text-4xl sm:text-5xl font-extrabold text-teal-700 tracking-tight mb-2">
                {displayStat(stat, i)}
              </div>
              <div className="text-sm sm:text-base font-medium text-slate-500">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-20 sm:py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14 animate-on-scroll">
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">Dipercaya oleh Yayasan Kami</h2>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto">
              Suara dari mereka yang telah merasakan manfaat sistem kami sehari-hari.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
            {testimonials.map((t, i) => (
              <div
                key={i}
                className="animate-on-scroll bg-white rounded-3xl p-8 border border-slate-100 shadow-sm transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 flex items-center justify-center text-white font-bold text-lg">
                    {t.name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-semibold text-slate-900 text-sm">{t.name}</div>
                    <div className="text-xs text-slate-400">{t.role}</div>
                  </div>
                </div>
                <p className="text-slate-600 leading-relaxed text-sm">"{t.text}"</p>
                <div className="mt-4 flex gap-1 text-teal-500 text-sm">
                  ★★★★★
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 sm:py-28 px-6 bg-gradient-to-br from-teal-700 via-teal-800 to-slate-900 text-white text-center">
        <div className="max-w-3xl mx-auto animate-on-scroll">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">Siap Mengelola Keuangan Yayasan?</h2>
          <p className="text-lg text-white/70 mb-10 max-w-xl mx-auto">
            Masuk sekarang dan nikmati kemudahan sistem terintegrasi untuk operasional sekolah yang lebih efisien.
          </p>
          <button
            onClick={goLogin}
            className="inline-flex items-center justify-center px-10 py-4 text-lg font-semibold bg-white text-teal-800 rounded-2xl shadow-lg shadow-black/20 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-black/30 focus:outline-none focus:ring-4 focus:ring-white/30"
          >
            Masuk Sekarang
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-16 px-6">
        <div className="max-w-6xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10">
          <div className="sm:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-3 mb-4">
              <img src="/logo%20yaomy.jpg" alt="El Yaomy" className="w-10 h-10 rounded-xl object-cover ring-2 ring-white/10" />
              <span className="font-bold text-white text-lg">El Yaomy</span>
            </div>
            <p className="text-sm leading-relaxed">Yayasan Pendidikan El Yaomy Klaten</p>
            <p className="text-xs text-slate-500 mt-1">NPSN: 20331580</p>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Tautan</h4>
            <ul className="space-y-2 text-sm">
              <li><button onClick={goLogin} className="hover:text-teal-400 transition-colors">Masuk Sistem</button></li>
              <li><a href="#" className="hover:text-teal-400 transition-colors">Tentang Kami</a></li>
              <li><a href="#" className="hover:text-teal-400 transition-colors">Fitur</a></li>
              <li><a href="#" className="hover:text-teal-400 transition-colors">Kontak</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Kontak</h4>
            <ul className="space-y-2 text-sm">
              <li>Batur Baru, Tegalrejo, Ceper, Klaten, Jawa Tengah 57465</li>
              <li>0272-555578</li>
              <li>sdim.elyaomy@gmail.com</li>
            </ul>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-4">Jam Operasional</h4>
            <p className="text-sm">Senin - Jumat</p>
            <p className="text-sm">07:00 - 14:00</p>
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-12 pt-8 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>© {new Date().getFullYear()} Yayasan Pendidikan El Yaomy Klaten. All rights reserved.</p>
          <p>Yayasan Pendidikan El Yaomy Klaten, NPSN: 20331580</p>
        </div>
      </footer>
    </div>
  );
}
