// Run with: npm test   (node --test, Node's built-in TypeScript support)
import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULT_REDIRECT, safeNext } from "./safe-redirect.ts";

test("keeps legitimate internal destinations", () => {
  const ok: Array<[string, string]> = [
    ["/dashboard/", "/dashboard/"],
    ["/products/list/", "/products/list/"],
    ["/products/3f2b/edit/", "/products/3f2b/edit/"],
    ["/sales/?status=DRAFT&page=2", "/sales/?status=DRAFT&page=2"],
    ["/trade/exports/#documents", "/trade/exports/#documents"],
    ["/reports/?q=a%2Fb", "/reports/?q=a%2Fb"], // encoded slash in the QUERY is fine
    ["/inventory/../dashboard/", "/dashboard/"], // normalised, still internal
  ];
  for (const [input, expected] of ok) assert.equal(safeNext(input), expected, input);
});

test("rejects external, protocol-relative and scheme URLs", () => {
  const bad = [
    "https://evil.com",
    "http://evil.com/dashboard/",
    "//evil.com",
    "//evil.com/dashboard/",
    "///evil.com",
    "http:/evil.com",
    "https:evil.com",
    "javascript:alert(1)",
    "JaVaScRiPt:alert(document.cookie)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "evil.com",
    "dashboard/",
    "mailto:a@evil.com",
  ];
  for (const input of bad) assert.equal(safeNext(input), DEFAULT_REDIRECT, input);
});

test("rejects backslash and whitespace tricks that browsers normalise into //host", () => {
  const bad = [
    "/\\evil.com",
    "\\\\evil.com",
    "/\\/evil.com",
    "\\/evil.com",
    "/\t/evil.com",
    "/\n/evil.com",
    "/\r/evil.com",
    " /dashboard/",
    "/dashboard/ ",
    "/\u0000/evil.com",
    "/\u2028/evil.com",
    "/\u00A0/evil.com",
    "/\u200B/evil.com",
  ];
  for (const input of bad) assert.equal(safeNext(input), DEFAULT_REDIRECT, JSON.stringify(input));
});

test("rejects encoded and nested-encoded separators in the path", () => {
  const bad = [
    "/%2F%2Fevil.com",
    "/%2f%2fevil.com",
    "/%5Cevil.com",
    "/%5c%5cevil.com",
    "/%252F%252Fevil.com", // decodes to /%2F%2F..., then to //...
    "/%25252F%25252Fevil.com",
    "%2F%2Fevil.com",
  ];
  for (const input of bad) assert.equal(safeNext(input), DEFAULT_REDIRECT, input);
});

test("rejects malformed, empty and oversized values", () => {
  for (const input of [null, undefined, "", "/" + "a".repeat(5000)]) {
    assert.equal(safeNext(input as string | null | undefined), DEFAULT_REDIRECT, String(input).slice(0, 20));
  }
});

test("does not send users back into the auth pages (redirect loops)", () => {
  for (const input of ["/login/", "/login/?next=//evil.com", "/signup/", "/signup/verify/"]) {
    assert.equal(safeNext(input), DEFAULT_REDIRECT, input);
  }
});

test("uses the caller's fallback", () => {
  assert.equal(safeNext("//evil.com", "/products/list/"), "/products/list/");
});
