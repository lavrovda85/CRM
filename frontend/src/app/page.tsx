import { redirect } from "next/navigation";

/**
 * Main landing page.
 *
 * Previously this route contained placeholder hardcoded numbers.
 * Now we redirect to the real dashboard that pulls data from the API.
 */
export default function DashboardPage() {
  redirect("/dashboard");
}
