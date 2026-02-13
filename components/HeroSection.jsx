export default function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-slate-950 px-4 py-8 sm:px-6 sm:py-10 md:py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-red-500/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-orange-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex w-full max-w-6xl flex-col items-center text-center [font-family:'Pretendard','Noto_Sans_KR',-apple-system,'Segoe_UI','Apple_SD_Gothic_Neo','Malgun_Gothic',sans-serif]">
        <h1 className="max-w-4xl text-4xl font-extrabold leading-tight tracking-tight text-transparent bg-gradient-to-b from-white via-zinc-100 to-zinc-400 bg-clip-text sm:text-5xl md:text-6xl">
          <span className="block">데이터가 검증한</span>
          <span className="mt-1 block">
            오늘의 Top Pick <span className="align-middle">💎</span>
          </span>
        </h1>

        <p className="mt-4 max-w-3xl text-lg font-medium leading-relaxed text-gray-400 sm:text-xl">
          <span className="block">복잡한 차트 속에서 AI가 찾아낸</span>
          <span className="mt-1 block">
            가장 강력한 상승 신호입니다. <span className="align-middle">📈</span>
          </span>
        </p>

      </div>
    </section>
  );
}
