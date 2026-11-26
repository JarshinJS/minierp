"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorAlert, Field, Spinner } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api/client";

/** A failed step may mean the pending signup was discarded and must start over. */
function needsRestart(error: unknown) {
  return error instanceof ApiError && !!(error.body as { restart?: boolean } | null)?.restart;
}

export function VerifyForm() {
  const router = useRouter();
  const email = useSearchParams().get("email") ?? "your email";
  const [otp, setOtp] = useState("");

  const verify = useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/signup/verify/", { body: { otp } })),
    onSuccess: () => router.push("/login/?registered=1"),
  });
  const resend = useMutation({ mutationFn: () => unwrap(api.POST("/api/auth/signup/resend/")) });
  const error = verify.error ?? resend.error;

  if (needsRestart(error)) {
    return (
      <>
        <h1 className="text-2xl font-semibold tracking-tight">Start again</h1>
        <ErrorAlert error={error} className="mt-6" />
        <Link href="/signup/" className="btn btn-primary mt-6 w-full">Back to sign up</Link>
      </>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Check your email</h1>
      <p className="mt-1.5 text-sm text-slate-500">We sent a 6-digit code to <strong className="text-slate-700">{email}</strong>. It expires in 5 minutes.</p>
      {resend.isSuccess && <div className="alert alert-success mt-6">A new code is on its way.</div>}
      <form className="mt-8 space-y-5" onSubmit={(e) => { e.preventDefault(); verify.mutate(); }}>
        {error && <ErrorAlert error={error} />}
        <Field label="Verification code">
          {(id) => (
            <input id={id} type="text" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required
              value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
              className="text-center font-mono text-lg tracking-[0.5em]" />
          )}
        </Field>
        <button type="submit" className="btn btn-primary w-full" disabled={verify.isPending || otp.length !== 6}>
          {verify.isPending && <Spinner />} Verify and create account
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Didn&apos;t get it?{" "}
        <button className="link" onClick={() => resend.mutate()} disabled={resend.isPending}>Send a new code</button>
      </p>
    </>
  );
}
