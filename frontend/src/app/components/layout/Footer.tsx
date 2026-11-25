import { CheckCircle2 } from 'lucide-react';

/** Chân trang Semantic <footer> kèm bảng kiểm tra tự động các tiêu chí Technical SEO. */
export function Footer() {
  const seoChecks = [
    'Thẻ <title> & Meta Description chuẩn độ dài',
    'Cấu trúc Heading phân cấp chuẩn H1 → H2 → H3',
    'Semantic HTML5 (<header>, <nav>, <main>, <article>, <aside>, <footer>)',
    'Dữ liệu có cấu trúc JSON-LD (Schema.org SoftwareApplication)',
    'OpenGraph, Canonical URL, robots.txt & sitemap.xml',
    'Ảnh Lazy-loading kèm thuộc tính alt mô tả & rel="noopener noreferrer"',
  ];

  return (
    <footer className="mt-14 border-t border-slate-800/80 bg-slate-900/50 py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div>
            <h2 className="text-sm font-bold text-white">DETOLA — AI KOC Discovery Engine</h2>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              Hệ thống nghiên cứu số lượng lớn KOC TikTok với phễu lọc 5 tầng tối ưu chi phí AI, phân tích khung hình
              Contact Sheet 3x3 và khôi phục tiến độ SQLite WAL khi gián đoạn.
            </p>
          </div>

          <div className="md:col-span-2">
            <h2 className="text-xs font-bold tracking-wider text-emerald-400 uppercase">
              Tiêu chuẩn Technical On-Page SEO & An ninh đã kích hoạt
            </h2>
            <ul className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {seoChecks.map((item) => (
                <li key={item} className="flex items-center gap-2 text-xs text-slate-300">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}
