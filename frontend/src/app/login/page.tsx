import { Suspense } from "react";
import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-md p-4">
          <div className="h-64 animate-pulse rounded-lg border border-surface-100 bg-white" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
