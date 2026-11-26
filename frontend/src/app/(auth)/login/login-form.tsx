"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorAlert, Field, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { safeNext, useLogin, useMe } from "@/lib/auth";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const { data: me } = useMe();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Already signed in → go straight through.
  useEffect(() => {
    if (me) router.replace(next);
  }, [me, next, router]);

  const fieldErrors = login.error instanceof ApiError ? login.error.fieldErrors : {};

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-1.5 text-sm text-slate-500">Welcome back. Enter your details to continue.</p>
      {params.get("registered") && (
        <div className="alert alert-success mt-6">Account created. You can sign in now.</div>
      )}
      <form
        className="mt-8 space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate({ email, password }, { onSuccess: () => window.location.assign(next) });
        }}
      >
        {login.error && !Object.keys(fieldErrors).length && <ErrorAlert error={login.error} />}
        <Field label="Email" error={fieldErrors.email}>
          {(id) => <input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />}
        </Field>
        <Field label="Password" error={fieldErrors.password}>
          {(id) => <input id={id} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <button type="submit" className="btn btn-primary w-full" disabled={login.isPending}>
          {login.isPending && <Spinner />} Sign in
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        New here? <Link href="/signup/" className="link">Create an account</Link>
      </p>
    </>
  );
}
