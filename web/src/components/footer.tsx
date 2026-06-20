import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/10 py-10">
      <div className="container-x flex flex-col items-center justify-between gap-4 text-sm text-white/50 sm:flex-row">
        <p>
          © {new Date().getFullYear()} Cloud-5 · Маркетплейс цифровых товаров
        </p>
        <div className="flex gap-5">
          <Link href="/catalog" className="hover:text-white">
            Каталог
          </Link>
          <Link href="/register" className="hover:text-white">
            Стать автором
          </Link>
        </div>
      </div>
    </footer>
  );
}
