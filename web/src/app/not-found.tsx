import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container-x flex min-h-[60vh] flex-col items-center justify-center text-center">
      <h1 className="font-display text-7xl font-extrabold text-gradient">404</h1>
      <p className="mt-3 text-white/60">Такой страницы нет</p>
      <Link href="/" className="btn-primary mt-6">
        На главную
      </Link>
    </div>
  );
}
