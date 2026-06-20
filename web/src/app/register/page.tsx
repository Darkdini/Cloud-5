import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { getSessionUser } from "@/lib/auth";

export default async function RegisterPage() {
  if (await getSessionUser()) redirect("/dashboard");
  return (
    <div className="container-x flex min-h-[70vh] items-center justify-center py-12">
      <AuthForm mode="register" />
    </div>
  );
}
