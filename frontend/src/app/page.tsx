import BackendStatus from "@/components/BackendStatus";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">FlowForge</h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Intelligent business process automation platform.
        </p>
      </div>

      <BackendStatus />

      <p className="text-sm text-gray-400 dark:text-gray-500">
        Phase 1: this page proves the browser, Next.js frontend, and FastAPI backend (backed by
        PostgreSQL) can all talk to each other.
      </p>
    </main>
  );
}
