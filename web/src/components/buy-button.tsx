"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Check, Star } from "lucide-react";

export function BuyButton({
  productId,
  priceStars,
  authed,
  owned,
}: {
  productId: string;
  priceStars: number;
  authed: boolean;
  owned?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "loading" | "done">(
    owned ? "done" : "idle",
  );
  const [error, setError] = useState("");

  async function buy() {
    if (!authed) {
      router.push("/login?next=back");
      return;
    }
    setState("loading");
    setError("");
    const res = await fetch("/api/purchase", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productId }),
    });
    if (res.ok) {
      setState("done");
      router.refresh();
    } else {
      const d = await res.json().catch(() => ({}));
      setError(d.error ?? "Ошибка");
      setState("idle");
    }
  }

  if (state === "done") {
    return (
      <button className="btn-ghost w-full cursor-default" disabled>
        <Check className="h-4 w-4 text-neon-lime" /> В библиотеке
      </button>
    );
  }

  return (
    <div className="w-full">
      <button onClick={buy} disabled={state === "loading"} className="btn-primary w-full">
        {state === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <>
            Купить за {priceStars} <Star className="h-4 w-4 fill-current" />
          </>
        )}
      </button>
      {error && <p className="mt-2 text-center text-xs text-neon-pink">{error}</p>}
    </div>
  );
}
