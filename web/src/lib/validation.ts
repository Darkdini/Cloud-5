import { z } from "zod";

export const registerSchema = z.object({
  name: z.string().min(2, "Имя слишком короткое").max(60),
  email: z.string().email("Некорректный email"),
  password: z.string().min(6, "Минимум 6 символов").max(100),
});

export const loginSchema = z.object({
  email: z.string().email("Некорректный email"),
  password: z.string().min(1, "Введите пароль"),
});

export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
