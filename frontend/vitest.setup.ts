import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

// next/link → plain <a>. Dynamic React import inside the factory dodges
// the ESM hoisting issue (vi.mock factories run before top-level imports).
vi.mock("next/link", async () => {
  const React = await import("react");
  type LinkProps = React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children?: React.ReactNode;
  };
  return {
    __esModule: true,
    default: ({ children, href, ...rest }: LinkProps) =>
      React.createElement("a", { href, ...rest }, children),
  };
});
