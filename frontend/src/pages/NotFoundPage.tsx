import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <h1 className="text-4xl font-bold text-gray-900 mb-2">404</h1>
      <p className="text-gray-500 mb-6">Page not found</p>
      <Link to="/dashboard" className="text-blue-600 hover:underline">
        Back to Dashboard
      </Link>
    </div>
  );
}
