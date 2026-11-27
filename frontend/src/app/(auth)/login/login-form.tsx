"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorAlert, Field, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { ACCOUNT_STATUS_MESSAGES, accountBlockCode, safeNext, useLogin, useMe } from "@/lib/auth";

/** Shown instead of a generic error when the password was right but the account can't be used yet. */
function AccountStatusNotice({ code }: { code: string }) {
  const info = ACCOUNT_STATUS_MESSAGES[code];
  if (!info) return null;
  const tones: Record<string, string> = { account_pending: "alert-info", account_suspended: "alert-warning" };
  const tone = tones[code] ?? "alert-danger";
  return (
    <div className={`alert ${tone} mt-6`} role="status" data-account-status={code}>
      <p className="font-medium">{info.title}</p>
      <p className="mt-1">{info.body}</p>
    </div>
  );
}

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

  // Status from a failed sign-in, or passed by the app shell when a session was ended.
  const statusParam = params.get("status");
  const blockCode = accountBlockCode(login.error) ?? (statusParam && statusParam in ACCOUNT_STATUS_MESSAGES ? statusParam : null);
  const fieldErrors = login.error instanceof ApiError ? login.error.fieldErrors : {};

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-1.5 text-sm text-slate-500">Welcome back. Enter your details to continue.</p>
      {params.get("registered") && !blockCode && (
        <div className="alert alert-info mt-6" role="status">
          <p className="font-medium">Account created</p>
          <p className="mt-1">An administrator must approve your account before you can use MiniERP. You can sign in to check its status.</p>
        </div>
      )}
      {blockCode && <AccountStatusNotice code={blockCode} />}
      <form
        className="mt-8 space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate({ email, password }, { onSuccess: () => window.location.assign(next) });
        }}
      >
        {login.error && !accountBlockCode(login.error) && !Object.keys(fieldErrors).length && <ErrorAlert error={login.error} />}
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
        New here? <Link href="/signup/" className="link">Request an account</Link>
      </p>
    </>
  );
}
