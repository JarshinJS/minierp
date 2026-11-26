"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorAlert, Field, Spinner } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api/client";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", full_name: "", password: "", confirm_password: "" });
  const signup = useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/signup/", { body: form })),
    onSuccess: (data) => router.push(`/signup/verify/?email=${encodeURIComponent(data.email)}`),
  });
  const errors = signup.error instanceof ApiError ? signup.error.fieldErrors : {};
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value });

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1.5 text-sm text-slate-500">We&apos;ll email you a code to verify your address. An admin assigns your role.</p>
      <form className="mt-8 space-y-5" onSubmit={(e) => { e.preventDefault(); signup.mutate(); }}>
        {signup.error && (errors.non_field_errors || !Object.keys(errors).length) && (
          <ErrorAlert error={errors.non_field_errors?.[0] ?? signup.error} />
        )}
        <Field label="Full name" error={errors.full_name} required>
          {(id) => <input id={id} type="text" autoComplete="name" required value={form.full_name} onChange={set("full_name")} />}
        </Field>
        <Field label="Email" error={errors.email} required>
          {(id) => <input id={id} type="email" autoComplete="email" required value={form.email} onChange={set("email")} />}
        </Field>
        <Field label="Password" error={errors.password} required help="At least 8 characters; not too common.">
          {(id) => <input id={id} type="password" autoComplete="new-password" required value={form.password} onChange={set("password")} />}
        </Field>
        <Field label="Confirm password" error={errors.confirm_password} required>
          {(id) => <input id={id} type="password" autoComplete="new-password" required value={form.confirm_password} onChange={set("confirm_password")} />}
        </Field>
        <button type="submit" className="btn btn-primary w-full" disabled={signup.isPending}>
          {signup.isPending && <Spinner />} Continue
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account? <Link href="/login/" className="link">Sign in</Link>
      </p>
    </>
  );
}
