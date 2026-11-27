import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { expect } from "@playwright/test";

/** Django's file-based e-mail backend writes here under config.settings.e2e. */
const MAIL_DIR = path.resolve(__dirname, "../../../backend/.e2e/mail");

function messagesTo(email: string): string[] {
  let files: string[] = [];
  try {
    files = readdirSync(MAIL_DIR).map((f) => path.join(MAIL_DIR, f));
  } catch {
    return [];
  }
  return files
    .sort((a, b) => statSync(a).mtimeMs - statSync(b).mtimeMs)
    .map((f) => readFileSync(f, "utf8"))
    .flatMap((content) => content.split(/^-{70,}$/m))
    .filter((msg) => new RegExp(`^To: ${email.replace(/[.+]/g, "\\$&")}$`, "m").test(msg));
}

/** The most recent 6-digit signup code e-mailed to `email`. */
export async function latestOtp(email: string): Promise<string> {
  let code = "";
  await expect.poll(() => {
    const last = messagesTo(email).at(-1) ?? "";
    code = last.match(/verification code is (\d{6})/)?.[1] ?? "";
    return code;
  }, { message: `no verification e-mail for ${email}`, timeout: 10_000 }).toMatch(/^\d{6}$/);
  return code;
}
