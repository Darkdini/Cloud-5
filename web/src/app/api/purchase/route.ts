import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSessionUser } from "@/lib/auth";

export async function POST(req: Request) {
  const session = await getSessionUser();
  if (!session) {
    return NextResponse.json({ error: "Требуется вход" }, { status: 401 });
  }
  const body = await req.json().catch(() => null);
  const productId = body?.productId as string | undefined;
  if (!productId) {
    return NextResponse.json({ error: "Не указан товар" }, { status: 400 });
  }

  const product = await prisma.product.findUnique({ where: { id: productId } });
  if (!product) {
    return NextResponse.json({ error: "Товар не найден" }, { status: 404 });
  }

  // Демо-оформление: фиксируем покупку (реальную оплату подключим позже).
  await prisma.purchase.upsert({
    where: { userId_productId: { userId: session.id, productId } },
    create: { userId: session.id, productId },
    update: {},
  });
  await prisma.product.update({
    where: { id: productId },
    data: { sales: { increment: 1 } },
  });

  return NextResponse.json({ ok: true });
}
